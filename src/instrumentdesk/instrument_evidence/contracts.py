from dataclasses import dataclass
from math import isfinite
from ..consignment_notes.contracts import InstrumentdeskRecord as RawObservation

RAW_KEYS = ('wear_grade', 'repair_count', 'setup_age', 'photos', 'price_index', 'play_log')
FEATURE_KEYS = ('wear_repairs', 'setup_lag', 'photo_attestation', 'pricing_gap', 'repair_risk')
FEATURE_NAMES = ('磨损和历史维修', '试奏修正的校准时差', '细节证据密度', '挂牌价偏差', '溢价时的维修负担')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class InstrumentEvidence:
    inspection_density: float
    freshness_days: float
    repair_photos: float
    price_over: float
    sound_evidence: float
    condition_attention: float
    reference_lower: float
    moisture_age_proxy: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.inspection_density, self.freshness_days, self.repair_photos, self.price_over, self.sound_evidence, self.condition_attention, self.reference_lower, self.moisture_age_proxy)):
            raise ValueError('寄售单存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('每磨损档照片', round(self.inspection_density, 4)),
            ('离试奏前校准日期', round(self.freshness_days, 4)),
            ('每次维修的影像', round(self.repair_photos, 4)),
            ('挂牌超出行情点', round(self.price_over, 4)),
            ('每次维修试奏覆盖', round(self.sound_evidence, 4)),
            ('磨损维修叠加', round(self.condition_attention, 4)),
            ('低于行情点', round(self.reference_lower, 4)),
            ('校准与磨损叠加暴露', round(self.moisture_age_proxy, 4)),
        )
