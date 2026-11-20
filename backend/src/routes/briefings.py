import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from src.config.database import get_db
from src.config.settings import ARTIFACT_DIR
from src.models import BriefingPlan, Delivery, Customer
from src.schemas.briefing import BriefingPlanInput
from src.middlewares.auth import current_user, admin_only
from src.services import briefings
from src.services.audit import record
from src.utils.serialization import plan_dict, delivery_dict
router = APIRouter()

@router.get('/verification')
def get_verification(customer_id: int, month: str, db=Depends(get_db), u=Depends(current_user)):
    return briefings.verification(db, customer_id, month)

@router.get('/briefings/plans')
def plans(db=Depends(get_db), u=Depends(current_user)):
    custs = {c.id: c.name for c in db.scalars(select(Customer))}
    return [plan_dict(p, custs.get(p.customer_id, '')) for p in db.scalars(select(BriefingPlan).order_by(BriefingPlan.id.desc()))]

@router.post('/briefings/plans', status_code=201)
def create_plan(data: BriefingPlanInput, db=Depends(get_db), u=Depends(admin_only)):
    p = briefings.create_plan(db, data)
    record(db, u.email, 'briefing.plan', {'id': p.id, 'customer_id': p.customer_id, 'month': p.month})
    db.commit()
    custs = {c.id: c.name for c in db.scalars(select(Customer))}
    return plan_dict(p, custs.get(p.customer_id, ''))

@router.post('/briefings/plans/{id}/toggle')
def toggle(id: int, db=Depends(get_db), u=Depends(admin_only)):
    p = db.get(BriefingPlan, id)
    if not p: raise HTTPException(404, '简报计划不存在')
    p.enabled = not p.enabled
    record(db, u.email, 'briefing.toggle', {'id': id, 'enabled': p.enabled})
    db.commit()
    custs = {c.id: c.name for c in db.scalars(select(Customer))}
    return plan_dict(p, custs.get(p.customer_id, ''))

@router.get('/briefings/deliveries')
def deliveries(db=Depends(get_db), u=Depends(current_user)):
    return [delivery_dict(d) for d in db.scalars(select(Delivery).order_by(Delivery.id.desc()).limit(100))]

@router.get('/briefings/deliveries/{id}/download')
def download(id: int, format: str = 'csv', db=Depends(get_db), u=Depends(current_user)):
    d = db.get(Delivery, id)
    if not d: raise HTTPException(404, '归档不存在')
    if format not in ('csv', 'json'): raise HTTPException(422, '支持 CSV 或 JSON')
    filename = d.filename + ('.json' if format == 'json' else '')
    p = os.path.join(ARTIFACT_DIR, filename)
    if not os.path.exists(p): raise HTTPException(404, '归档文件不存在，请等待计划下次执行')
    return FileResponse(p, filename=filename, media_type='application/json' if format == 'json' else 'text/csv; charset=utf-8')
