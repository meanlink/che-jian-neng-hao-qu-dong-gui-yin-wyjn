import time, os, csv, io, hashlib, json
from fastapi import HTTPException
from sqlalchemy import select, func
from src.models import Customer, Line, LineMonth, Claim, Certificate, BriefingPlan, Delivery
from src.config.settings import ARTIFACT_DIR

def verification(db, customer_id, month):
    """按月核验：绿电=有效已核发；未匹配部分为普通用电；失效份额单列扣减。"""
    customer = db.get(Customer, customer_id)
    if not customer: raise HTTPException(404, '客户不存在')
    lines = db.scalars(select(Line).where(Line.customer_id == customer.id).order_by(Line.code)).all()
    rows = []
    for line in lines:
        lm = db.scalar(select(LineMonth).where(LineMonth.line_id == line.id, LineMonth.month == month))
        usage = lm.usage_kwh if lm else 0.0
        reserved = lm.reserved_kwh if lm else 0.0
        green = lm.issued_kwh if lm else 0.0
        invalidated = db.scalar(select(func.coalesce(func.sum(Claim.kwh), 0.0)).where(
            Claim.line_id == line.id, Claim.month == month, Claim.status == 'invalidated'))
        rows.append({'line_id': line.id, 'line_code': line.code, 'line_name': line.name,
                     'usage_kwh': round(usage, 3), 'green_kwh': round(green, 3),
                     'regular_kwh': round(usage - green, 3), 'reserved_kwh': round(reserved, 3),
                     'invalidated_kwh': round(invalidated, 3)})
    certs = []
    line_ids = [l.id for l in lines]
    q = (select(Certificate.cert_no, Certificate.issuer, func.sum(Claim.kwh))
         .join(Claim, Claim.certificate_id == Certificate.id)
         .where(Claim.line_id.in_(line_ids), Claim.month == month, Claim.status == 'issued')
         .group_by(Certificate.id))
    for cert_no, issuer, kwh in db.execute(q):
        certs.append({'cert_no': cert_no, 'issuer': issuer, 'kwh': round(kwh, 3)})
    totals = {k: round(sum(r[k] for r in rows), 3) for k in
              ('usage_kwh', 'green_kwh', 'regular_kwh', 'reserved_kwh', 'invalidated_kwh')}
    return {'customer': {'id': customer.id, 'code': customer.code, 'name': customer.name},
            'month': month, 'lines': rows, 'certificates': certs, 'totals': totals,
            'generated_at': time.time()}

def create_plan(db, data):
    if not db.get(Customer, data.customer_id): raise HTTPException(404, '客户不存在')
    plan = BriefingPlan(name=data.name.strip(), customer_id=data.customer_id, month=data.month,
                        destination=data.destination.strip(), interval_seconds=data.interval_seconds,
                        next_run=time.time() + data.delay_seconds, enabled=True)
    db.add(plan); db.flush()
    return plan

def _safe(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool): return v
    text = str(v)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text

def deliver(db, plan):
    """生成月度核验简报：只扣失效份额后的绿电口径快照，CSV+JSON 留档。"""
    snap = verification(db, plan.customer_id, plan.month)
    out = io.StringIO(); out.write('﻿')
    writer = csv.writer(out)
    writer.writerow([_safe(h) for h in ['线体', '归属月', '实测用电kWh', '绿电kWh', '普通用电kWh', '核发中kWh', '失效扣减kWh']])
    for r in snap['lines']:
        writer.writerow([_safe(v) for v in [r['line_code'], snap['month'], r['usage_kwh'], r['green_kwh'],
                                            r['regular_kwh'], r['reserved_kwh'], r['invalidated_kwh']]])
    t = snap['totals']
    writer.writerow([_safe(v) for v in ['合计', snap['month'], t['usage_kwh'], t['green_kwh'],
                                        t['regular_kwh'], t['reserved_kwh'], t['invalidated_kwh']]])
    data = out.getvalue().encode('utf-8')
    delivery = Delivery(plan_id=plan.id, created_at=time.time(),
                        checksum=hashlib.sha256(data).hexdigest(), filename='', destination=plan.destination)
    db.add(delivery); db.flush()
    delivery.filename = f'briefing-{plan.id}-delivery-{delivery.id}.csv'
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR, delivery.filename), 'wb') as f: f.write(data)
    with open(os.path.join(ARTIFACT_DIR, delivery.filename + '.json'), 'w') as f:
        json.dump({'plan': plan.name, 'verification': snap, 'checksum': delivery.checksum}, f, ensure_ascii=False, allow_nan=False)
    plan.next_run = time.time() + plan.interval_seconds
    return delivery
