from pydantic import BaseModel, Field
class BriefingPlanInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    customer_id: int
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    destination: str = Field(default='客户能源部 · 本地收件箱', min_length=2, max_length=120)
    interval_seconds: int = Field(default=86400, ge=60, le=2592000)
    delay_seconds: int = Field(default=0, ge=0, le=2592000)
