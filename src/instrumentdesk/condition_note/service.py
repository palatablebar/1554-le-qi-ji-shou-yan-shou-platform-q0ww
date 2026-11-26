from .work_order import check_condition_note as site_checklist
from collections import Counter
from dataclasses import astuple
from hashlib import sha256
from json import dumps
from struct import pack

from .control import accountable_plan, document_control
from .contracts import BatchReceipt, LedgerCheck, POLICY_VERSION


def evidence_bytes(value):
    return dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def stable_digest(items):
    digest=sha256()
    for value in items:
        duration=evidence_bytes(value)
        digest.update(pack('>I',len(duration)))
        digest.update(duration)
    return digest.hexdigest()


def data_fingerprint(records):
    encoded = (evidence_bytes(record).decode('utf-8') for record in records)
    return stable_digest(sorted(encoded))


def policy_fingerprint(capacity,mode,feature_id,model_kind):
    return stable_digest((capacity,mode,model_kind,POLICY_VERSION,feature_id))[:16]


def check_flow(intake, windows, dispatched):
    decisions=tuple(dispatched.jobs)
    source=tuple(windows.live)
    if sorted(item.key for item in decisions) != sorted(item.key for item in source):
        raise ArithmeticError('原单与决定无法一一配对')
    by_group=Counter()
    disposition=Counter()
    for row in decisions:
        disposition[row.state]+=1
        if row.state=='已分派':
            by_group[row.cohort]+=row.cost
    if dict(by_group) != dict(dispatched.used_by_group):
        raise ArithmeticError('按作业区分配的额度未平')
    sources={unit.key for unit in intake.entries}
    treated=[item.key for _,slice_ in windows.partitions() for item in slice_]
    treated.extend(ref for ref,_ in windows.excluded)
    if len(treated)!=len(sources) or set(treated)!=sources or len(sources)+len(intake.issues)!=intake.source_rows:
        raise ArithmeticError('版次保留、分窗及隔离无法对账')
    return LedgerCheck(raw=intake.source_rows,isolated=len(intake.issues),mature_excluded=len(windows.excluded),
                       scored=len(decisions),capacity=dispatched.capacity,resource_used=by_group.total(),
                       balance=dispatched.balance,states=tuple(sorted(disposition.items())))


def close_batch(dataset,intake,windows,dispatched,feature_id,model_kind,mode):
    counts=check_flow(intake,windows,dispatched)
    upload=data_fingerprint(dataset)
    settings=policy_fingerprint(dispatched.capacity,mode,feature_id,model_kind)
    decisions=tuple((job.key,job.state,job.cost,job.reason,job.estimate) for job in dispatched.jobs)
    checksum=stable_digest((upload,settings,astuple(counts),*decisions))[:16]
    return BatchReceipt(checksum,upload,settings,counts,decisions)


def compare(before, after):
    old = {row[0]: row[1:] for row in before.decisions}
    current = {row[0]: row[1:] for row in after.decisions}
    new = current.keys() - old.keys()
    obsolete = old.keys() - current.keys()
    changed = {key for key in old.keys() & current.keys() if old[key] != current[key]}
    return {'新增': tuple(sorted(new)), '移出': tuple(sorted(obsolete)), '变更': tuple(sorted(changed)),
            '策略变化': before.policy_hash != after.policy_hash, '样本变化': before.batch_hash != after.batch_hash}


def reconciliation_evidence(receipt):
    ledger = receipt.totals
    rows = [{'核对项': '原始记录', '数量': ledger.raw}, {'核对项': '入站隔离', '数量': ledger.isolated},
            {'核对项': '窗口隔离', '数量': ledger.mature_excluded}, {'核对项': '当班对象', '数量': ledger.scored},
            {'核对项': '已用额度', '数量': ledger.resource_used}, {'核对项': '额度结余', '数量': ledger.balance}]
    rows.extend({'核对项': state, '数量': count} for state, count in ledger.states)
    return rows


def sign_field_evidence(rows, allocation):
    counts, spent = accountable_plan(rows, allocation.balance, allocation.capacity)
    if dict(counts) != dict(Counter(job.state for job in allocation.jobs)):
        raise ArithmeticError('展示单据和签发方案的处置统计不符')
    selected = {row['key']: row['cost'] for row in rows if row['state'] == '已分派'}
    original = {job.key: job.cost for job in allocation.jobs if job.state == '已分派'}
    if selected != original:
        raise ArithmeticError('分派凭证与作业单互相矛盾')
    return {'工位使用':spent, '执行业务单':document_control(rows)}


def intervention_summary(rows):
    actions = {}
    for record in rows:
        for sample in record['alternatives']:
            label = sample['情形']
            observed = actions.setdefault(label,[0,0,0,0])
            observed[0] += 1
            observed[1] += bool(sample['超训练域'])
            observed[2] += sample['用量']
            observed[3] += sample['预测变化']
    return [{'单项安排': key, '可比较单量': attempts, '超出拟合域': outlier,
             '总用量': units, '平均预测变化': round(delta/attempts,4)}
            for key,(attempts,outlier,units,delta) in sorted(actions.items())]
