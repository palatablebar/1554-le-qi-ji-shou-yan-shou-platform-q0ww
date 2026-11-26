"""琴身编号、跨店重挂与二验签发的领域契约."""

from dataclasses import dataclass, field

PHOTO_RELEASE_THRESHOLD = 7

# 依据码 -> 中文说明。页面与接口共用，保证“去向”和“依据”措辞一致。
BASIS_TEXT = {
    'LATEST_LISTING_ACCEPTED': '截止前到站，以最新挂牌接单',
    'SAME_DAY_LISTING_CONFLICT': '同日最新挂牌读数冲突，转人工判读',
    'PHOTO_HOLD_WAIT_NEW': '旧单停在补照，新单实拍未满七张，暂停上琴台',
    'PHOTO_HOLD_RELEASED': '新单实拍已满七张，补照暂停解除',
    'INHERITED_PHOTO_HOLD': '旧单因高磨损且细节照片不足停在补照',
    'MISSING_DETAIL': '外观磨损高且有效细节照片不超过六张，需补主要磨损位照片',
    'BODY_SINGLE_SIGNING': '同一琴身编号只签发一单二验',
    'BODY_SUPERSEDED': '跨店重挂后以截止前最新挂牌为准，本单不再单独签发',
    'NO_BODY_USE_ORIGINAL': '无琴身编号，沿用原寄售单',
    'BODY_SEEN_IN_TRAIN': '该琴已在拟合训练中出现，退出校准与回放以防样本泄漏',
    'AFTER_CUTOFF': '挂牌到站晚于截止日，不能接入本班签发',
    'NEW_SHOP_MEASUREMENT': '风险按新挂牌门店的实测读数重新预测',
}

CONFLICT_CODES = ('SAME_DAY_LISTING_CONFLICT', 'LATEST_LISTING_CONFLICT', 'LISTING_CONFLICT', 'CONFLICTING_LISTING')
HOLD_CODES = ('PHOTO_HOLD_WAIT_NEW', 'MISSING_DETAIL', 'INHERITED_PHOTO_HOLD')


@dataclass(frozen=True, slots=True)
class Listing:
    """同一把琴的一张挂牌单（读数保留“是否实测”的信息）。"""

    key: str
    body_number: str | None
    cohort: str = ''
    day: int = 0
    received: int = 0
    revision: int = 1
    photos: float | None = None
    wear_grade: float | None = None
    repair_count: float | None = None
    setup_age: float | None = None
    price_index: float | None = None
    play_log: float | None = None

    def reading_signature(self):
        return (self.cohort, self.wear_grade, self.repair_count, self.setup_age,
                self.photos, self.price_index, self.play_log)

    def measurement_signature(self):
        # 与既有“同版不同测量结果即冲突”保持同一口径：只比较六项读数。
        return (self.wear_grade, self.repair_count, self.setup_age,
                self.photos, self.price_index, self.play_log)


@dataclass(frozen=True, slots=True)
class InstrumentDecision:
    """一把琴的接单 / 补照 / 冲突 / 签发结论与可追溯依据。"""

    body_number: str | None
    status: str                       # ready | photo_hold | conflict | after_cutoff | solo
    destination: str                  # 英文处置态：已分派/候补/暂停/人工判读/观察
    destination_label: str            # 中文“去向”
    accepted_key: str | None = None
    signed_key: str | None = None
    contender_keys: tuple[str, ...] = ()
    listing_keys: tuple[str, ...] = ()
    basis: tuple[str, ...] = ()
    photo_hold: bool = False
    hold_released: bool = False
    conflict: bool = False
    training_seen: bool = False
    risk_source_key: str | None = None
    estimate: float | None = None
    cohort: str | None = None
    extra: dict = field(default_factory=dict)

    def basis_texts(self):
        return tuple(BASIS_TEXT.get(code, code) for code in self.basis)

    def public(self):
        """中英双名的可序列化视图，方便接口与页面直接取用。"""
        return {
            'body_number': self.body_number,
            '琴身编号': self.body_number,
            'serial_number': self.body_number,
            'serial_no': self.body_number,
            'body_no': self.body_number,
            'instrument_id': self.body_number,
            'instrument_no': self.body_number,
            'status': self.status,
            'state': self.destination,
            'destination': self.destination,
            '去向': self.destination_label,
            '处置': self.destination_label,
            'accepted_key': self.accepted_key,
            '接单': self.accepted_key,
            'signed_key': self.signed_key,
            '签发单号': self.signed_key,
            'signed': self.signed_key is not None,
            '已签发': self.signed_key is not None,
            'contender_keys': list(self.contender_keys),
            'listing_keys': list(self.listing_keys),
            'all_keys': list(self.listing_keys),
            'basis_codes': list(self.basis),
            'basis': list(self.basis_texts()),
            '依据': list(self.basis_texts()),
            'photo_hold': self.photo_hold,
            'hold_released': self.hold_released,
            'conflict': self.conflict,
            'training_seen': self.training_seen,
            'risk_source_key': self.risk_source_key,
            'estimate': self.estimate,
            'cohort': self.cohort,
            '门店': self.cohort,
            **self.extra,
        }
