from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import UsageBatch, UsageRecord, Line
from src.schemas.usage import UsageBatchInput
from src.middlewares.auth import current_user, can_write
from src.services import usage
from src.services.audit import record
from src.utils.serialization import batch_dict
router = APIRouter(prefix='/usage')

@router.get('/batches')
def batches(db=Depends(get_db), u=Depends(current_user)):
    return [batch_dict(b) for b in db.scalars(select(UsageBatch).order_by(UsageBatch.id.desc()))]

@router.post('/batches', status_code=201)
def create(data: UsageBatchInput, db=Depends(get_db), u=Depends(can_write)):
    b = usage.create_batch(db, data)
    record(db, u.email, 'usage.import', {'id': b.id, 'rows': b.rows})
    db.commit()
    return batch_dict(b)

@router.get('/batches/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    b = db.get(UsageBatch, id)
    if not b: raise HTTPException(404, '用电批次不存在')
    lines = {l.id: l.code for l in db.scalars(select(Line))}
    records = [{'day': r.day, 'line': lines.get(r.line_id, r.line_id), 'kwh': r.kwh}
               for r in db.scalars(select(UsageRecord).where(UsageRecord.batch_id == id).order_by(UsageRecord.day).limit(500))]
    return {**batch_dict(b), 'records': records}

@router.get('/summary')
def month_summary(db=Depends(get_db), u=Depends(current_user)):
    return usage.summary(db)
