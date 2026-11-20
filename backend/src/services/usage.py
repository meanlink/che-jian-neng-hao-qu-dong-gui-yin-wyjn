import math, time
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models import UsageBatch, UsageRecord, LineMonth, Line, Customer
from src.utils.serialization import checksum

def _bounded_kwh(value, index):
    try:
        if isinstance(value, bool): raise ValueError()
        v = float(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(422, f'第 {index} 行实测日电耗必须为数值') from None
    if not math.isfinite(v) or not 0 < v <= 1_000_000_000:
        raise HTTPException(422, f'第 {index} 行实测日电耗必须介于 0 与 10亿 kWh 之间')
    return round(v, 3)

def create_batch(db, data):
    name = data.name.strip()
    if len(name) < 2: raise HTTPException(422, '批次名称去除空格后至少需要两个字符')
    if db.scalar(select(UsageBatch).where(UsageBatch.name == name)):
        raise HTTPException(409, '该用电批次名已存在，请修改名称')
    lines = {l.code: l for l in db.scalars(select(Line))}
    parsed, seen = [], set()
    for i, row in enumerate(data.records, 1):
        day_raw = str(row.get('day') or '').strip()
        try:
            day = date.fromisoformat(day_raw)
        except ValueError:
            raise HTTPException(422, f'第 {i} 行日期须为 ISO 格式 YYYY-MM-DD') from None
        code = str(row.get('line') or '').strip()
        if code not in lines: raise HTTPException(422, f'第 {i} 行线体编码 {code or "空"} 不存在，请先核对线体主数据')
        kwh = _bounded_kwh(row.get('kwh'), i)
        key = (lines[code].id, day.isoformat())
        if key in seen: raise HTTPException(422, f'第 {i} 行与前面记录重复：{code} {day.isoformat()} 同一天只能有一条实测')
        seen.add(key)
        parsed.append((lines[code], day.isoformat(), day.isoformat()[:7], kwh))
    # 精确核对：同一线体同一天已入库则整批拒绝（数据库唯一约束兜底）
    existing = set(db.execute(select(UsageRecord.line_id, UsageRecord.day).where(
        UsageRecord.line_id.in_({l.id for l, _, _, _ in parsed}),
        UsageRecord.day.in_({d for _, d, _, _ in parsed}))))
    for line, day, month, kwh in parsed:
        if (line.id, day) in existing:
            raise HTTPException(409, f'{line.code} 在 {day} 已有实测记录，同一线体一天只能入库一次')
    batch = UsageBatch(name=name, source=data.source, rows=len(parsed), checksum=checksum(data.records), created_at=time.time())
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, '批次名或线体日记录与已有数据冲突，请勿重复导入') from None
    months = {}
    for line, day, month, kwh in parsed:
        db.add(UsageRecord(batch_id=batch.id, line_id=line.id, day=day, month=month, kwh=kwh))
        months.setdefault((line.id, month), 0)
        months[(line.id, month)] += kwh
    for (line_id, month), total in months.items():
        lm = db.scalar(select(LineMonth).where(LineMonth.line_id == line_id, LineMonth.month == month))
        if not lm:
            lm = LineMonth(line_id=line_id, month=month, usage_kwh=0)
            db.add(lm); db.flush()
        lm.usage_kwh = round(lm.usage_kwh + total, 3)
    return batch

def summary(db):
    """线体月度台账：实测、核发中、已核发绿电。"""
    rows = []
    q = (select(LineMonth, Line, Customer)
         .join(Line, Line.id == LineMonth.line_id)
         .join(Customer, Customer.id == Line.customer_id)
         .order_by(LineMonth.month.desc(), Line.code))
    for lm, line, cust in db.execute(q):
        rows.append({'line_id': line.id, 'line_code': line.code, 'line_name': line.name,
                     'customer': cust.name, 'month': lm.month,
                     'usage_kwh': round(lm.usage_kwh, 3), 'reserved_kwh': round(lm.reserved_kwh, 3),
                     'issued_kwh': round(lm.issued_kwh, 3),
                     'regular_kwh': round(lm.usage_kwh - lm.issued_kwh, 3)})
    return rows
