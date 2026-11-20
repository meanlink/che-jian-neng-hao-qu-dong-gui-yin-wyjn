import time
from fastapi import HTTPException
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError
from redis import Redis
from src.config.settings import REDIS_URL
from src.models import Certificate, Claim, Line, LineMonth
from src.services.audit import record
from src.services.certificates import issuable

EPS = 1e-6

def _line_month(db, line_id, month):
    return db.scalar(select(LineMonth).where(LineMonth.line_id == line_id, LineMonth.month == month))

def _reserve(db, cert, lm, kwh, now):
    """凭证与线体当月电量都不能超领：预检给出业务报错，原子条件更新兜底并发。"""
    if cert.reserved_kwh + cert.issued_kwh + kwh > cert.total_kwh + EPS:
        raise HTTPException(409, f'凭证可核发余量不足：剩余 {round(cert.total_kwh - cert.reserved_kwh - cert.issued_kwh, 3)} kWh')
    if lm is None or lm.usage_kwh <= 0:
        raise HTTPException(422, '该线体当月无实测用电记录，不能核发')
    if lm.reserved_kwh + lm.issued_kwh + kwh > lm.usage_kwh + EPS:
        raise HTTPException(409, f'线体当月可核发余量不足：剩余 {round(lm.usage_kwh - lm.reserved_kwh - lm.issued_kwh, 3)} kWh')
    moved = db.execute(update(Certificate).where(Certificate.id == cert.id, Certificate.status == 'active',
                                                 or_(Certificate.revoke_effective_at.is_(None), Certificate.revoke_effective_at > now),
                                                 Certificate.reserved_kwh + Certificate.issued_kwh + kwh <= Certificate.total_kwh + EPS)
                       .values(reserved_kwh=Certificate.reserved_kwh + kwh)).rowcount
    if moved != 1: raise HTTPException(409, '凭证可核发余量不足或已停止核发，请刷新后重试')

def create(db, data, user):
    if data.idempotency_key:
        existing = db.scalar(select(Claim).where(Claim.idempotency_key == data.idempotency_key))
        if existing: return existing, False  # 幂等键命中：重试不重复占量
    cert = db.get(Certificate, data.certificate_id)
    if not cert: raise HTTPException(404, '绿电凭证不存在')
    if not issuable(cert): raise HTTPException(409, '凭证已撤销或撤销已生效，停止核发')
    line = db.get(Line, data.line_id)
    if not line: raise HTTPException(404, '线体不存在')
    kwh = round(data.kwh, 3)
    month = cert.month  # 同月匹配：声明归属月强制取凭证归属月
    lm = _line_month(db, line.id, month)
    now = time.time()
    _reserve(db, cert, lm, kwh, now)
    moved = db.execute(update(LineMonth).where(LineMonth.id == lm.id,
                                               LineMonth.reserved_kwh + LineMonth.issued_kwh + kwh <= LineMonth.usage_kwh + EPS)
                       .values(reserved_kwh=LineMonth.reserved_kwh + kwh)).rowcount
    if moved != 1: raise HTTPException(409, '线体当月可核发余量不足，请刷新后重试')
    claim = Claim(certificate_id=cert.id, line_id=line.id, month=month, kwh=kwh, kind='original',
                  idempotency_key=data.idempotency_key or None, note=data.note.strip(),
                  created_by=user.id, created_at=now)
    db.add(claim)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, '相同幂等键的声明已存在，重试不会重复占量') from None
    claim.root_id = claim.id
    record(db, user.email, 'claim.create', {'id': claim.id, 'cert_no': cert.cert_no, 'line': line.code, 'month': month, 'kwh': kwh})
    return claim, True

def issue(db, claim_id):
    """核发：在途占用转为已核发。状态 CAS 保证重复出队/重试不重复占量。"""
    claim = db.get(Claim, claim_id)
    if not claim or claim.status != 'pending': return None
    now = time.time()
    taken = db.execute(update(Claim).where(Claim.id == claim_id, Claim.status == 'pending')
                       .values(status='issued', issued_at=now)).rowcount
    if taken != 1: return None
    moved = db.execute(update(Certificate).where(Certificate.id == claim.certificate_id,
                                                 Certificate.status == 'active',
                                                 or_(Certificate.revoke_effective_at.is_(None), Certificate.revoke_effective_at > now))
                       .values(reserved_kwh=Certificate.reserved_kwh - claim.kwh,
                               issued_kwh=Certificate.issued_kwh + claim.kwh)).rowcount
    if moved != 1: raise HTTPException(409, '凭证已停止核发，等待撤销任务清理')  # 触发回滚，声明回到在途
    db.execute(update(LineMonth).where(LineMonth.line_id == claim.line_id, LineMonth.month == claim.month)
               .values(reserved_kwh=LineMonth.reserved_kwh - claim.kwh, issued_kwh=LineMonth.issued_kwh + claim.kwh))
    record(db, 'worker', 'claim.issued', {'id': claim_id, 'kwh': claim.kwh})
    return db.get(Claim, claim_id)

def chain_tip(db, root_id):
    """补发链当前可补发端点：失效份额沿链下移，任一时刻最多一个可补发端点。"""
    nodes = db.scalars(select(Claim).where(Claim.root_id == root_id).order_by(Claim.id)).all()
    children = {}
    for n in nodes: children.setdefault(n.replaces_id, []).append(n)
    node = next((n for n in nodes if n.id == root_id), None)
    while node:
        mine = children.get(node.id, [])
        if any(c.status in ('pending', 'issued') for c in mine): return None  # 已有在途或已完成补发
        deeper = [c for c in mine if c.status == 'invalidated']
        if deeper: node = deeper[0]; continue  # 失效份额沿链下移
        return node if node.status == 'invalidated' else None
    return None

def reissue(db, original_id, data, user):
    original = db.get(Claim, original_id)
    if not original: raise HTTPException(404, '原声明不存在')
    cert = db.get(Certificate, data.certificate_id)
    if not cert: raise HTTPException(404, '换发凭证不存在')
    if original.status != 'invalidated': raise HTTPException(409, '仅已失效的声明可以换证补发')
    tip = chain_tip(db, original.root_id or original.id)
    if tip is None: raise HTTPException(409, '该失效份额已有在途或已完成的补发，请勿重复提交')
    if tip.id != original.id: raise HTTPException(409, f'失效份额已沿补发链下移，请对声明 #{tip.id} 发起补发')
    if not issuable(cert): raise HTTPException(409, '换发凭证已撤销或撤销已生效，停止核发')
    if cert.month != original.month: raise HTTPException(422, f'换发凭证归属月须与原声明同为 {original.month}')
    kwh = original.kwh  # 只补失效份额，金额由服务端锁定
    lm = _line_month(db, original.line_id, original.month)
    now = time.time()
    _reserve(db, cert, lm, kwh, now)
    moved = db.execute(update(LineMonth).where(LineMonth.id == lm.id,
                                               LineMonth.reserved_kwh + LineMonth.issued_kwh + kwh <= LineMonth.usage_kwh + EPS)
                       .values(reserved_kwh=LineMonth.reserved_kwh + kwh)).rowcount
    if moved != 1: raise HTTPException(409, '线体当月可核发余量不足，请刷新后重试')
    claim = Claim(certificate_id=cert.id, line_id=original.line_id, month=original.month, kwh=kwh,
                  kind='reissue', replaces_id=original.id, active_replaces_id=original.id,
                  root_id=original.root_id or original.id, note=f'换证补发 · 替代声明 #{original.id}',
                  created_by=user.id, created_at=now)
    db.add(claim)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, '该失效份额已有在途补发，重试不会重复占量') from None
    record(db, user.email, 'claim.reissue', {'id': claim.id, 'replaces': original.id, 'cert_no': cert.cert_no, 'kwh': kwh})
    return claim, True

def enqueue(claim_id):
    try:
        r = Redis.from_url(REDIS_URL); r.rpush('claims:queue', claim_id); r.close()
    except Exception:
        pass  # SQL 中的 pending 状态是持久兜底，worker 定时扫描
