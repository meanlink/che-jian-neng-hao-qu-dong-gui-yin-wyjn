import time
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select, update
from src.models import Certificate, Claim, LineMonth
from src.services.audit import record

def issuable(cert, now=None):
    """撤销生效后停止核发：生效时刻起凭证不再接受核发。"""
    now = time.time() if now is None else now
    return cert.status == 'active' and (cert.revoke_effective_at is None or now < cert.revoke_effective_at)

def register(db, data):
    cert_no = data.cert_no.strip()
    if db.scalar(select(Certificate).where(Certificate.cert_no == cert_no)):
        raise HTTPException(409, '该凭证号已登记，请勿重复录入')
    c = Certificate(cert_no=cert_no, issuer=data.issuer.strip(), month=data.month,
                    total_kwh=round(data.total_kwh, 3), created_at=time.time())
    db.add(c); db.flush()
    return c

def request_revoke(db, cert, effective_date, actor):
    try:
        day = datetime.strptime(effective_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(422, '撤销生效日须为 YYYY-MM-DD') from None
    effective_ts = time.mktime(day.timetuple())  # 生效日 00:00 起停止核发
    moved = db.execute(update(Certificate).where(Certificate.id == cert.id, Certificate.status == 'active',
                                                 Certificate.revoke_effective_at.is_(None))
                       .values(revoke_effective_at=effective_ts)).rowcount
    if moved != 1: raise HTTPException(409, '凭证已撤销或撤销已在等待生效，请勿重复提交')
    record(db, actor, 'certificate.revoke_scheduled', {'id': cert.id, 'cert_no': cert.cert_no, 'effective_at': effective_date})
    if effective_ts <= time.time():
        apply_revocation(db, cert)
    return db.get(Certificate, cert.id)

def apply_due_revocations(db):
    now = time.time()
    due = db.scalars(select(Certificate.id).where(Certificate.status == 'active',
                                                  Certificate.revoke_effective_at.isnot(None),
                                                  Certificate.revoke_effective_at <= now))
    for cert_id in list(due):
        apply_revocation(db, db.get(Certificate, cert_id))

def apply_revocation(db, cert):
    """撤销生效：在途声明取消并释放占用；已核发份额失效（简报只扣这部分）。旧声明留档不删除。"""
    now = time.time()
    moved = db.execute(update(Certificate).where(Certificate.id == cert.id, Certificate.status == 'active')
                       .values(status='revoked', revoked_at=now)).rowcount
    if moved != 1: return db.get(Certificate, cert.id)  # 已被并发撤销
    cancelled = invalidated = 0
    released = lost = 0.0
    for claim in db.scalars(select(Claim).where(Claim.certificate_id == cert.id, Claim.status == 'pending')):
        taken = db.execute(update(Claim).where(Claim.id == claim.id, Claim.status == 'pending')
                           .values(status='cancelled', active_replaces_id=None)).rowcount
        if taken == 1:
            db.execute(update(Certificate).where(Certificate.id == cert.id).values(reserved_kwh=Certificate.reserved_kwh - claim.kwh))
            db.execute(update(LineMonth).where(LineMonth.line_id == claim.line_id, LineMonth.month == claim.month)
                       .values(reserved_kwh=LineMonth.reserved_kwh - claim.kwh))
            cancelled += 1; released += claim.kwh
    for claim in db.scalars(select(Claim).where(Claim.certificate_id == cert.id, Claim.status == 'issued')):
        taken = db.execute(update(Claim).where(Claim.id == claim.id, Claim.status == 'issued')
                           .values(status='invalidated', active_replaces_id=None)).rowcount
        if taken == 1:
            db.execute(update(Certificate).where(Certificate.id == cert.id).values(issued_kwh=Certificate.issued_kwh - claim.kwh))
            db.execute(update(LineMonth).where(LineMonth.line_id == claim.line_id, LineMonth.month == claim.month)
                       .values(issued_kwh=LineMonth.issued_kwh - claim.kwh))
            invalidated += 1; lost += claim.kwh
    record(db, 'system', 'certificate.revoked', {'id': cert.id, 'cert_no': cert.cert_no,
                                                 'cancelled_pending': cancelled, 'invalidated_issued': invalidated,
                                                 'released_reserved_kwh': round(released, 3), 'invalidated_kwh': round(lost, 3)})
    return db.get(Certificate, cert.id)
