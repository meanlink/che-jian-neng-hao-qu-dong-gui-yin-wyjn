from pydantic import BaseModel, Field
class ClaimInput(BaseModel):
    certificate_id: int
    line_id: int
    kwh: float = Field(gt=0, le=1_000_000_000)
    note: str = Field(default='', max_length=300)
    idempotency_key: str | None = Field(default=None, max_length=80)
class ReissueInput(BaseModel):
    certificate_id: int  # 换发的新凭证，只补失效份额
