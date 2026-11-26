from collections import Counter
from dataclasses import replace

from .contracts import Chronology, FoldSummary, Span, WindowRule
from .readiness import formation_tail
from ..instrument_registry import body_of


def assign_fold(record, rule):
    day=record.day
    if day in rule.live and rule.as_of>=max(day,record.received):
        return 'live','OPEN_RUN'
    fold_names = ('train','calibration','replay')
    placements = {name:getattr(rule,name) for name in fold_names}
    for stage in fold_names:
        edge=placements[stage]
        if not (edge.begin<=day<edge.end):
            continue
        came=record.received
        seen=record.result_day
        landed_after=seen is None or came>=edge.end or seen>=edge.end
        if landed_after:
            return None,'RESULT_NOT_MATURE'
        if not (record.observed or rule.allow_censor):
            return None,'CENSORED_OUTCOME'
        audit_complete = record.outcome is not None and seen>=record.day
        return (stage,'LOCKED_HISTORY') if audit_complete else (None,'MISSING_OUTCOME')
    return None,'EMBARGO_OR_UNSCHEDULED'


def build_windows(records, rule=None):
    schedule=rule or WindowRule.standard(allow_censor=False)
    book=tuple(sorted(records,key=lambda row:(row.day,row.key)))
    observed=tuple((item,*assign_fold(item,schedule)) for item in book)
    # 防样本泄漏：训练段见过的琴身编号，其跨店重挂单必须退出校准与回放。
    trained_bodies={body_of(item) for item,stage,_ in observed
                    if stage=='train' and body_of(item)}
    screened=[]
    leakage=[]
    for item,stage,reason in observed:
        body=body_of(item)
        if stage in ('calibration','replay') and body and body in trained_bodies:
            leakage.append((item.key,body,stage))
            screened.append((item,None,'BODY_SEEN_IN_TRAIN'))
        else:
            screened.append((item,stage,reason))
    findings = {stage:tuple(item for item,label,_ in screened if stage==label) for stage in ('train','calibration','replay','live')}
    isolated=tuple(sorted((ticket.key,reason) for ticket,stage,reason in screened if stage is None))
    document=Chronology(**findings,excluded=isolated,leakage=tuple(sorted(leakage)))
    document.check_conservation(len(book))
    return document


def partition_summary(windows):
    statistics=[]
    for label, tickets in windows.partitions():
        count=len(tickets)
        locations={entry.cohort for entry in tickets}
        unresolved=sum(entry.observed is False for entry in tickets)
        dates=tuple(entry.day for entry in tickets)
        statistics.append(FoldSummary(label,count,len(locations),unresolved,min(dates,default=None),max(dates,default=None)))
    return tuple(statistics)


def window_evidence(windows):
    short={'train':'拟合','calibration':'校准','replay':'回放','live':'当班'}
    view=[{'时段':short[row.name], '单量':row.count, '作业组':row.cohort_count, '右截尾':row.censored, '有效起点':row.first_day,'有效末日':row.last_day}
          for row in partition_summary(windows)]
    view.extend({'样本隔离':code,'单量':amount} for code,amount in Counter(reason for _,reason in windows.excluded).items())
    return view


def model_inputs(windows):
    history=windows.train
    if len(history)<16:
        raise ValueError('寄售验收至少需要 16 张成熟历史单据')
    minimum={'calibration':3,'replay':1,'live':1}
    for field,value in windows.partitions():
        if field in minimum and len(value)<minimum[field]:
            raise ValueError(f'寄售验收的 {field} 窗内单据不足 {minimum[field]} 条')
    return tuple(item.key for item in history)


def readiness_evidence(windows, as_of=96):
    report=formation_tail(windows, replace(WindowRule.standard(), as_of=as_of))
    return sorted(report,key=lambda entry:(entry['交班段'],-entry['有效单'],entry['来源']))
