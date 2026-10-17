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

class ClaimList(BaseModel):
    claims: list[Claim]