from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class ConsignmentNotesSheet:
    wear_in_tenths: Decimal
    previous_repairs: Decimal
    setup_hours_old: Decimal
    usable_witness_photos: Decimal
    asking_basis_points: Decimal
    recorded_play_sec: Decimal

    def fields(self):
        return {
            'wear_grade': float(self.wear_in_tenths) / 10,
            'repair_count': float(self.previous_repairs),
            'setup_age': float(self.setup_hours_old) / 24,
            'photos': float(self.usable_witness_photos),
            'price_index': float(self.asking_basis_points) / 100,
            'play_log': float(self.recorded_play_sec) / 60,
        }

    def validation(self):
        fields = self.fields()
        wear_grade = fields['wear_grade']
        repair_count = fields['repair_count']
        setup_age = fields['setup_age']
        photos = fields['photos']
        price_index = fields['price_index']
        play_log = fields['play_log']
        listing_pressure = price_index/max(1,photos)
        sounded_min = play_log/max(1,repair_count)
        condition_pressure = (10-wear_grade+1)*photos
        new_service_window = setup_age==1 and wear_grade>=8
        alerts = []
        if condition_pressure<6 and listing_pressure>30:
            alerts.append(('usable_witness_photos', 'APPRAISAL_EVIDENCE_INCOMPLETE'))
        if new_service_window and sounded_min<1:
            alerts.append(('setup_hours_old', 'SETUP_NOTE_NEEDS_SIGNATURE'))
        if sounded_min>=50 and repair_count>=1:
            alerts.append(('recorded_play_sec', 'CHECK_SOUND_FILE_DURATION'))
        return tuple(alerts)


def read_consignment_notes(form):
    return ConsignmentNotesSheet(
        wear_in_tenths=form_number(form, '品相记录', 'wear_in_tenths', 10, 100),
        previous_repairs=form_number(form, '品相记录', 'previous_repairs', 0, 8),
        setup_hours_old=form_number(form, '估价单', 'setup_hours_old', 24, 6480),
        usable_witness_photos=form_number(form, '估价单', 'usable_witness_photos', 2, 32),
        asking_basis_points=form_number(form, '试奏交接', 'asking_basis_points', 5100, 15500),
        recorded_play_sec=form_number(form, '试奏交接', 'recorded_play_sec', 0, 3300),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_consignment_notes(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('wear_grade', 'repair_count', 'setup_age', 'photos', 'price_index', 'play_log')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}
