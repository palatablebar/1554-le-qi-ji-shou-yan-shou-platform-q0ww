from dataclasses import replace
from statistics import median

from .contracts import InstrumentEvidence, Proposal


def measure_instrument_evidence(values) -> InstrumentEvidence:
    wear_grade, repair_count, setup_age, photos, price_index, play_log = values
    return InstrumentEvidence(
        inspection_density=photos/wear_grade,
        freshness_days=setup_age,
        repair_photos=photos/max(1,repair_count),
        price_over=max(0,price_index-100),
        sound_evidence=play_log/(1+repair_count),
        condition_attention=wear_grade*(1+repair_count/8),
        reference_lower=max(0,100-price_index),
        moisture_age_proxy=setup_age*wear_grade/50,
    )


def propose_authentication_window(values, missing=()):
    wear_grade, repair_count, setup_age, photos, price_index, play_log = values
    if 'photos' not in missing and (photos<=26):
        yield Proposal('补拍六张细节照片', 'photos', photos, min(32,photos+6), 1)
    if 'play_log' not in missing and (play_log<=45):
        yield Proposal('现场延长十分钟试奏', 'play_log', play_log, min(55,play_log+10), 2)
    if 'setup_age' not in missing and (setup_age>=38):
        yield Proposal('重新校准留档', 'setup_age', setup_age, 1, 3)
    if 'price_index' not in missing and (abs(price_index-100)>=14):
        yield Proposal('挂牌价向行情回调', 'price_index', price_index, round((price_index+100)/2), 1)
