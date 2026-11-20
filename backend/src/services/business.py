"""绿电凭证月度核验：业务元数据与演示数据口径。"""
from datetime import date, timedelta
import calendar
import math
import random

LINES = [
    ("CUST-CC", "澄川金属", [("P01", "冲压P01"), ("P02", "冲压P02"), ("P03", "冲压P03")]),
    ("CUST-YZ", "渝州电子", [("S01", "贴片S01"), ("S02", "贴片S02")]),
    ("CUST-MZ", "明州塑业", [("M01", "注塑M01")]),
]
SEED_MONTHS = ["2026-09", "2026-10"]


def metadata():
    return {
        "name": "绿电凭证月度核验", "short": "green-ledger",
        "tagline": "同月绿电凭证匹配线体实测日耗，核发、撤销与换证补发全程留痕",
        "client": "模拟客户：澄川金属、渝州电子、明州塑业三家用能企业，共 6 条产线。",
        "workflow": "能源专员按月核验各线绿电：导入实测日耗，用同月绿电凭证核发声明，未匹配部分计普通用电。",
        "pains": ["一张凭证拆给多家，并发核发时凭证与线体当月电量都容易超领", "凭证撤销生效后旧声明口径混乱，简报该扣多少说不清", "换证补发与重试重复占量，同一失效份额被核发两次"],
        "upstream": "每日线体抄表与绿电凭证签发文件", "downstream": "客户月度绿电核验简报与留档声明。",
        "entities": ["用电日记录", "绿电凭证", "核发声明", "月度核验简报"],
        "dataset_name": "三家客户_2026年9-10月_线体日耗.csv",
        "columns": [{"key": "day", "label": "日期", "type": "string"}, {"key": "line", "label": "线体编码", "type": "string"}, {"key": "kwh", "label": "实测日电耗", "type": "number"}],
        "usage_columns": [{"key": "day", "label": "日期"}, {"key": "line", "label": "线体"}, {"key": "kwh", "label": "实测日电耗 kWh"}],
        "claim_columns": [{"key": "id", "label": "编号"}, {"key": "cert_no", "label": "凭证号"}, {"key": "line_code", "label": "线体"}, {"key": "month", "label": "归属月"}, {"key": "kwh", "label": "电量 kWh"}, {"key": "kind", "label": "类型"}, {"key": "status", "label": "状态"}, {"key": "created_at", "label": "提交时间"}],
        "verification_columns": [{"key": "line_code", "label": "线体"}, {"key": "usage_kwh", "label": "实测用电 kWh"}, {"key": "green_kwh", "label": "绿电 kWh"}, {"key": "regular_kwh", "label": "普通用电 kWh"}, {"key": "reserved_kwh", "label": "核发中 kWh"}, {"key": "invalidated_kwh", "label": "失效扣减 kWh"}],
        "method": "核发声明只在同月凭证与同月线体实测电量内占用份额：凭证 reserved+issued≤总量，线体当月 reserved+issued≤实测。凭证撤销生效后停止核发，在途声明取消、已核发份额失效；简报只扣失效份额。换证补发金额恒等于失效份额，同一失效份额最多一个在途补发。",
        "limitations": ["绿电占比为台账口径核验，不构成电网物理溯源证明。", "撤销以生效日 00:00 为界，生效前已核发的份额在生效时统一失效。", "补发只覆盖失效份额，不补偿撤销后新产生的用电缺口。"],
        "seed_story": ["08:10 导入三家客户 9–10 月线体日耗。", "08:30 登记当月绿电凭证，一张凭证拆给多家客户。", "09:00 提交核发声明，后台按队列核发，占用同月凭证与线体份额。", "10:20 凭证 B002 撤销生效：在途声明取消，已核发份额失效留档。", "11:00 为失效份额换证补发，重试不会重复占量。", "14:00 生成客户月度核验简报，只扣失效份额。"],
        "accent": "oklch(49% 0.11 155)", "style": "ledger-sheet",
    }


def seed_usage_records():
    """固定随机种子的三家客户 2026-09/2026-10 逐日线体电耗。"""
    rng = random.Random(20261120)
    rows = []
    for _, _, lines in LINES:
        for offset, (code, _) in enumerate(lines):
            base = 3600 + offset * 520 + rng.uniform(-160, 160)
            for month in SEED_MONTHS:
                year, mon = int(month[:4]), int(month[5:])
                for d in range(1, calendar.monthrange(year, mon)[1] + 1):
                    day = date(year, mon, d)
                    weekly = 0.82 if day.weekday() >= 5 else 1.0
                    kwh = round(base * weekly * (1 + 0.08 * math.sin(d / 6.1)) + rng.gauss(0, 90), 1)
                    rows.append({"day": day.isoformat(), "line": code, "kwh": max(kwh, 400.0)})
    return rows
