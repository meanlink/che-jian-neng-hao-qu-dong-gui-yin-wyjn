from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Certificate, Claim, Line, Customer, UsageRecord, LineMonth
from src.schemas.claim import ClaimInput, ReissueInput
from src.middlewares.auth import current_user, can_write
from src.services import claims as claims_svc
from src.services.audit import record
from src.utils.serialization import claim_dict, cert_dict
router = APIRouter(prefix='/claims')

def _maps(db):
    certs = {c.id: c for c in db.scalars(select(Certificate))}
    lines = {l.id: l for l in db.scalars(select(Line))}
    custs = {c.id: c for c in db.scalars(select(Customer))}
    return certs, lines, custs

def _reissue_states(db, invalidated):
    """每个失效声明的补发状态：待补发 / 补发在途 / 已补发 / 份额已沿链下移。"""
    states = {c.id: '待补发' for c in invalidated}
    children = {}
    for c in db.scalars(select(Claim).where(Claim.replaces_id.isnot(None))):
        children.setdefault(c.replaces_id, []).append(c)
    def fill(node_id):
        kids = children.get(node_id, [])
        if any(k.status == 'issued' for k in kids): return '已补发'
        if any(k.status == 'pending' for k in kids): return '补发在途'
        if any(k.status == 'invalidated' for k in kids): return '沿链下移'
        return '待补发'
    for c in invalidated: states[c.id] = fill(c.id)
    return states

@router.get('')
def listing(view: str = 'pending', db=Depends(get_db), u=Depends(current_user)):
    certs, lines, custs = _maps(db)
    q = select(Claim).order_by(Claim.id.desc())
    if view == 'pending': q = q.where(Claim.status == 'pending')
    elif view == 'issued': q = q.where(Claim.status == 'issued')
    elif view == 'reissue': q = q.where(Claim.status == 'invalidated')
    rows = db.scalars(q.limit(200)).all()
    states = _reissue_states(db, [c for c in rows if c.status == 'invalidated']) if view in ('reissue', 'all') else {}
    out = []
    for c in rows:
        line = lines.get(c.line_id); cust = custs.get(line.customer_id) if line else None
        cert = certs.get(c.certificate_id)
        out.append(claim_dict(c, cert.cert_no if cert else '', line.code if line else '',
                              cust.name if cust else '', states.get(c.id, '')))
    return out

@router.post('', status_code=201)
def create(data: ClaimInput, db=Depends(get_db), u=Depends(can_write)):
    claim, created = claims_svc.create(db, data, u)
    db.commit()
    if created: claims_svc.enqueue(claim.id)
    certs, lines, custs = _maps(db)
    line = lines.get(claim.line_id); cust = custs.get(line.customer_id) if line else None
    cert = certs.get(claim.certificate_id)
    return claim_dict(claim, cert.cert_no if cert else '', line.code if line else '', cust.name if cust else '')

@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    c = db.get(Claim, id)
    if not c: raise HTTPException(404, '核发声明不存在')
    cert = db.get(Certificate, c.certificate_id)
    line = db.get(Line, c.line_id)
    cust = db.get(Customer, line.customer_id) if line else None
    chain = []
    for node in db.scalars(select(Claim).where(Claim.root_id == (c.root_id or c.id)).order_by(Claim.id)):
        node_cert = db.get(Certificate, node.certificate_id)
        chain.append(claim_dict(node, node_cert.cert_no if node_cert else '', line.code if line else '',
                                cust.name if cust else ''))
    lm = db.scalar(select(LineMonth).where(LineMonth.line_id == c.line_id, LineMonth.month == c.month))
    usage_rows = [{'day': r.day, 'kwh': r.kwh} for r in db.scalars(
        select(UsageRecord).where(UsageRecord.line_id == c.line_id, UsageRecord.month == c.month).order_by(UsageRecord.day))]
    return {**claim_dict(c, cert.cert_no if cert else '', line.code if line else '', cust.name if cust else ''),
            'certificate': cert_dict(cert) if cert else None,
            'line': {'id': line.id, 'code': line.code, 'name': line.name} if line else None,
            'customer': {'id': cust.id, 'name': cust.name} if cust else None,
            'chain': chain,
            'line_month': {'usage_kwh': round(lm.usage_kwh, 3), 'reserved_kwh': round(lm.reserved_kwh, 3),
                           'issued_kwh': round(lm.issued_kwh, 3)} if lm else None,
            'usage_records': usage_rows}

@router.post('/{id}/reissue', status_code=201)
def reissue(id: int, data: ReissueInput, db=Depends(get_db), u=Depends(can_write)):
    claim, created = claims_svc.reissue(db, id, data, u)
    db.commit()
    if created: claims_svc.enqueue(claim.id)
    certs, lines, custs = _maps(db)
    line = lines.get(claim.line_id); cust = custs.get(line.customer_id) if line else None
    cert = certs.get(claim.certificate_id)
    return claim_dict(claim, cert.cert_no if cert else '', line.code if line else '', cust.name if cust else '')
