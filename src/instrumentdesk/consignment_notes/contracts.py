from dataclasses import dataclass

FIELDS = {'wear_grade': ('外观磨损分', '分', 1, 10),
 'repair_count': ('历史维修次数', '次', 0, 8),
 'setup_age': ('距上次校准', '天', 1, 270),
 'photos': ('有效细节照片', '张', 2, 32),
 'price_index': ('挂牌价与行情比', '%', 51, 155),
 'play_log': ('试奏留档时长', 'min', 0, 55)}
LIMITS = {'result_max': 1}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class InstrumentdeskRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    wear_grade: float | None
    repair_count: float | None
    setup_age: float | None
    photos: float | None
    price_index: float | None
    play_log: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[InstrumentdeskRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int
