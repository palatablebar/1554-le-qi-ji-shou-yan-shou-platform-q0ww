def collect_wear_evidence(measures, missing, estimate):
    wear_grade = measures['wear_grade']
    photos = measures['photos']
    if not (wear_grade>=6 or photos<=9):
        return None
    value=photos/wear_grade
    return {'现场复核':'验证细节图片','可复查值':round(value,3),'单位':'张/分','归档要求':'复拍指板或面板主要磨损',
            '需补测':not set(missing).isdisjoint(('wear_grade', 'photos'))}


def collect_repair_trace(measures, missing, estimate):
    repair_count = measures['repair_count']
    if not (repair_count>=3):
        return None
    value=repair_count
    return {'现场复核':'查看维修凭证','可复查值':round(value,3),'单位':'次','归档要求':'核对配件序号和维修店单据',
            '需补测':not set(missing).isdisjoint(('repair_count',))}


def collect_play_record(measures, missing, estimate):
    setup_age = measures['setup_age']
    play_log = measures['play_log']
    if not (play_log<=18 or setup_age>=150):
        return None
    value=play_log
    return {'现场复核':'重新试奏','可复查值':round(value,3),'单位':'分钟','归档要求':'保存同日调试与试听记录',
            '需补测':not set(missing).isdisjoint(('setup_age', 'play_log'))}


def collect_market_quote(measures, missing, estimate):
    price_index = measures['price_index']
    if not (abs(price_index-100)>=19):
        return None
    value=price_index
    return {'现场复核':'挂牌复核','可复查值':round(value,3),'单位':'%','归档要求':'对照近期同条件成交',
            '需补测':not set(missing).isdisjoint(('price_index',))}


def check_condition_note(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_wear_evidence(measures,absent,estimate),
            collect_repair_trace(measures,absent,estimate),
            collect_play_record(measures,absent,estimate),
            collect_market_quote(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide
