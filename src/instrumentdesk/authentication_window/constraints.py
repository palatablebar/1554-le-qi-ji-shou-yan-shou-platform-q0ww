from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_authentication_window(consignments, admit: Callable, wait: Callable):
    review_work = set()
    for item in consignments:
        wear, repair_history, age, photos, appraisal, recorded = item.assessment.raw.input_values
        test = (item.job.cohort, '多次返修' if repair_history>=4 else '外观')
        if recorded < 6 and price_exposure(appraisal, wear) > 2.1:
            wait(item, 'PLAY_FILE_REQUIRED', '先补试奏再请二验师')
            continue
        if test in review_work and wear > 5 and photos <= 9:
            wait(item, 'APPRAISAL_HANDOVER', '同类品相合并交给验收专员')
        elif admit(item):
            review_work.add(test)

def price_exposure(appraisal, wear):
    return max(0, appraisal-105)/45 + wear/4
