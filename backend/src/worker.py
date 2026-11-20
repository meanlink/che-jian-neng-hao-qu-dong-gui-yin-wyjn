import time, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Claim, BriefingPlan
from src.services import claims as claims_svc
from src.services.certificates import apply_due_revocations
from src.services.briefings import deliver
from src.services.audit import record
logging.basicConfig(level=logging.INFO)

def issue_one(claim_id):
    with Session() as db:
        claims_svc.issue(db, claim_id)
        db.commit()

def tick():
    with Session() as db:
        apply_due_revocations(db)  # 撤销生效后停止核发：先处理到期撤销
        db.commit()
    with Session() as db:
        queued = list(db.scalars(select(Claim.id).where(Claim.status == 'pending').limit(5)))
    for claim_id in queued: issue_one(claim_id)
    with Session() as db:
        for plan in db.scalars(select(BriefingPlan).where(BriefingPlan.enabled == True, BriefingPlan.next_run <= time.time())):
            d = deliver(db, plan)
            if d: record(db, 'worker', 'briefing.delivered', {'id': plan.id, 'delivery': d.id})
        db.commit()

def main():
    r = Redis.from_url(REDIS_URL, socket_timeout=3)
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item = r.blpop('claims:queue', timeout=1)
            if item: issue_one(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry'); time.sleep(2)

if __name__ == '__main__': main()
