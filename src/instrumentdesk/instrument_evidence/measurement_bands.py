from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_inspection_density(vector):
    wear_grade = vector.input_values[0]
    photos = vector.input_values[3]
    return float(photos/wear_grade)


def compare_inspection_density(training, target):
    usual_inspection_density = take_sample(training, current_inspection_density)
    recent_inspection_density = take_sample(target, current_inspection_density)
    if len(usual_inspection_density) < 4 or not recent_inspection_density:
        return {'作业量': '每磨损档照片', '有效读数': len(recent_inspection_density), '判断': '参考不足'}
    anchor_inspection_density = median(usual_inspection_density)
    measured_inspection_density = median(recent_inspection_density)
    ordered_inspection_density = sorted(usual_inspection_density)
    low_inspection_density, high_inspection_density = ordered_inspection_density[len(ordered_inspection_density)//10], ordered_inspection_density[(len(ordered_inspection_density)*9)//10]
    change_inspection_density = measured_inspection_density-anchor_inspection_density
    outside_inspection_density = sum(value<low_inspection_density or value>high_inspection_density for value in recent_inspection_density)
    return {'作业量': '每磨损档照片', '训练参考': round(anchor_inspection_density, 4), '现场中位': round(measured_inspection_density, 4),
            '变动': round(change_inspection_density, 4), '越界量': outside_inspection_density, '有效读数': len(recent_inspection_density)}


def current_freshness_days(vector):
    setup_age = vector.input_values[2]
    return float(setup_age)


def compare_freshness_days(training, target):
    usual_freshness_days = take_sample(training, current_freshness_days)
    recent_freshness_days = take_sample(target, current_freshness_days)
    if len(usual_freshness_days) < 4 or not recent_freshness_days:
        return {'作业量': '离试奏前校准日期', '有效读数': len(recent_freshness_days), '判断': '参考不足'}
    anchor_freshness_days = median(usual_freshness_days)
    measured_freshness_days = median(recent_freshness_days)
    band_freshness_days = max(1.0, abs(anchor_freshness_days)*.2, median(abs(value-anchor_freshness_days) for value in usual_freshness_days))
    change_freshness_days = (measured_freshness_days-anchor_freshness_days) / band_freshness_days
    outside_freshness_days = sum(abs(value-anchor_freshness_days)>2.5*band_freshness_days for value in recent_freshness_days)
    return {'作业量': '离试奏前校准日期', '训练参考': round(anchor_freshness_days, 4), '现场中位': round(measured_freshness_days, 4),
            '变动': round(change_freshness_days, 4), '越界量': outside_freshness_days, '有效读数': len(recent_freshness_days)}


def current_repair_photos(vector):
    repair_count = vector.input_values[1]
    photos = vector.input_values[3]
    return float(photos/max(1,repair_count))


def compare_repair_photos(training, target):
    usual_repair_photos = take_sample(training, current_repair_photos)
    recent_repair_photos = take_sample(target, current_repair_photos)
    if len(usual_repair_photos) < 4 or not recent_repair_photos:
        return {'作业量': '每次维修的影像', '有效读数': len(recent_repair_photos), '判断': '参考不足'}
    anchor_repair_photos = median(usual_repair_photos)
    measured_repair_photos = median(recent_repair_photos)
    band_repair_photos = max(1.0, abs(anchor_repair_photos)*.2, median(abs(value-anchor_repair_photos) for value in usual_repair_photos))
    change_repair_photos = (measured_repair_photos-anchor_repair_photos) / band_repair_photos
    outside_repair_photos = sum(abs(value-anchor_repair_photos)>2.5*band_repair_photos for value in recent_repair_photos)
    return {'作业量': '每次维修的影像', '训练参考': round(anchor_repair_photos, 4), '现场中位': round(measured_repair_photos, 4),
            '变动': round(change_repair_photos, 4), '越界量': outside_repair_photos, '有效读数': len(recent_repair_photos)}


def current_price_over(vector):
    price_index = vector.input_values[4]
    return float(max(0,price_index-100))


def compare_price_over(training, target):
    usual_price_over = take_sample(training, current_price_over)
    recent_price_over = take_sample(target, current_price_over)
    if len(usual_price_over) < 4 or not recent_price_over:
        return {'作业量': '挂牌超出行情点', '有效读数': len(recent_price_over), '判断': '参考不足'}
    anchor_price_over = median(usual_price_over)
    measured_price_over = median(recent_price_over)
    ordered_price_over = sorted(usual_price_over)
    low_price_over, high_price_over = ordered_price_over[len(ordered_price_over)//10], ordered_price_over[(len(ordered_price_over)*9)//10]
    change_price_over = measured_price_over-anchor_price_over
    outside_price_over = sum(value<low_price_over or value>high_price_over for value in recent_price_over)
    return {'作业量': '挂牌超出行情点', '训练参考': round(anchor_price_over, 4), '现场中位': round(measured_price_over, 4),
            '变动': round(change_price_over, 4), '越界量': outside_price_over, '有效读数': len(recent_price_over)}


def current_sound_evidence(vector):
    repair_count = vector.input_values[1]
    play_log = vector.input_values[5]
    return float(play_log/(1+repair_count))


def compare_sound_evidence(training, target):
    usual_sound_evidence = take_sample(training, current_sound_evidence)
    recent_sound_evidence = take_sample(target, current_sound_evidence)
    if len(usual_sound_evidence) < 4 or not recent_sound_evidence:
        return {'作业量': '每次维修试奏覆盖', '有效读数': len(recent_sound_evidence), '判断': '参考不足'}
    anchor_sound_evidence = median(usual_sound_evidence)
    measured_sound_evidence = median(recent_sound_evidence)
    ordered_sound_evidence = sorted(usual_sound_evidence)
    low_sound_evidence, high_sound_evidence = ordered_sound_evidence[len(ordered_sound_evidence)//10], ordered_sound_evidence[(len(ordered_sound_evidence)*9)//10]
    change_sound_evidence = measured_sound_evidence-anchor_sound_evidence
    outside_sound_evidence = sum(value<low_sound_evidence or value>high_sound_evidence for value in recent_sound_evidence)
    return {'作业量': '每次维修试奏覆盖', '训练参考': round(anchor_sound_evidence, 4), '现场中位': round(measured_sound_evidence, 4),
            '变动': round(change_sound_evidence, 4), '越界量': outside_sound_evidence, '有效读数': len(recent_sound_evidence)}


def current_condition_attention(vector):
    wear_grade = vector.input_values[0]
    repair_count = vector.input_values[1]
    return float(wear_grade*(1+repair_count/8))


def compare_condition_attention(training, target):
    usual_condition_attention = take_sample(training, current_condition_attention)
    recent_condition_attention = take_sample(target, current_condition_attention)
    if len(usual_condition_attention) < 4 or not recent_condition_attention:
        return {'作业量': '磨损维修叠加', '有效读数': len(recent_condition_attention), '判断': '参考不足'}
    anchor_condition_attention = median(usual_condition_attention)
    measured_condition_attention = median(recent_condition_attention)
    ordered_condition_attention = sorted(usual_condition_attention)
    low_condition_attention, high_condition_attention = ordered_condition_attention[len(ordered_condition_attention)//10], ordered_condition_attention[(len(ordered_condition_attention)*9)//10]
    change_condition_attention = measured_condition_attention-anchor_condition_attention
    outside_condition_attention = sum(value<low_condition_attention or value>high_condition_attention for value in recent_condition_attention)
    return {'作业量': '磨损维修叠加', '训练参考': round(anchor_condition_attention, 4), '现场中位': round(measured_condition_attention, 4),
            '变动': round(change_condition_attention, 4), '越界量': outside_condition_attention, '有效读数': len(recent_condition_attention)}


def current_reference_lower(vector):
    price_index = vector.input_values[4]
    return float(max(0,100-price_index))


def compare_reference_lower(training, target):
    usual_reference_lower = take_sample(training, current_reference_lower)
    recent_reference_lower = take_sample(target, current_reference_lower)
    if len(usual_reference_lower) < 4 or not recent_reference_lower:
        return {'作业量': '低于行情点', '有效读数': len(recent_reference_lower), '判断': '参考不足'}
    anchor_reference_lower = median(usual_reference_lower)
    measured_reference_lower = median(recent_reference_lower)
    ordered_reference_lower = sorted(usual_reference_lower)
    low_reference_lower, high_reference_lower = ordered_reference_lower[len(ordered_reference_lower)//10], ordered_reference_lower[(len(ordered_reference_lower)*9)//10]
    change_reference_lower = measured_reference_lower-anchor_reference_lower
    outside_reference_lower = sum(value<low_reference_lower or value>high_reference_lower for value in recent_reference_lower)
    return {'作业量': '低于行情点', '训练参考': round(anchor_reference_lower, 4), '现场中位': round(measured_reference_lower, 4),
            '变动': round(change_reference_lower, 4), '越界量': outside_reference_lower, '有效读数': len(recent_reference_lower)}


def current_moisture_age_proxy(vector):
    wear_grade = vector.input_values[0]
    setup_age = vector.input_values[2]
    return float(setup_age*wear_grade/50)


def compare_moisture_age_proxy(training, target):
    usual_moisture_age_proxy = take_sample(training, current_moisture_age_proxy)
    recent_moisture_age_proxy = take_sample(target, current_moisture_age_proxy)
    if len(usual_moisture_age_proxy) < 4 or not recent_moisture_age_proxy:
        return {'作业量': '校准与磨损叠加暴露', '有效读数': len(recent_moisture_age_proxy), '判断': '参考不足'}
    anchor_moisture_age_proxy = median(usual_moisture_age_proxy)
    measured_moisture_age_proxy = median(recent_moisture_age_proxy)
    band_moisture_age_proxy = max(1.0, abs(anchor_moisture_age_proxy)*.2, median(abs(value-anchor_moisture_age_proxy) for value in usual_moisture_age_proxy))
    change_moisture_age_proxy = (measured_moisture_age_proxy-anchor_moisture_age_proxy) / band_moisture_age_proxy
    outside_moisture_age_proxy = sum(abs(value-anchor_moisture_age_proxy)>2.5*band_moisture_age_proxy for value in recent_moisture_age_proxy)
    return {'作业量': '校准与磨损叠加暴露', '训练参考': round(anchor_moisture_age_proxy, 4), '现场中位': round(measured_moisture_age_proxy, 4),
            '变动': round(change_moisture_age_proxy, 4), '越界量': outside_moisture_age_proxy, '有效读数': len(recent_moisture_age_proxy)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_instrument_evidence_band(history, daybook):
    yield compare_inspection_density(history, daybook)
    yield compare_freshness_days(history, daybook)
    yield compare_repair_photos(history, daybook)
    yield compare_price_over(history, daybook)
    yield compare_sound_evidence(history, daybook)
    yield compare_condition_attention(history, daybook)
    yield compare_reference_lower(history, daybook)
    yield compare_moisture_age_proxy(history, daybook)


def evaluate_shift(training, current):
    return list(measure_instrument_evidence_band(training, current))
