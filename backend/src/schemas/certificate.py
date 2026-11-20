from pydantic import BaseModel, Field
class CertificateInput(BaseModel):
    cert_no: str = Field(min_length=4, max_length=80)
    issuer: str = Field(min_length=2, max_length=160)
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    total_kwh: float = Field(gt=0, le=1_000_000_000)
class RevokeInput(BaseModel):
    effective_at: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$')  # 撤销生效日 YYYY-MM-DD
