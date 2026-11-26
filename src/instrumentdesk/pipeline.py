from dataclasses import replace
import json
from pathlib import Path

from .consignment_notes import service as intake_service
from .return_observation import service as cohort_service
from .instrument_evidence import service as feature_service
from .return_prior_claim import service as model_service
from .consignment_eval import service as calibration_service
from .shop_mix import service as monitor_service
from .authentication_window import service as dispatch_service
from .condition_note import service as audit_service
from .instrument_registry import BodyLedger, training_body_numbers
from .return_observation import contracts as window_contract

PRESET = Path(__file__).resolve().parents[2] / 'sample_data' / 'consignment_notes_sample.json'
MODULES = (('consignment_notes', '寄售登记'),
 ('return_observation', '退货观察'),
 ('instrument_evidence', '验收证据'),
 ('return_prior_claim', '退货先验'),
 ('consignment_eval', '寄售回放'),
 ('shop_mix', '门店分组'),
 ('authentication_window', '二次验收'),
 ('condition_note', '品相签记'))
DISPLAY = {'title': '乐器寄售验收台',
 'object_name': '寄售单',
 'unit': '概率',
 'role': '二手琴行验收专员',
 'endpoint': 'instrumentdesk',
 'identity': 'CONSIGNMENT',
 'location': '寄售组 · 非标乐器',
 'visual': '退货风险与留档',
 'queue': '待复核寄售单',
 'resource': '试奏验收工位',
 'action': '安排二次验收',
 'lane': 'L14',
 'field_title': '琴台二验排单'}


def open_fixture(path=PRESET):
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or not isinstance(document.get('records'), list):
        raise ValueError('样例必须包含 records 数组')
    if len(document['records']) > 2500:
        raise ValueError('单次导入最多处理 2500 条单据')
    return document


def stage_at(index, details, records, issues=()):
    code, title = MODULES[index]
    return {'key': code, 'title': title, 'summary': details, 'records': list(records), 'errors': list(issues)}


def rows_for(plan, scored, vectors):
    by_key = {item.key: item for item in scored}
    factor_names = ('磨损和历史维修', '试奏修正的校准时差', '细节证据密度', '挂牌价偏差', '溢价时的维修负担')
    order = []
    for job in plan.jobs:
        point = by_key[job.key]
        if len(point.contributions) == len(factor_names):
            reasons = sorted(zip(factor_names, point.contributions, strict=True), key=lambda val: (-abs(val[1]), val[0]))
            driver = ' · '.join(f'{key} {amount:+.2f}' for key, amount in reasons[:2])
        else:
            driver = ' · '.join(f'{amount:+.2f}' for amount in point.contributions)
        interval = ('–' if job.lower is None else f'{job.lower:.2f}–{job.upper:.2f}')
        order.append({'key': job.key, 'zone': job.cohort, 'estimate': job.estimate, 'interval': interval,
                      'state': job.state, 'cost': job.cost, 'reason': job.reason, 'evidence': job.summary,
                      'drivers': driver, 'missing': len(point.missing), 'hits': list(job.rule_hits),
                      'measurements': dict(zip(('wear_grade', 'repair_count', 'setup_age', 'photos', 'price_index', 'play_log'), point.input_values, strict=True)),
                      'unmeasured': list(point.missing), 'operations': feature_service.business_factors(vectors[job.key])})
    return order


def comparison_rows(predictions):
    return [{'单号': point.key, '分组': point.cohort, '原始估计': round(point.score, 4),
             '补值字段': len(point.missing), '偏离特征': '、'.join(point.excursions) or '—'}
            for point in predictions[:14]]


def replay_metrics(report):
    result = [{'label': '回放实绩样本', 'value': report.count}, {'label': '回放绝对误差', 'value': report.mae}]
    return result


def execute(documents, capacity=12, mode='balanced', *, as_of=96):
    if type(as_of) is not int or not 91 <= as_of <= 3650:
        raise ValueError('截止日须为第 91 日至第 3650 日之间的整数')
    if not isinstance(documents, (list, tuple)) or not 1 <= len(documents) <= 2500:
        raise ValueError('单据批次须包含 1 到 2500 条记录')
    intake = intake_service.load_samples(documents, as_of)
    window_rule = replace(window_contract.WindowRule.standard(allow_censor=False), as_of=as_of)
    windows = cohort_service.build_windows(intake.entries, window_rule)
    cohort_service.model_inputs(windows)
    trained_bodies = training_body_numbers(windows)
    active_keys = frozenset(row.key for row in windows.live)
    body_ledger = BodyLedger.from_records(intake.entries, as_of=as_of,
                                          training_bodies=trained_bodies, active_keys=active_keys)
    state = feature_service.fit_features(windows.train)
    features = feature_service.transform_windows(windows, state)
    kernel = model_service.fit_model(features.train, state.fingerprint)
    scored = model_service.predict(kernel, features.live, state.fingerprint)
    retrospective = model_service.predict(kernel, features.replay, state.fingerprint)
    calibration = model_service.predict(kernel, features.calibration, state.fingerprint)
    fitted_calibration = calibration_service.prepare_verification(calibration)
    evaluated = calibration_service.validate_predictions(retrospective, fitted_calibration)
    performance = calibration_service.performance(evaluated)
    checked_live = calibration_service.validate_predictions(scored, fitted_calibration)
    baseline = monitor_service.fit_baseline(features.train, state.fingerprint)
    drift = monitor_service.scan_current(baseline, features.live, state.fingerprint)
    coverage = monitor_service.coverage_by_group(features.calibration, features.live)
    allocation = dispatch_service.plan_jobs(checked_live, drift.domain, capacity, mode, body_ledger)
    closed = audit_service.close_batch(documents, intake, windows, allocation, state.fingerprint, kernel.name, mode)
    states = dict(closed.totals.states)
    overview = [
        {'label': '当班寄售单', 'value': len(allocation.jobs)},
        {'label': '已分派', 'value': states.get('已分派', 0)},
        {'label': '候补', 'value': states.get('候补', 0)},
        {'label': '暂停及人工判读', 'value': states.get('暂停', 0) + states.get('人工判读', 0)},
        {'label': '额度结余', 'value': allocation.balance},
    ]
    vectors = {item.key: item for item in features.live}
    row_list = rows_for(allocation, scored, vectors)
    jobs_by_key = {job.key: job for job in allocation.jobs}
    instrument_cards = body_ledger.index(jobs_by_key)
    cards_by_body = {card['body_number']: card for card in instrument_cards}
    for row in row_list:
        body = body_ledger.body_for_key(row['key'])
        row['body_number'] = body
        for alias_key in ('琴身编号', 'serial_number', 'serial_no', 'body_no',
                          'instrument_id', 'instrument_no', 'serial'):
            row[alias_key] = body
        if body is not None and body in cards_by_body:
            card = cards_by_body[body]
            row['signed'] = row['已签发'] = row['state'] == '已分派' and card.get('signed_key') == row['key']
            row['instrument_destination'] = card['destination']
            row['去向'] = card['去向']
            row['instrument_basis'] = card['basis']
            row['依据'] = card['依据']
        else:
            row['signed'] = row['已签发'] = row['state'] == '已分派'
            row['instrument_destination'] = row['state']
            row['去向'] = row['state']
            row['instrument_basis'] = ['无琴身编号，沿用原寄售单']
            row['依据'] = ['无琴身编号，沿用原寄售单']
    operating_rows = dispatch_service.operating_ledger(row_list)
    leakage_rows = [{'单号': key, '琴身编号': body, '退出环节': '校准' if fold == 'calibration' else '回放',
                     '原因': 'BODY_SEEN_IN_TRAIN',
                     '说明': '训练拟合见过该琴，退出校准与回放以防样本泄漏'}
                    for key, body, fold in windows.leakage]
    signings = [card for card in instrument_cards if card['signed']]
    overtime = calibration_service.boundary_diagnostics(evaluated, 0.5)
    sector = calibration_service.sector_replay(evaluated, 0.5)
    operating_shift = monitor_service.shop_floor_shift(features.train, features.live)
    field_evidence = audit_service.sign_field_evidence(row_list, allocation)
    features_glance = feature_service.feature_evidence(state) + feature_service.measure_review(features)
    weight_rows = [{'量测': key, '取值': value} for key, value in kernel.evidence]
    ignored = [issue.evidence() for issue in intake.issues]
    details = [
        stage_at(0, f'接收 {intake.source_rows} 条，采用 {len(intake.entries)} 条', intake_service.preliminary_evidence(intake), ignored),
        stage_at(1, f'拟合 {len(windows.train)} 条，校准 {len(windows.calibration)} 条，回放 {len(windows.replay)} 条', cohort_service.window_evidence(windows) + cohort_service.readiness_evidence(windows, as_of) + leakage_rows),
        stage_at(2, '特征转换版本 ' + state.fingerprint, features_glance),
        stage_at(3, kernel.name, weight_rows + model_service.inspection_rows(kernel, features) + comparison_rows(scored)),
        stage_at(4, f'{fitted_calibration.method} · {performance.status} · {performance.count} 条回放实绩', calibration_service.calibration_evidence(performance) + [overtime] + sector),
        stage_at(5, f'{drift.status} · {len(drift.domain)} 张单据需外推判读', monitor_service.shift_evidence(drift, coverage) + operating_shift),
        stage_at(6, f'本班占用 {allocation.capacity-allocation.balance} / {allocation.capacity} 个工位单位', dispatch_service.action_evidence(allocation) + dispatch_service.operating_group(checked_live, allocation)),
        stage_at(7, f'处置凭证 {closed.stamp} · 额度守恒', audit_service.reconciliation_evidence(closed) + field_evidence['执行业务单']),
    ]
    details[6]['operating_rows'] = operating_rows
    details[6]['operating_title'] = '琴台二验排单'
    points = [{'label': row['key'], 'value': row['estimate'], 'state': row['state'], 'zone': row['zone'],
               'upper': row['interval'], 'cost': row['cost']} for row in sorted(row_list, key=lambda row: row['key'])]
    def estimate(vector):
        return calibration_service.check_point(model_service.predict_one(kernel, vector), fitted_calibration).estimate

    # Compare interventions against frozen features, model and calibration;
    # scenario estimates never overwrite the base ticket or its decision.
    for row in row_list:
        current = vectors[row['key']]
        row['alternatives'] = feature_service.render_interventions(current, state, estimate)
        row['joint_experiments'] = feature_service.render_joint_experiments(current,state,estimate)
    details[7]['records'].extend(audit_service.site_checklist(row_list))
    details[7]['records'].extend(audit_service.intervention_summary(row_list))
    overview_report = {'capacity' : capacity, 'mode': mode, 'as_of': as_of, 'sample_hash': closed.batch_hash,
              'policy_hash': closed.policy_hash, 'feature_stamp': state.fingerprint,
              'model': kernel.name, 'run_id': closed.stamp, 'object_name': DISPLAY['object_name'],
              'unit': DISPLAY['unit'], 'sections': details, 'flow_counts': list(states.items()),
              'measures': {'wear_grade': ('外观磨损分', '分'),
 'repair_count': ('历史维修次数', '次'),
 'setup_age': ('距上次校准', '天'),
 'photos': ('有效细节照片', '张'),
 'price_index': ('挂牌价与行情比', '%'),
 'play_log': ('试奏留档时长', 'min')}, 'metrics': overview, 'performance': replay_metrics(performance), 'rows': row_list, 'series': points,
              'instruments': instrument_cards,
              'instrument_index': {card['body_number']: card for card in instrument_cards},
              'signings': signings,
              'leakage_excluded': leakage_rows,
              'body_count': len(instrument_cards),
              'signed_count': len(signings)}
    # 兼容不同调用方对“跨店重挂 / 琴身追踪”命名的接口预期。
    overview_report['body_index'] = overview_report['instrument_index']
    overview_report['bodies'] = instrument_cards
    overview_report['relistings'] = overview_report['instruments']
    overview_report['instrument_trace'] = overview_report['instruments']
    overview_report['whereabouts'] = overview_report['instruments']
    overview_report['签发清册'] = signings
    overview_report['按琴查询'] = overview_report['instrument_index']
    return overview_report


def preview(capacity=12, mode='balanced'):
    fixture = open_fixture()
    return execute(fixture['records'], capacity, mode, as_of=fixture['as_of'])
