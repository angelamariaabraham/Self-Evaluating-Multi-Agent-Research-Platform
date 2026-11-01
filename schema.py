#schema.py
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Claim(BaseModel):
    claim_id: str
    claim_text: str
    source_url: str
    evidence_span: str = Field(description="Exact sentence copied from the source text")
    contradiction_flag: Optional[bool] = None
    stress_verdict: Optional[Literal["holds", "weak", "unsupported"]] = None
    confidence: Optional[float] = None  # 0.0 to 1.0, filled later
    span_supports_claim: Optional[bool] = None
    stress_weakness: Optional[str] = None
    confidence_reasons: list[str] = Field(default_factory=list)

class ClaimList(BaseModel):
    claims: list[Claim]


class ContradictionFlag(BaseModel):
    claim_ids: list[str]
    explanation: str

class ContradictionResult(BaseModel):
    flags: list[ContradictionFlag]
    pairs_checked: int = 0
    pairs_failed: int = 0

class StressItem(BaseModel):
    claim_id: str
    verdict: Literal["holds", "weak"]
    weakness: str
    reason: str

class StressResult(BaseModel):
    items: list[StressItem]
    failed: int = 0