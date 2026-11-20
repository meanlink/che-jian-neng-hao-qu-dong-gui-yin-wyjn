from sqlalchemy import String, Double, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class UsageBatch(Base):
    __tablename__ = 'usage_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    source: Mapped[str] = mapped_column(String(200), default='manual.json')
    rows: Mapped[int] = mapped_column(default=0)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Double)
class UsageRecord(Base):
    __tablename__ = 'usage_records'
    __table_args__ = (UniqueConstraint('line_id', 'day', name='uq_usage_line_day'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('usage_batches.id'))
    line_id: Mapped[int] = mapped_column(ForeignKey('lines.id'))
    day: Mapped[str] = mapped_column(String(10))  # ISO YYYY-MM-DD
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM，归属核验月
    kwh: Mapped[float] = mapped_column(Double)
class LineMonth(Base):
    """线体月度台账：实测电量与核发占用在同一行内，行锁保证并发不超领。"""
    __tablename__ = 'line_months'
    __table_args__ = (UniqueConstraint('line_id', 'month', name='uq_line_month'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    line_id: Mapped[int] = mapped_column(ForeignKey('lines.id'))
    month: Mapped[str] = mapped_column(String(7))
    usage_kwh: Mapped[float] = mapped_column(Double, default=0)
    reserved_kwh: Mapped[float] = mapped_column(Double, default=0)  # 待核发占用
    issued_kwh: Mapped[float] = mapped_column(Double, default=0)    # 已核发（有效绿电）
