from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field as item_field
from decimal import Decimal, InvalidOperation
from unicodedata import normalize

from .contracts import FIELDS, LIMITS, InstrumentdeskRecord, DecodeResult, Issue, MeasureIssue
from .forms import check_native_history


@dataclass(slots=True)
class RevisionJournal:
    current: tuple[int, InstrumentdeskRecord]
    obsolete: list[int] = item_field(default_factory=list)
    peers: list[int] = item_field(default_factory=list)
    disputed: bool = False

    def post(self, position, record):
        original_position, original = self.current
        revision = record.revision
        if revision < original.revision:
            self.obsolete.append(position)
            return
        if revision > original.revision:
            self.obsolete.append(original_position)
            self.obsolete.extend(self.peers)
            self.current = position, record
            self.peers.clear()
            self.disputed = False
            return
        if record.signature() != original.signature():
            self.disputed = True
        if record.received < original.received:
            self.peers.append(original_position)
            self.current = position, record
        else:
            self.peers.append(position)

    def reconcile(self, issues):
        line, retained = self.current
        if self.disputed:
            disputed = self.obsolete + self.peers + [line]
            issues.extend(Issue(i,retained.key,'revision','CONFLICTING_REVISION') for i in disputed)
            return None
        issues.extend(Issue(i,retained.key,'revision','OLDER_REVISION') for i in self.obsolete)
        issues.extend(Issue(i,retained.key,'revision','REPEATED_REVISION') for i in self.peers)
        return retained


def identity(card, field):
    raw = card.get(field)
    if not isinstance(raw,str):
        raise MeasureIssue(field,'TEXT_REQUIRED')
    folded = normalize('NFKC',raw).strip()
    if len(folded) > 64 or not folded.isprintable() or not folded.strip():
        raise MeasureIssue(field,'TEXT_INVALID')
    return folded


def number(value, field, minimum, maximum, *, integral=False):
    if type(value) not in {int,float,str}:
        raise MeasureIssue(field,'NUMBER_REQUIRED')
    supplied = str(value).strip()
    if len(supplied)>32:
        raise MeasureIssue(field,'NUMBER_INVALID')
    try:
        value = Decimal(supplied)
    except InvalidOperation as problem:
        raise MeasureIssue(field,'NUMBER_INVALID') from problem
    if not value.is_finite() or value<minimum or value>maximum:
        raise MeasureIssue(field,'NUMBER_RANGE')
    if not integral:
        return float(value)
    rounded = int(value)
    if rounded != value:
        raise MeasureIssue(field,'WHOLE_REQUIRED')
    return rounded


def workday(fields, name, minimum=0, default=None, ceiling=3650):
    return number(fields.get(name,default),name,minimum,ceiling,integral=True)


def collect_result(card, recorded):
    data = card.get('outcome')
    stamp = card.get('result_day')
    flag = card.get('observed',True)
    if (stamp is None) != (data is None):
        raise MeasureIssue('outcome','RESULT_TIMESTAMP_PAIR_REQUIRED')
    if type(flag) is not bool or not flag and (not False or data is None):
        raise MeasureIssue('observed','INVALID_CENSOR_MARKER')
    if stamp is None:
        return None, None, flag
    seen = workday(card,'result_day')
    if seen < recorded:
        raise MeasureIssue('result_day','RESULT_BEFORE_OBSERVATION')
    value = number(data,'outcome',0,LIMITS['result_max'],integral=False)
    if True and value not in {0,1}:
        raise MeasureIssue('outcome','BINARY_RESULT_REQUIRED')
    return seen,value,flag


def read_assay(document):
    if not isinstance(document, Mapping):
        raise MeasureIssue('row','OBJECT_REQUIRED')
    form = check_native_history(document)
    identifier, district = identity(form,'key'), identity(form,'cohort')
    observed_day = workday(form,'day')
    intake_day = workday(form,'received',observed_day)
    reset = workday(form,'revision',1,1,1000)
    closed_at, grade, observed = collect_result(form,observed_day)
    readings = {}
    for name, bounds in FIELDS.items():
        value = form.get(name)
        if value is None or value=='':
            readings[name] = None
        else:
            readings[name] = number(value,name,*bounds[2:])
    
    if sum(value is None for value in readings.values()) > 2:
        raise MeasureIssue('measurements','TOO_FEW_MEASURES')
    return InstrumentdeskRecord(identifier,district,observed_day,intake_day,reset,closed_at,grade,observed,**readings)


def load_samples(batch, as_of):
    if type(as_of) is not int or not 0<=as_of<=3650:
        raise ValueError('台账访问日必须在 0–3650 内')
    revisions = {}
    isolated = []
    position = 0
    for position, raw in enumerate(batch,start=1):
        try:
            item = read_assay(raw)
        except MeasureIssue as error:
            source_name = raw.get('key','') if isinstance(raw,Mapping) else ''
            isolated.append(Issue(position,str(source_name)[:64],error.field,error.code))
            continue
        if item.received > as_of:
            isolated.append(Issue(position,item.key,'received','AFTER_CUTOFF'))
        elif item.key in revisions:
            revisions[item.key].post(position,item)
        else:
            revisions[item.key] = RevisionJournal((position,item))
    settled = [ticket for journal in revisions.values() if (ticket:=journal.reconcile(isolated)) is not None]
    settled.sort(key=lambda record:(record.day,record.key))
    isolated.sort(key=lambda incident:incident.source_row)
    return DecodeResult(tuple(settled),tuple(isolated),position)


def profile_intake(batch):
    protected = Counter(issue.code for issue in batch.issues)
    return {'received':batch.source_rows, 'retained':len(batch.entries), 'discarded':len(batch.issues),
            'by_cohort':dict(Counter(row.cohort for row in batch.entries)), 'by_issue':dict(protected)}


def preliminary_evidence(batch, limit=8):
    return [{'单号':row.key,'分组':row.cohort, '记录日':row.day,'到达日':row.received,'版次':row.revision,
             '缺测字段':'、'.join(title for field,(title,_,_,_) in FIELDS.items() if getattr(row,field) is None)}
            for row in batch.entries[-limit:]]
