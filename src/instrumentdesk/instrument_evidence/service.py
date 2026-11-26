from dataclasses import replace
from hashlib import sha256
import json
from math import fsum, isfinite, sqrt
from statistics import median

from .measurement_bands import evaluate_shift
from .contracts import PreparedRuns, FeatureState, FeatureVector, FEATURE_KEYS, RAW_KEYS


def spread(samples):
    origin = fsum(samples) / len(samples)
    residuals = tuple(value - origin for value in samples)
    variance = fsum(value * value for value in residuals) / len(residuals)
    sigma = sqrt(variance)
    return origin, sigma if sigma > 1e-9 else 1.0


def derive(values):
    wear_grade, repair_count, setup_age, photos, price_index, play_log = values
    wear_repairs = wear_grade+.7*repair_count
    setup_lag = setup_age/(1+play_log)
    photo_attestation = photos/(1+wear_grade)
    pricing_gap = abs(price_index-100)
    repair_risk = repair_count*price_index/100
    return wear_repairs, setup_lag, photo_attestation, pricing_gap, repair_risk


def fit_features(training):
    rows = sorted(training,key=lambda row:(row.day,row.key))
    if not rows:
        raise ValueError('拟合段没有测量值')
    filled = []
    for key in RAW_KEYS:
        evidence = tuple(getattr(obs,key) for obs in rows if getattr(obs,key) is not None)
        if not evidence:
            raise ValueError(f'训练字段 {key} 未见有效值')
        filled.append(median(evidence))
    axes = tuple(zip(*(derive(measurement(row,filled)[0]) for row in rows),strict=True))
    centres, scales = zip(*(spread(axis) for axis in axes),strict=True)
    revision = (FEATURE_KEYS,filled,axes,[record.signature() for record in rows])
    return FeatureState(tuple(filled),centres,scales,tuple(map(min,axes)),tuple(map(max,axes)),
                        sha256(json.dumps(revision,ensure_ascii=False).encode()).hexdigest()[:16])


def measurement(row, fills):
    source = [getattr(row,field) for field in RAW_KEYS]
    absent = tuple(key for key, value in zip(RAW_KEYS,source) if value is None)
    values = tuple(patch if value is None else value for value,patch in zip(source,fills,strict=True))
    return values, absent


def numeric_fields(raw, fitted):
    entries = derive(raw)
    selected = []
    outliers = []
    for slot,(key,base,scale,low,high) in enumerate(zip(FEATURE_KEYS,fitted.offsets,fitted.scales,fitted.floor,fitted.ceil,strict=True)):
        value = entries[slot]
        adjusted = (value-base)/scale
        if not isfinite(adjusted):
            raise ValueError(f'{key} 的标准值无效')
        selected.append(adjusted)
        if not low-.75*scale <= value <= high+.75*scale:
            outliers.append(key)
    return tuple(selected), entries, tuple(outliers)


def transform(row, reference):
    raw, missed = measurement(row,reference.fill)
    scaled, factors, outside = numeric_fields(raw,reference)
    return FeatureVector(row.key,row.cohort,row.day,scaled,factors,missed,outside,row.outcome,row.observed,raw)


def transform_all(observations, reference):
    return tuple(transform(row,reference) for row in observations)


def transform_windows(windows, reference):
    return PreparedRuns(*(transform_all(records, reference) for _, records in windows.partitions()))


def feature_evidence(reference):
    return [{'特征': name,'中心':round(center,3),'尺度':round(scale,3),'训练最小':round(low,3),'训练最大':round(high,3)}
            for name,center,scale,low,high in zip(FEATURE_KEYS,reference.offsets,reference.scales,reference.floor,reference.ceil,strict=True)]


def render_interventions(vector, reference, score):
    from .interventions import propose_authentication_window

    records = []
    estimate = score(vector)
    for adjustment in propose_authentication_window(vector.input_values, vector.missing):
        position=RAW_KEYS.index(adjustment.field)
        modified=tuple(adjustment.after if position==slot else part for slot,part in enumerate(vector.input_values))
        values, factors, flags = numeric_fields(modified,reference)
        alternative=replace(vector,values=values,factors=factors,input_values=modified,excursions=flags)
        revised=score(alternative)
        records.append({**adjustment.evidence(),'原预测':round(estimate,4),'替换预测':round(revised,4),
                        '预测变化':round(revised-estimate,4),'超训练域':bool(flags)})
    return records


def business_factors(vector):
    from .interventions import measure_instrument_evidence

    return measure_instrument_evidence(vector.input_values).explain()


def measure_review(features):
    return evaluate_shift(features.train, features.live)


def render_joint_experiments(vector, reference, score):
    from .joint import options

    raw = vector.input_values
    base = score(vector)
    replies=[]
    for action in options(raw,vector.missing):
        adjusted = tuple(action.changes[key][1] if key in action.changes else value for key,value in zip(RAW_KEYS,raw,strict=True))
        normalized, measured, signals=numeric_fields(adjusted,reference)
        scenario=replace(vector,values=normalized,input_values=adjusted,factors=measured,excursions=signals)
        replies.append(action.evidence(base,score(scenario),signals))
    return replies
