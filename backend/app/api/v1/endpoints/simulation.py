"""Authenticated scenario simulation and comparison history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.simulation.service import SimulationService
from app.schemas.common import DomainResult
from app.schemas.simulation import SimulationInput, SimulationResult

router = APIRouter(prefix="/simulation", tags=["What-if Simulation"])


@router.post("/scenarios", response_model=DomainResult[SimulationResult])
def create_scenario(
    input_data: SimulationInput,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return SimulationService(db, context).run_scenario(input_data)


@router.get("/scenarios", response_model=list[dict])
def list_scenarios(
    limit: int = Query(default=20, ge=1, le=100),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return SimulationService(db, context).list_scenarios(limit)
