from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .beta_model import score_kernel



def explain_return_prior_claim(fit, calibration, replay, live):
    medians, baseline, pooled, branches = fit.parameters
    by_shop = {}
    for (name,evidence),(returned, inspected) in branches:
        by_shop.setdefault(name,[]).append((evidence,returned,inspected))
    result = []
    for shop, records in by_shop.items():
        for trace, returned, inspected in records:
            global_rate = dict(pooled).get(trace,baseline)
            local_rate = (returned+7*global_rate)/(inspected+7)
            trace_name = ' / '.join(label for label, flag in zip(('高磨损','旧校准','留档齐'),trace,strict=True) if flag) or '常规'
            result.append({'寄售门店':shop,'品相证据':trace_name,'有效验收':inspected,'已退回':int(returned),
                           '全店基准':round(global_rate,4),'门店收缩':round(local_rate,4)})
    return sorted(result,key=lambda item: (-item['门店收缩'],item['寄售门店']))[:16]
