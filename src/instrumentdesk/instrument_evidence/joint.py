from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_evidence_pair(readings, invalid):
    photos, play_log = readings[3], readings[5]
    if invalid.intersection(('photos', 'play_log')):
        return None
    if not (play_log<=43 and photos<=25):
        return None
    play_log_adjusted = play_log+10
    photos_adjusted = photos+6
    inspected = {
        'play_log': (play_log, play_log_adjusted),
        'photos': (photos, photos_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('试奏与外观证据齐备', 2, '同验收师登记视频与磨损照', inspected)
    return None


def simulate_check_tune_and_price(readings, invalid):
    setup_age, price_index = readings[2], readings[4]
    if invalid.intersection(('setup_age', 'price_index')):
        return None
    if not (setup_age>=40 and price_index>=119):
        return None
    setup_age_adjusted = 1
    price_index_adjusted = price_index-12
    inspected = {
        'setup_age': (setup_age, setup_age_adjusted),
        'price_index': (price_index, price_index_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('新校准平抑挂价', 3, '重新试奏后复核同类行情', inspected)
    return None


def simulate_validate_repairs(readings, invalid):
    repair_count, photos = readings[1], readings[3]
    if invalid.intersection(('repair_count', 'photos')):
        return None
    if not (repair_count>=3 and photos<=25):
        return None
    repair_count_adjusted = repair_count-2
    photos_adjusted = photos+7
    inspected = {
        'repair_count': (repair_count, repair_count_adjusted),
        'photos': (photos, photos_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('追回维修单补拍', 2, '清理重复维修并核对配件序号', inspected)
    return None


def simulate_condition_rehearsal(readings, invalid):
    wear_grade, play_log = readings[0], readings[5]
    if invalid.intersection(('wear_grade', 'play_log')):
        return None
    if not (wear_grade>=4 and play_log<=40):
        return None
    wear_grade_adjusted = wear_grade-2
    play_log_adjusted = play_log+12
    inspected = {
        'wear_grade': (wear_grade, wear_grade_adjusted),
        'play_log': (play_log, play_log_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('修复磨痕延长试奏', 3, '交回前核对修复后磨损和音色', inspected)
    return None


def simulate_market_check(readings, invalid):
    photos, price_index = readings[3], readings[4]
    if invalid.intersection(('photos', 'price_index')):
        return None
    if not (abs(price_index-100)>=18 and photos<=24):
        return None
    price_index_adjusted = round((price_index+100)/2)
    photos_adjusted = photos+6
    inspected = {
        'price_index': (price_index, price_index_adjusted),
        'photos': (photos, photos_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('对照行情留档', 2, '同时固定比价截图和品相档', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_evidence_pair(measurements, unobserved),
        simulate_check_tune_and_price(measurements, unobserved),
        simulate_validate_repairs(measurements, unobserved),
        simulate_condition_rehearsal(measurements, unobserved),
        simulate_market_check(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)
