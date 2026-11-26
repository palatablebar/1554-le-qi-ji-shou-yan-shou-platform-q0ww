from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def shop_mix_domains(vectors):
    inspection_density = []
    freshness_days = []
    repair_photos = []
    price_over = []
    sound_evidence = []
    condition_attention = []
    reference_lower = []
    moisture_age_proxy = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        wear_grade, repair_count, setup_age, photos, price_index, play_log = measurement.input_values
        if unobserved.isdisjoint(('wear_grade', 'photos')):
            inspection_density.append((round(photos/wear_grade, 4), wear_grade>=7))
        if unobserved.isdisjoint(('repair_count', 'setup_age')):
            freshness_days.append((round(setup_age, 4), repair_count>=4))
        if unobserved.isdisjoint(('repair_count', 'photos')):
            repair_photos.append((round(photos/max(1,repair_count), 4), photos<=8))
        if unobserved.isdisjoint(('setup_age', 'price_index')):
            price_over.append((round(max(0,price_index-100), 4), setup_age>=160))
        if unobserved.isdisjoint(('repair_count', 'price_index', 'play_log')):
            sound_evidence.append((round(play_log/(1+repair_count), 4), abs(price_index-100)>=24))
        if unobserved.isdisjoint(('wear_grade', 'repair_count')):
            condition_attention.append((round(wear_grade*(1+repair_count/8), 4), wear_grade>=7))
        if unobserved.isdisjoint(('repair_count', 'price_index')):
            reference_lower.append((round(max(0,100-price_index), 4), repair_count>=4))
        if unobserved.isdisjoint(('wear_grade', 'setup_age', 'photos')):
            moisture_age_proxy.append((round(setup_age*wear_grade/50, 4), photos<=8))
    return {
        '每磨损档照片 · 高磨损件': tuple(inspection_density),
        '离试奏前校准日期 · 多次维修': tuple(freshness_days),
        '每次维修的影像 · 少细节照片': tuple(repair_photos),
        '挂牌超出行情点 · 久未校准': tuple(price_over),
        '每次维修试奏覆盖 · 报价偏离行情': tuple(sound_evidence),
        '磨损维修叠加 · 高磨损件': tuple(condition_attention),
        '低于行情点 · 多次维修': tuple(reference_lower),
        '校准与磨损叠加暴露 · 少细节照片': tuple(moisture_age_proxy),
    }


def evaluate_domains(training, current):
    references = shop_mix_domains(training)
    activity = shop_mix_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)
