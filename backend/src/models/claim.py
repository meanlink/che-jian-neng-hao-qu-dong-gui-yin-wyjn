from sqlalchemy import String, Double, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Claim(Base):
    """核发声明：一次申领或一次换证补发。状态机 pending→issued→invalidated；pending→cancelled。

    active_replaces_id：仅当本声明是在途补发（pending/issued）时等于 replaces_id，
    唯一索引保证同一失效份额最多一个在途补发，重试不会重复占量。
    """
    __tablename__ = 'claims'
    id: Mapped[int] = mapped_column(primary_key=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey('certificates.id'))
    line_id: Mapped[int] = mapped_column(ForeignKey('lines.id'))
    month: Mapped[str] = mapped_column(String(7))
    kwh: Mapped[float] = mapped_column(Double)
    kind: Mapped[str] = mapped_column(String(20), default='original')
    status: Mapped[str] = mapped_column(String(20), default='pending')
    root_id: Mapped[int] = mapped_column(default=0)  # 补发链根声明 id，便于整链追溯
    replaces_id: Mapped[int | None] = mapped_column(ForeignKey('claims.id'), nullable=True)
    active_replaces_id: Mapped[int | None] = mapped_column(unique=True, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    issued_at: Mapped[float | None] = mapped_column(Double, nullable=True)
