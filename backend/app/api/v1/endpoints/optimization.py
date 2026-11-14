"""Budget-constrained procurement optimization endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.optimization.service import ProcurementOptimizerService
from app.schemas.common import DomainResult
from app.schemas.optimization import OptimizationInput, OptimizationResult

router = APIRouter(prefix="/optimization", tags=["Profit Optimization"])


@router.post("/procurement", response_model=DomainResult[OptimizationResult])
def optimize_procurement(
    payload: OptimizationInput,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return ProcurementOptimizerService(db, context).optimize_procurement(payload)
