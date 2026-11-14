"""Transactional and idempotent posting service for confirmed extraction records."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import NotFoundError
from app.models.audit import AuditLog
from app.models.catalogue import Product
from app.models.document import DocumentExtraction, UploadedDocument
from app.models.inventory import MovementType
from app.models.operations import Expense, Sale, SaleItem
from app.models.udhar import Customer, TransactionType
from app.repositories.customer import CustomerRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.product import ProductRepository
from app.repositories.udhar import UdharRepository
from app.schemas.ingestion import (
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    DocumentExtractionData,
)


class PostingService:
    """Posts owner-reviewed and confirmed candidate records into authoritative domain tables."""

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.user_id = context.user_id
        self.prod_repo = ProductRepository(db, context)
        self.inv_repo = InventoryRepository(db, context)
        self.cust_repo = CustomerRepository(db, context)
        self.udhar_repo = UdharRepository(db, context)

    def post_confirmation(
        self, document_id: str, payload: DocumentConfirmRequest
    ) -> DocumentConfirmResponse:
        """Post reviewed candidate records transactionally with strict idempotency."""
        doc = (
            self.db.query(UploadedDocument)
            .filter(
                UploadedDocument.id == document_id,
                UploadedDocument.business_id == self.business_id,
            )
            .first()
        )
        if not doc:
            raise NotFoundError(f"Document {document_id} not found in this business")

        extraction = (
            self.db.query(DocumentExtraction)
            .filter(
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.business_id == self.business_id,
            )
            .first()
        )
        if not extraction:
            raise NotFoundError(f"Extractions for document {document_id} not found")

        # Idempotency check: If already confirmed, do not re-post duplicates
        if extraction.is_confirmed:
            return DocumentConfirmResponse(
                document_id=document_id,
                is_confirmed=True,
                sales_posted=0,
                expenses_posted=0,
                credit_transactions_posted=0,
                message="Already confirmed previously; duplicate posting skipped idempotently",
            )

        sales_posted = 0
        expenses_posted = 0
        credits_posted = 0

        now = datetime.now(UTC)

        # Fallback to saved extraction candidates if not explicitly overridden
        sales_to_post = payload.confirmed_sales
        expenses_to_post = payload.confirmed_expenses
        credits_to_post = payload.confirmed_credit_transactions

        if sales_to_post is None and expenses_to_post is None and credits_to_post is None:
            if extraction.validated_candidates_json:
                data = DocumentExtractionData.model_validate_json(
                    extraction.validated_candidates_json
                )
                sales_to_post = data.sales
                expenses_to_post = data.expenses
                credits_to_post = data.credit_transactions

        # 1. Post Sales
        if sales_to_post:
            for s_idx, sale_cand in enumerate(sales_to_post, start=1):
                sale_num = sale_cand.sale_number or f"DOC-{doc.id[:8]}-S{s_idx}"
                sale = Sale(
                    business_id=self.business_id,
                    sale_number=sale_num,
                    sold_at=sale_cand.sold_at or now,
                    total_amount=sale_cand.total_amount,
                    payment_mode=sale_cand.payment_mode,
                    status="COMPLETED",
                )
                self.db.add(sale)
                self.db.flush()

                for item_cand in sale_cand.items:
                    # Match or auto-create product
                    prod = (
                        self.db.query(Product)
                        .filter(
                            Product.business_id == self.business_id,
                            Product.name == item_cand.product_name,
                        )
                        .first()
                    )
                    if not prod:
                        prod = self.prod_repo.create_product(
                            name=item_cand.product_name,
                            selling_price=item_cand.unit_price,
                            cost_price=item_cand.unit_cost,
                        )

                    sale_item = SaleItem(
                        business_id=self.business_id,
                        sale_id=sale.id,
                        product_id=prod.id,
                        quantity=item_cand.quantity,
                        unit_price=item_cand.unit_price,
                        unit_cost=item_cand.unit_cost or prod.cost_price,
                        total_amount=item_cand.total_amount,
                    )
                    self.db.add(sale_item)

                    # Deduct physical inventory through an immutable movement
                    self.inv_repo.record_movement(
                        product_id=prod.id,
                        movement_type=MovementType.SALE_DISPATCH,
                        quantity=item_cand.quantity,
                        unit_cost=item_cand.unit_cost or prod.cost_price,
                        reference_type="SALE_CONFIRMATION",
                        reference_id=sale.id,
                        notes=f"Auto-dispatch from confirmed document {doc.filename}",
                    )

                sales_posted += 1

        # 2. Post Expenses
        if expenses_to_post:
            for exp_cand in expenses_to_post:
                expense = Expense(
                    business_id=self.business_id,
                    category=exp_cand.category,
                    amount=exp_cand.amount,
                    expense_date=exp_cand.expense_date or now,
                    description=exp_cand.description or f"Imported from {doc.filename}",
                    payment_mode=exp_cand.payment_mode,
                )
                self.db.add(expense)
                expenses_posted += 1

        # 3. Post Udhar Credit Transactions
        if credits_to_post:
            for r_idx, c_cand in enumerate(credits_to_post, start=1):
                # Customer matching
                cust = (
                    self.db.query(Customer)
                    .filter(
                        Customer.business_id == self.business_id,
                        Customer.display_name == c_cand.customer_candidate_name,
                    )
                    .first()
                )
                if not cust:
                    cust = self.cust_repo.create_customer(
                        display_name=c_cand.customer_candidate_name,
                        phone_e164=c_cand.phone,
                    )

                credit_acc = self.cust_repo.get_credit_account_or_fail(cust.id)
                idemp_key = f"doc_{doc.id}_row_{c_cand.source_row or r_idx}"

                if c_cand.transaction_type == TransactionType.REPAYMENT.value:
                    self.udhar_repo.record_repayment(
                        credit_account_id=credit_acc.id,
                        amount=c_cand.amount,
                        description=c_cand.description
                        or f"Confirmed repayment from {doc.filename}",
                        reference=c_cand.reference or f"DOC-{doc.id[:8]}",
                        idempotency_key=idemp_key,
                    )
                else:
                    self.udhar_repo.record_charge(
                        credit_account_id=credit_acc.id,
                        amount=c_cand.amount,
                        description=c_cand.description
                        or f"Confirmed credit sale from {doc.filename}",
                        reference=c_cand.reference or f"DOC-{doc.id[:8]}",
                        due_at=c_cand.due_at,
                        idempotency_key=idemp_key,
                    )

                credits_posted += 1

        # 4. Mark document confirmed
        extraction.is_confirmed = True
        extraction.confirmed_by = self.user_id
        extraction.confirmed_at = now

        doc.status = "CONFIRMED"

        # 5. Audit Log
        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.user_id,
            action="CONFIRM_IMPORT",
            entity_type="UPLOADED_DOCUMENT",
            entity_id=doc.id,
            changes_json=(
                f'{{"sales_posted": {sales_posted}, '
                f'"expenses_posted": {expenses_posted}, '
                f'"credit_transactions_posted": {credits_posted}}}'
            ),
        )
        self.db.add(audit)
        self.db.commit()

        return DocumentConfirmResponse(
            document_id=doc.id,
            is_confirmed=True,
            sales_posted=sales_posted,
            expenses_posted=expenses_posted,
            credit_transactions_posted=credits_posted,
            message="Records posted transactionally and verified against ledger constraints",
        )
