from collections import defaultdict
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class ConditionSheet:
    technician_minutes: float
    photos_due: int
    note: str
    discount_ceiling: float
    risk_band: str


def bench_check(trade):
    record = trade['measurements']
    adjustment = record['setup_age']>=160
    repair = int(record['repair_count'])
    wear = record['wear_grade']
    recorded = record['play_log']
    photos_gap = max(0,ceil(4+wear*1.1+(2 if repair else 0)-record['photos']))
    desired_play = 14 + 5*adjustment + min(12,repair * 2)
    bench_time = max(0, desired_play-recorded) + photos_gap*.6
    if wear >= 7 and photos_gap:
        report = '磨损位全景、局部和背光三拍'
    elif adjustment and recorded < 12:
        report = '先复做校准并补长音录音'
    elif repair>=4 and record['price_index']>=128:
        report = '核验维修履历与挂牌价'
    else:
        report = '试奏回访留档'
    risk = '复查' if trade['estimate']>=.50 else '常规'
    ceiling = max(0,record['price_index'] - 100) *.3 + wear*.7 + repair
    return ConditionSheet(bench_time,photos_gap,report,round(min(32,ceiling),1),risk)


def operating_ledger(rows):
    console = []
    bays = defaultdict(list)
    for trade in rows:
        if trade['unmeasured']:
            console.append({'业务安排':'待店员填写琴况和试奏凭证','关联单据':trade['key'],'可签收寄售':False})
            continue
        evidence = bench_check(trade)
        bays[trade['zone']].append((trade,evidence))
    for shop, selections in sorted(bays.items()):
        elapsed = 0
        photo_count = 0
        for trade,evidence in sorted(selections,key=lambda group:(group[1].risk_band!='复查',-group[1].technician_minutes,group[0]['key'])):
            earmarked = trade['state']=='已分派' and evidence.technician_minutes>0
            start = elapsed if earmarked else None
            if earmarked:
                elapsed += ceil(evidence.technician_minutes)
                photo_count += evidence.photos_due
            if evidence.technician_minutes or trade['state']=='暂停':
                console.append({'业务安排':evidence.note,'关联单据':trade['key'],'寄卖点':shop,'上琴台分钟':start,
                                '拟复验分钟':round(evidence.technician_minutes,1),'补照张数':evidence.photos_due,
                                '可讨论下调上限百分点':evidence.discount_ceiling,'复查标记':evidence.risk_band})
        console.append({'业务安排':'验收琴台当班对账','寄卖点':shop,'已排琴台分钟':elapsed,
                        '记录需补照片':photo_count,'涉及寄售件数':len(selections)})
    return console
