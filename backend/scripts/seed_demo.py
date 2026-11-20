import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Customer, Line, UsageBatch, UsageRecord, LineMonth, Certificate, Claim, BriefingPlan, Delivery, Audit
from src.schemas.usage import UsageBatchInput
from src.schemas.claim import ClaimInput, ReissueInput
from src.services.business import LINES, SEED_MONTHS, seed_usage_records
from src.services import usage as usage_svc, claims as claims_svc, briefings as briefings_svc
from src.services import certificates as certs_svc
from src.utils.security import hash_password

def _user(db, role, name):
    email = role + '@demo.local'
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        u = User(email=email, name=name, role=role, password=hash_password('Demo123!'))
        db.add(u); db.flush()
    return u

def _claim(db, admin, cert, line_code, kwh, key, note=''):
    line = db.scalar(select(Line).where(Line.code == line_code))
    claim, created = claims_svc.create(db, ClaimInput(certificate_id=cert.id, line_id=line.id, kwh=kwh,
                                                      note=note, idempotency_key=key), admin)
    return claim

def seed():
    migrate()
    with Session() as db:
        admin = _user(db, 'admin', '林知 · 业务负责人')
        _user(db, 'analyst', '陈舟 · 能源专员')
        _user(db, 'viewer', '周禾 · 观察员')
        # 客户与线体主数据
        lines = {}
        for cust_code, cust_name, line_defs in LINES:
            cust = db.scalar(select(Customer).where(Customer.code == cust_code))
            if not cust:
                cust = Customer(code=cust_code, name=cust_name)
                db.add(cust); db.flush()
            for code, name in line_defs:
                line = db.scalar(select(Line).where(Line.code == code))
                if not line:
                    line = Line(code=code, name=name, customer_id=cust.id)
                    db.add(line); db.flush()
                lines[code] = line
        # 用电批次：三家客户 2026-09/2026-10 逐日实测
        if not db.scalar(select(UsageBatch).where(UsageBatch.name == '三家客户_2026年9-10月_线体日耗.csv')):
            rows = seed_usage_records()
            usage_svc.create_batch(db, UsageBatchInput(name='三家客户_2026年9-10月_线体日耗.csv',
                                                       source='meter-export-202611.csv', records=rows))
        # 绿电凭证：A 可拆多家，B 将撤销，C 用于换证补发，D 覆盖 9 月
        def cert(no, issuer, month, total):
            c = db.scalar(select(Certificate).where(Certificate.cert_no == no))
            if not c:
                c = certs_svc.register(db, type('C', (), {'cert_no': no, 'issuer': issuer, 'month': month, 'total_kwh': total})())
            return c
        a = cert('GE-2026-10-A001', '华东绿色电力交易中心', '2026-10', 200000)
        b = cert('GE-2026-10-B002', '华东绿色电力交易中心', '2026-10', 150000)
        c3 = cert('GE-2026-10-C003', '省间绿电凭证平台', '2026-10', 120000)
        d = cert('GE-2026-09-D004', '华东绿色电力交易中心', '2026-09', 500000)
        # 9 月：六条线各核发 70,000 kWh
        for code in lines:
            claim = _claim(db, admin, d, code, 70000, f'seed-claim-d004-{code}', '9 月月度核发')
            claims_svc.issue(db, claim.id)
        # 10 月：A001 拆给三家客户
        for code, kwh in [('P01', 60000), ('S01', 50000), ('M01', 40000)]:
            claim = _claim(db, admin, a, code, kwh, f'seed-claim-a001-{code}', '10 月拆分核发')
            claims_svc.issue(db, claim.id)
        # B002 核发后撤销：P02 已核发 45,000、S02 已核发 60,000、P03 在途 20,000
        p02 = _claim(db, admin, b, 'P02', 45000, 'seed-claim-b002-p02', '10 月核发')
        claims_svc.issue(db, p02.id)
        s02 = _claim(db, admin, b, 'S02', 60000, 'seed-claim-b002-s02', '10 月核发')
        claims_svc.issue(db, s02.id)
        _claim(db, admin, b, 'P03', 20000, 'seed-claim-b002-p03', '10 月在途申领')
        if b.revoke_effective_at is None:
            certs_svc.request_revoke(db, b, '2026-11-08', 'seed')  # 生效日已过，立即生效
        # S02 的失效份额换 C003 补发并核发；P02 的失效份额留作待补发
        s02 = db.scalar(select(Claim).where(Claim.idempotency_key == 'seed-claim-b002-s02'))
        if s02 and s02.status == 'invalidated' and not db.scalar(select(Claim).where(Claim.replaces_id == s02.id)):
            re, created = claims_svc.reissue(db, s02.id, ReissueInput(certificate_id=c3.id), admin)
            claims_svc.issue(db, re.id)
        # 留给后台 worker 现场核发的在途声明
        _claim(db, admin, c3, 'P03', 25000, 'seed-claim-c003-p03', '10 月补充申领 · 待核发')
        # 月度核验简报计划并投递一次
        cc = db.scalar(select(Customer).where(Customer.code == 'CUST-CC'))
        if not db.scalar(select(BriefingPlan).where(BriefingPlan.name == '澄川金属 2026-10 月度绿电核验简报')):
            plan = briefings_svc.create_plan(db, type('P', (), {'name': '澄川金属 2026-10 月度绿电核验简报',
                                                                'customer_id': cc.id, 'month': '2026-10',
                                                                'destination': '澄川金属能源部 · 本地收件箱',
                                                                'interval_seconds': 86400, 'delay_seconds': 0})())
            briefings_svc.deliver(db, plan)
        db.add(Audit(actor='seed', action='demo.baseline', detail={'months': SEED_MONTHS}, at=time.time()))
        db.commit()
        counts = {m.__tablename__: db.scalar(select(func.count()).select_from(m))
                  for m in [User, Customer, Line, UsageBatch, UsageRecord, Certificate, Claim, BriefingPlan, Delivery, Audit]}
        print(json.dumps(counts, ensure_ascii=False))
        return counts

if __name__ == '__main__': seed()
