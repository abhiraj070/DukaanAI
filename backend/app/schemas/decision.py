"""Typed request and evidence contract for AI Decision Lab."""

from pydantic import BaseModel, Field


class DecisionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)


class DecisionEvidence(BaseModel):
    source: str
    detail: str


class DecisionResponse(BaseModel):
    answer: str
    evidence: list[DecisionEvidence] = []
    assumptions: list[str] = []
    limitations: list[str] = []
    proposed_actions: list[str] = []
