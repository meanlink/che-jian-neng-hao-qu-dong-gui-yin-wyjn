from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from src.config.database import get_db
from src.middlewares.auth import current_user
from src.models import UsageRecord, Certificate, Claim, Audit, Customer, Line, LineMonth
from src.services.business import metadata
router = APIRouter()

@router.get('/meta')
def meta(): return metadata()

@router.get('/customers')
def customers(db=Depends(get_db), user=Depends(current_user)):
    by_cust = {}
    for l in db.scalars(select(Line).order_by(Line.code)):
        by_cust.setdefault(l.customer_id, []).append({'id': l.id, 'code': l.code, 'name': l.name})
    return [{'id': c.id, 'code': c.code, 'name': c.name, 'lines': by_cust.get(c.id, [])}
            for c in db.scalars(select(Customer).order_by(Customer.id))]

@router.get('/overview')
def overview(db=Depends(get_db), user=Depends(current_user)):
    latest = db.scalar(select(func.max(LineMonth.month)))
    totals = {'usage_kwh': 0.0, 'green_kwh': 0.0, 'reserved_kwh': 0.0}
    per_line = []
    if latest:
        q = (select(LineMonth, Line).join(Line, Line.id == LineMonth.line_id).where(LineMonth.month == latest).order_by(Line.code))
        for lm, line in db.execute(q):
            totals['usage_kwh'] += lm.usage_kwh
            totals['green_kwh'] += lm.issued_kwh
            totals['reserved_kwh'] += lm.reserved_kwh
            per_line.append({'line_code': line.code, 'green_kwh': round(lm.issued_kwh, 1),
                             'regular_kwh': round(lm.usage_kwh - lm.issued_kwh, 1)})
    invalidated = db.scalar(select(func.coalesce(func.sum(Claim.kwh), 0.0)).where(Claim.status == 'invalidated'))
    awaiting = 0
    children = {}
    for c in db.scalars(select(Claim).where(Claim.replaces_id.isnot(None))):
        children.setdefault(c.replaces_id, []).append(c)
    for c in db.scalars(select(Claim).where(Claim.status == 'invalidated')):
        kids = children.get(c.id, [])
        if not any(k.status in ('pending', 'issued', 'invalidated') for k in kids): awaiting += 1
    return {'usage_records': db.scalar(select(func.count()).select_from(UsageRecord)),
            'certificates': db.scalar(select(func.count()).select_from(Certificate).where(Certificate.status == 'active')),
            'claims_pending': db.scalar(select(func.count()).select_from(Claim).where(Claim.status == 'pending')),
            'claims_issued': db.scalar(select(func.count()).select_from(Claim).where(Claim.status == 'issued')),
            'reissue_pending': awaiting,
            'invalidated_kwh': round(invalidated, 3),
            'latest_month': latest, 'totals': {k: round(v, 3) for k, v in totals.items()}, 'per_line': per_line}

@router.get('/audits')
def audits(db=Depends(get_db), user=Depends(current_user)):
    return [{'id': a.id, 'actor': a.actor, 'action': a.action, 'detail': a.detail, 'at': a.at}
            for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(50))]
