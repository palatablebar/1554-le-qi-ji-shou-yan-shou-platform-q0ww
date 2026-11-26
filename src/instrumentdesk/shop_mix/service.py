from collections import Counter
from math import fsum
from statistics import median

from .contracts import ShiftReport, ReferenceProfile
from .operating_reference import evaluate_domains


def l1_distance(first, second):
    return fsum(abs(x-y) for x,y in zip(first,second,strict=True))


def fit_baseline(features, signature):
    if not features:
        raise ValueError('邻域基线缺少有效单据')
    domain = tuple(sorted((row.key,row.values) for row in features))
    distances = [min((l1_distance(query,other) for other_id,other in domain if other_id!=tag), default=0.)
                 for tag, query in domain]
    ordered = sorted(distances)
    boundary = max(.75,1.4*ordered[(len(ordered)-1)*9//10])
    local = Counter(point.cohort for point in features)
    return ReferenceProfile(signature, (tuple(value for _,value in domain),boundary), tuple(local),len(features))


def scan_current(reference, points, signature):
    if signature!=reference.signature:
        raise ValueError('邻近样本版本已撤销，需重建')
    if not points:
        return ShiftReport(0,(),(),(),'NO_CURRENT_RECORDS')
    archive, cutoff = reference.bands
    unrecognized = {row.cohort for row in points}.difference(reference.cohorts)
    distances = {row.key:min(l1_distance(vector,row.values) for vector in archive) for row in points}
    manual = {item.key for item in points if len(item.excursions)>=2 or len(item.missing)>=2 or item.cohort in unrecognized}
    rare = [item.key for item in points if distances[item.key]>cutoff]
    manual.update(rare)
    count = len(points)
    flags = (('邻域外占比',len(rare)/count),('最近邻距中值',median(distances.values())),('历史距离界',cutoff))
    return ShiftReport(count,flags,tuple(sorted(unrecognized)),tuple(sorted(manual)),
                       'SHIFT_REVIEW' if any(rare) or unrecognized else 'STABLE')



def coverage_by_group(calibration, validation):
    past = Counter(item.cohort for item in calibration)
    current = Counter(item.cohort for item in validation)
    return tuple((key,past[key],current[key]) for key in sorted(past.keys()|current.keys()))


def shift_evidence(current, coverage):
    names = dict(zip(('wear_repairs', 'setup_lag', 'photo_attestation', 'pricing_gap', 'repair_risk'),('磨损和历史维修', '试奏修正的校准时差', '细节证据密度', '挂牌价偏差', '溢价时的维修负担'),strict=True))
    new = set(current.novel)
    table = [{'检测项':names.get(field,field), '训练邻域距离':round(evidence,4)} for field,evidence in current.signals]
    table.extend({'检测项':unit, '校准单数':old,'本班单数':seen,'现场': '未登记' if unit in new else '已登记'}
                 for unit,old,seen in coverage)
    return table


def shop_floor_shift(reference, current):
    measures = evaluate_domains(reference,current)
    return sorted(measures,key=lambda line:(-line['越线量'],line['观察维度']))
