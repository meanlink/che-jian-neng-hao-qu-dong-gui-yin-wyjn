from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Certificate, Claim, Line, Customer
from src.schemas.certificate import CertificateInput, RevokeInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import certificates
from src.services.audit import record
from src.utils.serialization import cert_dict, claim_dict
router = APIRouter(prefix='/certificates')

@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    return [cert_dict(c) for c in db.scalars(select(Certificate).order_by(Certificate.id.desc()))]

@router.post('', status_code=201)
def create(data: CertificateInput, db=Depends(get_db), u=Depends(can_write)):
    c = certificates.register(db, data)
    record(db, u.email, 'certificate.register', {'id': c.id, 'cert_no': c.cert_no, 'total_kwh': c.total_kwh})
    db.commit()
    return cert_dict(c)

@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    c = db.get(Certificate, id)
    if not c: raise HTTPException(404, '绿电凭证不存在')
    lines = {l.id: l for l in db.scalars(select(Line))}
    custs = {cu.id: cu for cu in db.scalars(select(Customer))}
    claims = []
    for cl in db.scalars(select(Claim).where(Claim.certificate_id == id).order_by(Claim.id.desc())):
        line = lines.get(cl.line_id)
        cust = custs.get(line.customer_id) if line else None
        claims.append(claim_dict(cl, c.cert_no, line.code if line else '', cust.name if cust else ''))
    return {**cert_dict(c), 'claims': claims}

@router.post('/{id}/revoke')
def revoke(id: int, data: RevokeInput, db=Depends(get_db), u=Depends(admin_only)):
    c = db.get(Certificate, id)
    if not c: raise HTTPException(404, '绿电凭证不存在')
    certificates.request_revoke(db, c, data.effective_at, u.email)
    db.commit()
    return cert_dict(c)
