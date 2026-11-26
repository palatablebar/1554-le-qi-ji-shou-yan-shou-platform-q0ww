from collections import defaultdict
from statistics import median


def cell(value, boundary):
    return int(value >= boundary)


def beta_mean(success, count, first, second):
    return (success + first) / (count + first + second)


def fit_kernel(rows):
    thresholds = tuple(median(column) for column in zip(*(row.values for row in rows), strict=True))
    prevalence = beta_mean(sum(row.outcome for row in rows), len(rows), 1, 1)
    prior_success, prior_failure = 7 * prevalence, 7 * (1 - prevalence)
    shop_register = defaultdict(lambda:[0, 0])
    global_register = defaultdict(lambda:[0, 0])
    for instrument in rows:
        wear = cell(instrument.values[0], thresholds[0])
        recency = cell(instrument.values[1], thresholds[1])
        photos = cell(instrument.values[2], thresholds[2])
        key = wear, recency, photos
        for batch in (shop_register[instrument.cohort, key], global_register[key]):
            batch[0] += instrument.outcome
            batch[1] += 1
    branch = tuple((key, tuple(value)) for key, value in sorted(shop_register.items()))
    pooled = tuple((key, beta_mean(success,total,prior_success,prior_failure))
                   for key, (success,total) in sorted(global_register.items()))
    return (thresholds, prevalence, pooled, branch), (('店铺验收组', len(branch)), ('全量既往退货率', prevalence))


def score_kernel(priors, sample):
    thresholds, prevalence, pooled, branch = priors
    evidence = tuple(cell(value, anchor) for value, anchor in zip(sample.values[:3], thresholds[:3], strict=True))
    default = dict(pooled).get(evidence, prevalence)
    returned, claims = dict(branch).get((sample.cohort, evidence), (0,0))
    reliability = beta_mean(returned, claims, 7 * default, 7 * (1 - default))
    return reliability, (default - prevalence, reliability - default, claims)
