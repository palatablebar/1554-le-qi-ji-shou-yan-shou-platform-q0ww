from collections import Counter
from hashlib import blake2s
from math import isfinite

from .contracts import MODEL_NAME, Fit, Prediction
from .baseline import baseline_review
from .diagnostics import explain_return_prior_claim
from .beta_model import fit_kernel, score_kernel


def fit_model(history, feature_stamp):
    ordered = sorted(history,key=lambda sample:(sample.day,sample.key))
    if not feature_stamp or len(ordered)<8:
        raise ValueError('风险拟合需要八条记录和特征版本')
    accepted = {}
    cohorts = Counter()
    digest = blake2s(feature_stamp.encode(),digest_size=8)
    for sample in ordered:
        if not sample.observed or sample.outcome not in (0,1):
            raise ValueError('风险拟合需要已确认的二元实绩')
        if not sample.values or not all(map(isfinite,sample.values)):
            raise ValueError('风险特征必须有限')
        if sample.key in accepted:
            raise ValueError('风险实绩表单号重复')
        accepted[sample.key] = sample
        cohorts[sample.cohort] += 1
        identity = (sample.key,sample.day,sample.cohort,sample.values,sample.outcome)
        digest.update(repr(identity).encode())
        digest.update(b'\n')
    kernel, stats = fit_kernel(tuple(accepted.values()))
    positive = sum(row.outcome for row in ordered)
    return Fit(MODEL_NAME,feature_stamp,digest.hexdigest(),kernel,
               (*stats,('确认阳性数',positive),('基线阳性率',positive/len(ordered)),('训练作业组',len(cohorts))))


def predict_one(fit, sample):
    probability, deltas = score_kernel(fit.parameters,sample)
    if not 0<=probability<=1 or not all(map(isfinite,deltas)):
        raise ArithmeticError('概率或局部解释幅度超界')
    return Prediction(sample.key,sample.cohort,sample.day,probability,tuple(deltas),sample.missing,
                      sample.excursions,sample.outcome,sample.observed,sample.input_values)


def predict(fit, observations, feature_stamp):
    if feature_stamp != fit.feature:
        raise ValueError('风险校验需要相同特征版本')
    checked = map(lambda sample:predict_one(fit,sample),observations)
    return tuple(checked)


def compare_batches(fit, groups, feature_stamp):
    separate = tuple(prediction for group in groups for prediction in predict(fit, group, feature_stamp))
    return separate == predict(fit, (row for group in groups for row in group), feature_stamp)


def inspection_rows(fit, sections):
    """Return model-specific evidence for the current run without retraining."""
    return (explain_return_prior_claim(fit, sections.calibration, sections.replay, sections.live)
            + baseline_review(fit, sections.train, sections.replay))
