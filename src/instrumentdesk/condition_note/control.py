from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    signed_bodies = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        body = row.get('body_number') or row.get('琴身编号')
        if state == '已分派':
            total += row['cost']
            # 同一琴身编号只签发一单二验；无编号单不参与琴身去重。
            if body:
                if body in signed_bodies:
                    raise ArithmeticError('同一琴身编号只能签发一单二验')
                signed_bodies.add(body)
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_condition_note(measurements, estimate):
    wear_grade = measurements['wear_grade']
    repair_count = measurements['repair_count']
    setup_age = measurements['setup_age']
    photos = measurements['photos']
    price_index = measurements['price_index']
    play_log = measurements['play_log']
    return {
        '每磨损档照片': round(photos/wear_grade, 3),
        '每次维修的影像': round(photos/max(1,repair_count), 3),
        '低于行情点': round(max(0,100-price_index), 3),
        '校准与磨损叠加暴露': round(setup_age*wear_grade/50, 3),
        '复核代价指标': round(wear_grade/9 + repair_count/10 + max(0,12-play_log)/15, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_condition_note(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register
