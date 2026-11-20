from sqlalchemy import String, Double
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Certificate(Base):
    """绿电凭证：总量恒定，reserved+issued 永不超过 total，可拆给多家客户。"""
    __tablename__ = 'certificates'
    id: Mapped[int] = mapped_column(primary_key=True)
    cert_no: Mapped[str] = mapped_column(String(80), unique=True)
    issuer: Mapped[str] = mapped_column(String(160))
    month: Mapped[str] = mapped_column(String(7))  # 只能匹配同月用电
    total_kwh: Mapped[float] = mapped_column(Double)
    reserved_kwh: Mapped[float] = mapped_column(Double, default=0)  # 待核发占用
    issued_kwh: Mapped[float] = mapped_column(Double, default=0)    # 已核发未失效
    status: Mapped[str] = mapped_column(String(20), default='active')
    revoke_effective_at: Mapped[float | None] = mapped_column(Double, nullable=True)  # 撤销生效时刻
    revoked_at: Mapped[float | None] = mapped_column(Double, nullable=True)           # 撤销实际执行时刻
    created_at: Mapped[float] = mapped_column(Double)
