from instrumentdesk.pipeline import preview
from instrumentdesk.authentication_window.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('wear_grade', 'repair_count', 'setup_age', 'photos', 'price_index', 'play_log'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '琴台二验排单'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_waiting_trade_gives_photo_request_without_booked_bench_time():
    incoming = note('IN-1',(9,5,235,3,134,3),state='候补',estimate=.74)
    action, desk = operating_ledger([incoming])
    assert action['业务安排']=='磨损位全景、局部和背光三拍'
    assert action['上琴台分钟'] is None and action['补照张数']>0
    assert desk['已排琴台分钟']==0
