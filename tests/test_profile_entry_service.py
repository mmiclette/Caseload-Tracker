from datetime import date

import pytest

from app.models.enums import ProfileSection
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.repositories.profile_entry import ProfileEntryRepository
from app.services.profile_entry_service import (
    SECTION_SUB_FIELD_SUGGESTIONS,
    ProfileEntryService,
)


def make_patient(db_session, mrn="MRN-PROF-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Profile Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_record_entry_with_date_and_context(db_session):
    patient = make_patient(db_session)
    entry = ProfileEntryService(db_session).record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SOCIAL_ENVIRONMENTAL,
        sub_field="living_situation",
        value="Lives alone, stable housing",
        context="Discussed during initial assessment",
        recorded_date=date(2026, 2, 1),
        recorded_by="Priya Nandakumar",
    )
    assert entry.profile_entry_id is not None
    assert entry.section == ProfileSection.SOCIAL_ENVIRONMENTAL
    assert entry.context == "Discussed during initial assessment"
    assert entry.recorded_date == date(2026, 2, 1)


def test_recorded_date_defaults_to_today(db_session):
    patient = make_patient(db_session)
    entry = ProfileEntryService(db_session).record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.BEHAVIORAL_HEALTH,
        sub_field="diagnoses",
        value="MDD, moderate",
    )
    assert entry.recorded_date == date.today()


def test_record_entry_unknown_patient_is_rejected(db_session):
    with pytest.raises(ValueError, match="Patient 99999 not found"):
        ProfileEntryService(db_session).record_entry(
            patient_id=99999,
            section=ProfileSection.MEDICAL_PROFILE,
            sub_field="chronic_pain",
            value="Lower back pain",
        )


def test_empty_value_and_sub_field_are_rejected(db_session):
    patient = make_patient(db_session)
    service = ProfileEntryService(db_session)
    with pytest.raises(ValueError, match="value must not be empty"):
        service.record_entry(
            patient_id=patient.patient_id,
            section=ProfileSection.SUBSTANCE_USE,
            sub_field="alcohol",
            value="   ",
        )
    with pytest.raises(ValueError, match="sub_field must not be empty"):
        service.record_entry(
            patient_id=patient.patient_id,
            section=ProfileSection.SUBSTANCE_USE,
            sub_field="",
            value="2-3 drinks weekly",
        )


def test_custom_sub_field_beyond_suggestions_is_accepted(db_session):
    """Suggestions are picker defaults, not validation."""
    patient = make_patient(db_session)
    entry = ProfileEntryService(db_session).record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SOCIAL_ENVIRONMENTAL,
        sub_field="caregiver_status",
        value="Primary caregiver for elderly parent",
    )
    assert entry.sub_field == "caregiver_status"


def test_append_only_history_newest_first_per_sub_field(db_session):
    patient = make_patient(db_session)
    service = ProfileEntryService(db_session)
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SAFETY_AND_RISK,
        sub_field="access_to_firearms",
        value="Yes — hunting rifle in home",
        recorded_date=date(2026, 1, 10),
    )
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SAFETY_AND_RISK,
        sub_field="access_to_firearms",
        value="No — firearm moved to relative's home",
        context="Safety plan step completed",
        recorded_date=date(2026, 2, 20),
    )
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SAFETY_AND_RISK,
        sub_field="safety_plan",
        value="Completed, copy given to patient",
        recorded_date=date(2026, 1, 10),
    )

    entries = ProfileEntryRepository(db_session).list_by_patient(patient.patient_id)
    firearms = [e for e in entries if e.sub_field == "access_to_firearms"]
    assert [e.recorded_date for e in firearms] == [date(2026, 2, 20), date(2026, 1, 10)]
    assert firearms[0].value.startswith("No")


def test_same_day_entries_break_ties_by_insert_order(db_session):
    patient = make_patient(db_session)
    service = ProfileEntryService(db_session)
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.BEHAVIORAL_HEALTH,
        sub_field="treatment_goals",
        value="Reduce PHQ-9 below 10",
        recorded_date=date(2026, 3, 1),
    )
    corrected = service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.BEHAVIORAL_HEALTH,
        sub_field="treatment_goals",
        value="Reduce PHQ-9 below 5 (remission)",
        recorded_date=date(2026, 3, 1),
    )

    entries = ProfileEntryRepository(db_session).list_by_patient(
        patient.patient_id, section=ProfileSection.BEHAVIORAL_HEALTH
    )
    assert entries[0].profile_entry_id == corrected.profile_entry_id


def test_section_filter(db_session):
    patient = make_patient(db_session)
    service = ProfileEntryService(db_session)
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SUBSTANCE_USE,
        sub_field="nicotine",
        value="Vapes daily",
    )
    service.record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.MEDICAL_PROFILE,
        sub_field="sleep_disorders",
        value="Reports insomnia",
    )

    substance_only = ProfileEntryRepository(db_session).list_by_patient(
        patient.patient_id, section=ProfileSection.SUBSTANCE_USE
    )
    assert [e.sub_field for e in substance_only] == ["nicotine"]


def test_suggestions_cover_every_section_and_meds_section_is_allergies_only():
    assert set(SECTION_SUB_FIELD_SUGGESTIONS) == set(ProfileSection)
    assert SECTION_SUB_FIELD_SUGGESTIONS[ProfileSection.CURRENT_MEDICATIONS] == [
        "allergies_intolerances"
    ]


def test_clinical_dashboard_includes_profile_entries(db_session):
    from app.services.reporting import build_clinical_dashboard

    patient = make_patient(db_session, mrn="MRN-PROF-DASH")
    ProfileEntryService(db_session).record_entry(
        patient_id=patient.patient_id,
        section=ProfileSection.SOCIAL_ENVIRONMENTAL,
        sub_field="transportation",
        value="No car; relies on bus",
        recorded_date=date(2026, 2, 1),
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)
    assert len(dashboard.profile_entries) == 1
    entry = dashboard.profile_entries[0]
    assert entry.section == ProfileSection.SOCIAL_ENVIRONMENTAL
    assert entry.sub_field == "transportation"
    assert entry.recorded_date == date(2026, 2, 1)
