"""按琴身编号裁决跨店重挂、补照暂停与二验签发。

本模块不依赖 Flask / 模型，输入可以是：

* :class:`~instrumentdesk.consignment_notes.contracts.InstrumentdeskRecord`
* 导入用的原始 ``dict``（兼容多种琴身编号字段名）
* 流水线产出的行 ``dict``（读数嵌在 ``measurements`` 中）

所有聚合都排序后输出，换序输入得到逐字段相同的结论。
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace

from .contracts import BASIS_TEXT, PHOTO_RELEASE_THRESHOLD, InstrumentDecision, Listing

BODY_ALIASES = ('body_number', 'body_no', 'body_id', 'body_code', 'body_sn', 'body',
                'serial_number', 'serial_no', 'serial_id', 'serial_code', 'serial',
                'instrument_number', 'instrument_no', 'instrument_id', 'instrument_code',
                'instrument_sn', 'instrument_serial', 'instrument_serial_number',
                'shell_number', 'shell_no', 'piano_number', 'piano_no', 'piano_sn',
                'qin_number', 'qin_no', 'qin_id', 'qin_sn', 'sn',
                '琴身编号', '琴编号', '琴号', '机身编号', '序列编号', '序列号')

MEASURE_FIELDS = ('wear_grade', 'repair_count', 'setup_age', 'photos', 'price_index', 'play_log')


def _scalar_body(source):
    for name in BODY_ALIASES:
        value = source.get(name)
        if isinstance(value, Mapping):
            continue
        if value not in (None, ''):
            if isinstance(value, bool):
                return str(value)
            return str(value).strip() or None
    return None


def body_of(source):
    """从任意单据表示中取出琴身编号（找不到返回 ``None``）。"""
    if source is None:
        return None
    if not isinstance(source, Mapping):
        value = getattr(source, 'body_number', None)
        if value not in (None, ''):
            return str(value).strip() or None
        for name in BODY_ALIASES:
            value = getattr(source, name, None)
            if value not in (None, ''):
                return str(value).strip() or None
        return None
    value = _scalar_body(source)
    if value:
        return value
    measurements = source.get('measurements')
    if isinstance(measurements, Mapping):
        value = _scalar_body(measurements)
        if value:
            return value
    for group in ('instrument_identity', 'identity', 'instrument', '琴', '琴身'):
        nested = source.get(group)
        if isinstance(nested, Mapping):
            value = _scalar_body(nested)
            if value:
                return value
    return None


def _number(source, name):
    if isinstance(source, Mapping):
        value = source.get(name)
    else:
        value = getattr(source, name, None)
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def listing_from(record):
    """把一种单据表示归一为 :class:`Listing`。"""
    if isinstance(record, Listing):
        return record
    body = body_of(record)
    measurements = record.get('measurements') if isinstance(record, Mapping) else None

    def read(name):
        if isinstance(measurements, Mapping) and measurements.get(name) not in (None, ''):
            return _number(measurements, name)
        return _number(record, name)

    def attr(name, default=None):
        if isinstance(record, Mapping):
            return record.get(name, default)
        return getattr(record, name, default)

    key = attr('key')
    return Listing(
        key=str(key),
        body_number=body,
        cohort=str(attr('cohort', '') or ''),
        day=int(_number(record, 'day') or 0),
        received=int(_number(record, 'received') if _number(record, 'received') is not None else (read('day') or 0)),
        revision=int(_number(record, 'revision') or 1),
        photos=read('photos'),
        wear_grade=read('wear_grade'),
        repair_count=read('repair_count'),
        setup_age=read('setup_age'),
        price_index=read('price_index'),
        play_log=read('play_log'),
    )


def hits_missing_detail(listing):
    """与验收硬规则 MISSING_DETAIL 同口径，但只认真实读数，不认补值。"""
    return (listing.wear_grade is not None and listing.photos is not None
            and listing.wear_grade >= 7 and listing.photos <= 6)


def _winner_key(front):
    # 确定性 tie-break：工日、版次更新者优先，仍并列则单号字典序最小。
    ordered = sorted(front, key=lambda item: (-item.day, -item.revision, item.key))
    return ordered[0].key


def resolve_body(body, listings, *, as_of=96, photo_target=PHOTO_RELEASE_THRESHOLD,
                 training_bodies=frozenset(), active_keys=None):
    """裁决同一琴身编号下的全部挂牌。

    ``active_keys`` 给出当前班次仍在流转的单号；只有这些单的“补照”状态能
    延续到新挂牌。``None`` 表示把全部传入挂牌都视为在途（便于独立调用）。
    """
    listings = tuple(item if isinstance(item, Listing) else listing_from(item) for item in listings)
    keys = tuple(sorted(item.key for item in listings))
    eligible = [item for item in listings if item.received <= as_of]
    basis = []
    training_seen = body in frozenset(training_bodies)
    if training_seen:
        basis.append('BODY_SEEN_IN_TRAIN')

    if not eligible:
        return InstrumentDecision(body, 'after_cutoff', '人工判读', '到站晚于截止日，转人工核对',
                                  listing_keys=keys, basis=tuple(basis + ['AFTER_CUTOFF']),
                                  training_seen=training_seen)

    latest_day = max(item.received for item in eligible)
    front = [item for item in eligible if item.received == latest_day]
    distinct_readings = {item.measurement_signature() for item in front}

    if len(front) > 1 and len(distinct_readings) > 1:
        contenders = tuple(sorted(item.key for item in front))
        return InstrumentDecision(
            body, 'conflict', '人工判读', '同日最新挂牌冲突，转人工判读',
            contender_keys=contenders, listing_keys=keys,
            basis=tuple(basis + ['SAME_DAY_LISTING_CONFLICT', 'BODY_SINGLE_SIGNING']),
            conflict=True, training_seen=training_seen)

    winner_key = _winner_key(front)
    winner = next(item for item in listings if item.key == winner_key)
    older = [item for item in eligible if item.key != winner_key]

    def on_desk(item):
        return active_keys is None or item.key in active_keys

    old_hold_keys = tuple(sorted(item.key for item in older
                                 if on_desk(item) and hits_missing_detail(item)))
    own_hold = on_desk(winner) and hits_missing_detail(winner)
    hold_required = bool(old_hold_keys or own_hold)
    actual_photos = winner.photos
    released = actual_photos is not None and actual_photos >= photo_target

    basis.append('LATEST_LISTING_ACCEPTED')
    basis.append('NEW_SHOP_MEASUREMENT')
    if old_hold_keys:
        basis.append('INHERITED_PHOTO_HOLD')
    if hold_required and not released:
        basis.append('PHOTO_HOLD_WAIT_NEW')
        basis.append('MISSING_DETAIL')
        return InstrumentDecision(
            body, 'photo_hold', '暂停', '新单实拍未满七张，补照暂停不解除',
            accepted_key=winner_key, contender_keys=(winner_key,), listing_keys=keys,
            basis=tuple(dict.fromkeys(basis)), photo_hold=True, hold_released=False,
            training_seen=training_seen, risk_source_key=winner_key,
            cohort=winner.cohort or None,
            extra={'hold_keys': list(old_hold_keys), 'actual_photos': actual_photos,
                   'photo_target': photo_target})

    if hold_required and released:
        basis.append('PHOTO_HOLD_RELEASED')
    basis.append('BODY_SINGLE_SIGNING')
    return InstrumentDecision(
        body, 'ready', '观察', '最新挂牌可进入二验派单',
        accepted_key=winner_key, contender_keys=(winner_key,), listing_keys=keys,
        basis=tuple(dict.fromkeys(basis)), photo_hold=hold_required, hold_released=released,
        training_seen=training_seen, risk_source_key=winner_key,
        cohort=winner.cohort or None,
        extra={'hold_keys': list(old_hold_keys), 'actual_photos': actual_photos,
               'photo_target': photo_target})


def build_registry(records, *, as_of=96, photo_target=PHOTO_RELEASE_THRESHOLD,
                   training_bodies=frozenset(), active_keys=None):
    """把一批单据按琴身编号分组并裁决；无编号单据各自成 ``solo`` 案。

    返回 ``(decisions_by_body, solo_by_key, body_of_key)``。
    """
    grouped = defaultdict(list)
    solo = {}
    body_of_key = {}
    for raw in records:
        listing = listing_from(raw)
        if listing.key is None or listing.key == 'None':
            continue
        if listing.body_number:
            grouped[listing.body_number].append(listing)
            body_of_key[listing.key] = listing.body_number
        else:
            solo[listing.key] = InstrumentDecision(
                None, 'solo', '观察', '无琴身编号，沿用原寄售单',
                accepted_key=listing.key, listing_keys=(listing.key,),
                basis=('NO_BODY_USE_ORIGINAL',), risk_source_key=listing.key,
                cohort=listing.cohort or None)

    decisions = {}
    for body in sorted(grouped):
        decisions[body] = resolve_body(body, grouped[body], as_of=as_of,
                                       photo_target=photo_target,
                                       training_bodies=training_bodies,
                                       active_keys=active_keys)
    return decisions, solo, body_of_key


def training_body_numbers(windows_or_records):
    """取出现在拟合训练段中的琴身编号。"""
    train = getattr(windows_or_records, 'train', windows_or_records)
    bodies = set()
    for item in train:
        body = body_of(item)
        if body:
            bodies.add(body)
    return frozenset(bodies)


def find_instrument(decisions, query):
    """按琴身编号（容忍 NFKC / 大小写 / 空白）做精确或包含查询。"""
    if query is None:
        return []
    wanted = str(query).strip().casefold()
    if not wanted:
        return []
    if hasattr(decisions, 'decision_by_body'):
        decisions = decisions.decision_by_body
    exact = []
    partial = []
    for body, decision in decisions.items():
        folded = str(body).strip().casefold()
        if folded == wanted:
            exact.append(decision)
        elif wanted in folded:
            partial.append(decision)
    return exact or sorted(partial, key=lambda item: item.body_number or '')


def signing_records(decisions, jobs_by_key=None):
    """生成“一琴一单”的签发清册；可并入派单 Job 的最终状态与估计。"""
    jobs_by_key = jobs_by_key or {}
    signed = []
    for body in sorted(decisions):
        decision = with_job(decisions[body], jobs_by_key)
        if decision.signed_key:
            signed.append(decision.public())
    return signed


def evaluate_instruments(records, *, as_of=96, training_bodies=frozenset(), jobs_by_key=None):
    """一站式入口：返回 (可序列化琴身清册, BodyLedger)。"""
    ledger = BodyLedger.from_records(records, as_of=as_of, training_bodies=training_bodies)
    return ledger.index(jobs_by_key), ledger


# 常见命名别名，便于不同调用约定接入。
build_body_registry = build_registry
resolve_relistings = build_registry
select_latest_listing = resolve_body
latest_listing_decision = resolve_body
sign_second_inspections = evaluate_instruments
issue_second_authentication = evaluate_instruments


class BodyLedger:
    """连接琴身裁决与派单过程的策略对象。

    派单侧在 ``recommend`` 之后调用 :meth:`adjust_job`，在批准前可用
    :meth:`body_of_key` 做“一琴一单”的最后闸口。
    """

    def __init__(self, decisions, solo, body_of_key, *, as_of=96, training_bodies=frozenset()):
        self.decision_by_body = dict(decisions)
        self.solo = dict(solo)
        self.body_of_key = dict(body_of_key)
        self.as_of = as_of
        self.training_bodies = frozenset(training_bodies)

    @classmethod
    def from_records(cls, records, *, as_of=96, training_bodies=frozenset(),
                     photo_target=PHOTO_RELEASE_THRESHOLD, active_keys=None):
        decisions, solo, body_of_key = build_registry(
            records, as_of=as_of, photo_target=photo_target,
            training_bodies=training_bodies, active_keys=active_keys)
        return cls(decisions, solo, body_of_key, as_of=as_of, training_bodies=training_bodies)

    def body_for_key(self, key):
        return self.body_of_key.get(key)

    def decision_for_key(self, key):
        body = self.body_of_key.get(key)
        return self.decision_by_body.get(body) if body else None

    def adjust_job(self, job):
        """按琴身规则改写推荐态；无编号单原样返回（沿用原单）。"""
        decision = self.decision_for_key(job.key)
        if decision is None:
            return job
        key = job.key

        if decision.status == 'photo_hold':
            if key == decision.accepted_key and job.state != '暂停':
                return job.change('暂停', 'MISSING_DETAIL',
                                  '旧单补照暂停未解除：新单实拍未满七张，不能让缺照片的琴上台')
            if key != decision.accepted_key and job.state == '候选':
                return job.change('观察', 'BODY_SUPERSEDED', BASIS_TEXT['BODY_SUPERSEDED'])
            return job

        if decision.status == 'conflict':
            if key in decision.contender_keys and job.state != '暂停':
                return job.change('人工判读', 'SAME_DAY_LISTING_CONFLICT',
                                  BASIS_TEXT['SAME_DAY_LISTING_CONFLICT'])
            if key not in decision.contender_keys and job.state == '候选':
                return job.change('观察', 'BODY_SUPERSEDED', BASIS_TEXT['BODY_SUPERSEDED'])
            return job

        if decision.status == 'after_cutoff':
            if job.state == '候选':
                return job.change('人工判读', 'AFTER_CUTOFF', BASIS_TEXT['AFTER_CUTOFF'])
            return job

        # ready：中选最新挂牌走原预测，其余同琴单不再单独签发。
        if key == decision.accepted_key:
            return job
        if decision.hold_released and job.state == '暂停' and job.reason == 'MISSING_DETAIL':
            return job.change('观察', 'BODY_SUPERSEDED',
                              '新单实拍满七张，补照暂停解除；旧单由最新挂牌接替，不再单独签发')
        if job.state == '候选':
            return job.change('观察', 'BODY_SUPERSEDED', BASIS_TEXT['BODY_SUPERSEDED'])
        return job

    def index(self, jobs_by_key=None):
        jobs_by_key = jobs_by_key or {}
        return [with_job(decision, jobs_by_key).public()
                for body, decision in sorted(self.decision_by_body.items())]

    def query(self, text, jobs_by_key=None):
        found = find_instrument(self.decision_by_body, text)
        return [with_job(item, jobs_by_key).public() for item in found]


def with_job(decision, jobs_by_key):
    """把派单 Job 的状态 / 估计合并进琴的去向与签发标记。"""
    if decision.status in ('conflict', 'photo_hold', 'after_cutoff'):
        # 这些状态由琴身规则强制，派单侧也已同步，不被普通预测覆盖。
        job = jobs_by_key.get(decision.accepted_key) if decision.accepted_key else None
        estimate = getattr(job, 'estimate', None)
        if estimate is None:
            estimate = decision.estimate
        return replace(decision, estimate=estimate)

    key = decision.accepted_key
    job = jobs_by_key.get(key) if key else None
    if job is None:
        return decision
    state = getattr(job, 'state', decision.destination)
    estimate = getattr(job, 'estimate', decision.estimate)
    if state == '已分派':
        label = '二验已签发 · 已上琴台排单'
        signed_key = key
    elif state == '候补':
        label = '最新挂牌列候补，额度腾出后签发'
        signed_key = None
    elif state == '人工判读':
        label = '转人工判读，暂不签发'
        signed_key = None
    elif state == '暂停':
        label = '暂停补照，暂不签发'
        signed_key = None
    else:
        label = f'{state}，达到阈值后再签发二验'
        signed_key = None
    basis = tuple(dict.fromkeys(decision.basis + (f'JOB_{state}',)))
    return InstrumentDecision(
        decision.body_number, decision.status, state, label,
        accepted_key=decision.accepted_key, signed_key=signed_key,
        contender_keys=decision.contender_keys, listing_keys=decision.listing_keys,
        basis=basis, photo_hold=decision.photo_hold, hold_released=decision.hold_released,
        conflict=decision.conflict, training_seen=decision.training_seen,
        risk_source_key=decision.risk_source_key, estimate=estimate,
        cohort=decision.cohort, extra=decision.extra)
