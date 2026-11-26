"""跨店重挂琴的二验签发规则。

覆盖：最新挂牌接单、同日冲突转人工、补照暂停与七张实拍解除、
一琴一单、无编号沿用原单、训练琴退出校准/回放、换序一致、按琴查询。
"""

import copy

from instrumentdesk.pipeline import execute, open_fixture
from instrumentdesk.consignment_notes.service import read_assay
from instrumentdesk.return_observation.service import build_windows
from instrumentdesk.instrument_registry import resolve_body


def listing(key, received, **over):
    base = {'key': key, 'body_number': 'B1', 'cohort': '甲店', 'day': received,
            'received': received, 'revision': 1,
            'wear_grade': 3, 'repair_count': 1, 'setup_age': 60,
            'photos': 12, 'price_index': 100, 'play_log': 20}
    base.update(over)
    return base


def test_latest_arrival_before_cutoff_is_accepted():
    decision = resolve_body('B1', [listing('OLD', 80), listing('NEW', 95)], as_of=96)
    assert decision.accepted_key == 'NEW'
    assert 'LATEST_LISTING_ACCEPTED' in decision.basis


def test_late_arrival_after_cutoff_is_not_accepted():
    decision = resolve_body('B1', [listing('OLD', 80), listing('LATE', 99)], as_of=96)
    # 99 日到站的单不具资格，截止前的 OLD 成为最新可接挂牌。
    assert decision.accepted_key == 'OLD'


def test_same_day_conflicting_latest_goes_manual():
    a = listing('A', 95, wear_grade=6.0)
    b = listing('B', 95, wear_grade=6.5)
    forward = resolve_body('B1', [a, b], as_of=96)
    backward = resolve_body('B1', [b, a], as_of=96)
    assert forward.status == backward.status == 'conflict'
    assert forward.destination == '人工判读'
    assert set(forward.contender_keys) == {'A', 'B'}
    assert forward.public() == backward.public()


def test_same_day_identical_readings_are_not_conflict():
    decision = resolve_body('B1', [listing('A', 95), listing('B', 95)], as_of=96)
    assert decision.status == 'ready'
    assert decision.accepted_key == 'A'  # 确定性 tie-break


def test_photo_hold_only_releases_at_seven_actual_photos():
    old = listing('OLD', 80, wear_grade=9, photos=3)
    for photos in (None, 4, 5, 6):
        decision = resolve_body('B1', [old, listing('NEW', 95, photos=photos)], as_of=96)
        assert decision.status == 'photo_hold'
        assert decision.destination == '暂停'
        assert decision.signed_key is None
    for photos in (7, 8, 12):
        decision = resolve_body('B1', [old, listing('NEW', 95, photos=photos)], as_of=96)
        assert decision.status == 'ready'
        assert decision.hold_released is True
        assert 'PHOTO_HOLD_RELEASED' in decision.basis


def _fixture_with_body_scenarios():
    records = copy.deepcopy(open_fixture()['records'])
    # IN-1258 是样例中唯一的 MISSING_DETAIL 暂停单。
    for row in records:
        if row['key'] == 'IN-1258':
            row['body_number'] = 'HOLD-BODY'
    old = next(row for row in records if row['key'] == 'IN-1258')

    def new_ticket(key, photos):
        ticket = copy.deepcopy(old)
        ticket.update({'key': key, 'day': 95, 'received': 95, 'revision': 1,
                       'result_day': None, 'outcome': None,
                       'wear_grade': 3, 'photos': photos})
        return ticket

    return records, new_ticket


def test_pipeline_blocks_new_listing_until_seven_photos():
    records, new_ticket = _fixture_with_body_scenarios()
    for photos in (5, 6):
        batch = records + [new_ticket('IN-NEW-LOW', photos)]
        batch[-1]['body_number'] = 'HOLD-BODY'
        report = execute(batch, 12, 'balanced', as_of=96)
        row = next(r for r in report['rows'] if r['key'] == 'IN-NEW-LOW')
        assert row['state'] == '暂停' and row['reason'] == 'MISSING_DETAIL'
        card = report['instrument_index']['HOLD-BODY']
        assert card['signed_key'] is None and card['photo_hold'] is True


def test_pipeline_releases_old_hold_at_seven_photos():
    records, new_ticket = _fixture_with_body_scenarios()
    fresh = new_ticket('IN-NEW-OK', 7)
    fresh['body_number'] = 'HOLD-BODY'
    report = execute(records + [fresh], 12, 'balanced', as_of=96)
    old_row = next(r for r in report['rows'] if r['key'] == 'IN-1258')
    new_row = next(r for r in report['rows'] if r['key'] == 'IN-NEW-OK')
    assert not (old_row['state'] == '暂停' and old_row['reason'] == 'MISSING_DETAIL')
    assert new_row['reason'] != 'MISSING_DETAIL'
    card = report['instrument_index']['HOLD-BODY']
    assert card['hold_released'] is True


def test_one_signing_per_body_and_reorder_invariant():
    fixture = open_fixture()['records']

    def clone(key, received, body):
        row = copy.deepcopy(next(r for r in fixture if r['key'] == 'IN-1253'))
        row.update({'key': key, 'body_number': body, 'received': received,
                    'day': received, 'result_day': None, 'outcome': None})
        return row

    batch = fixture + [clone('IN-DUP-A', 94, 'DUP-BODY'), clone('IN-DUP-B', 95, 'DUP-BODY')]
    first = execute(batch, 12, 'balanced', as_of=96)
    second = execute(list(reversed(batch)), 12, 'balanced', as_of=96)
    assert first['rows'] == second['rows']
    assert first['instruments'] == second['instruments']
    assert first['run_id'] == second['run_id']
    body_rows = [r for r in first['rows'] if r['body_number'] == 'DUP-BODY']
    signed = [r for r in body_rows if r['state'] == '已分派']
    assert len(signed) == 1
    card = first['instrument_index']['DUP-BODY']
    assert card['signed_key'] == signed[0]['key']
    assert len(first['signings']) == len({c['body_number'] for c in first['signings']})


def test_same_day_conflict_through_pipeline_goes_manual():
    fixture = open_fixture()['records']

    def clone(key, wear):
        row = copy.deepcopy(next(r for r in fixture if r['key'] == 'IN-1253'))
        row.update({'key': key, 'body_number': 'CF-BODY', 'received': 95, 'day': 95,
                    'wear_grade': wear, 'result_day': None, 'outcome': None})
        return row

    report = execute(fixture + [clone('IN-C1', 6.0), clone('IN-C2', 6.4)], 12, as_of=96)
    for key in ('IN-C1', 'IN-C2'):
        row = next(r for r in report['rows'] if r['key'] == key)
        assert row['state'] == '人工判读' and row['reason'] == 'SAME_DAY_LISTING_CONFLICT'


def test_no_body_number_keeps_original_tickets():
    records = copy.deepcopy(open_fixture()['records'])
    for row in records:
        row.pop('body_number', None)
    report = execute(records, 12, 'balanced', as_of=96)
    assert report['body_count'] == 0
    assert all(row['body_number'] is None for row in report['rows'])
    assert all(row['signed'] == (row['state'] == '已分派') for row in report['rows'])


def test_training_seen_body_leaves_calibration_and_replay(observation):
    train = read_assay({**observation, 'body_number': 'LEAK-1'})
    calib = read_assay({**observation, 'key': 'CAL-1', 'body_number': 'LEAK-1',
                        'day': 43, 'received': 43, 'result_day': 48})
    replay = read_assay({**observation, 'key': 'REP-1', 'body_number': 'LEAK-1',
                         'day': 66, 'received': 66, 'result_day': 70})
    windows = build_windows((train, calib, replay))
    assert all(row.key != 'CAL-1' for row in windows.calibration)
    assert all(row.key != 'REP-1' for row in windows.replay)
    reasons = dict(windows.excluded)
    assert reasons.get('CAL-1') == 'BODY_SEEN_IN_TRAIN'
    assert reasons.get('REP-1') == 'BODY_SEEN_IN_TRAIN'
    assert {body for _, body, fold in windows.leakage} == {'LEAK-1'}


def test_body_aliases_are_recognized(observation):
    for field in ('serial_number', '琴身编号', 'body_no', 'instrument_id'):
        row = read_assay({**observation, field: ' ALIAS-1 '})
        assert row.body_number == 'ALIAS-1'


def test_page_and_routes_expose_instrument_lookup():
    from instrumentdesk.entry import app
    client = app.test_client()
    page = client.get('/').get_data(as_text=True)
    assert '按琴查询' in page and 'instrument-filter' in page
    assert client.get('/api/instrumentdesk/instruments').status_code == 200
    miss = client.get('/api/instrumentdesk/instrument/NO-SUCH-BODY').get_json()
    assert miss['found'] is False
    # 自备批次经 POST /run 后，琴身去向与依据随结果返回，可供页面按琴查询。
    fixture = open_fixture()['records']
    row = copy.deepcopy(next(r for r in fixture if r['key'] == 'IN-1253'))
    row.update({'key': 'IN-WEB-1', 'body_number': 'WEB-BODY', 'received': 95, 'day': 95,
                'result_day': None, 'outcome': None})
    response = client.post('/api/instrumentdesk/run',
                           json={'records': fixture + [row], 'as_of': 96, 'capacity': 12})
    assert response.status_code == 200
    payload = response.get_json()
    card = payload['instrument_index']['WEB-BODY']
    assert card['去向'] and card['依据'] and 'LATEST_LISTING_ACCEPTED' in card['basis_codes']
