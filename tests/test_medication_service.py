from datetime import date

import pytest

from app.models.patient import Patient
from app.repositories.medication import MedicationRepository
from app.repositories.patient import PatientRepository
from app.services.medication_catalog import get_catalog_entry, search_catalog
from app.services.medication_service import MedicationService


def make_patient(db_session, mrn="MRN-MED-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Medication Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


# --- catalog ----------------------------------------------------------------


def test_catalog_search_matches_generic_and_brand_name():
    by_generic = search_catalog("sert")
    assert any(e.key == "sertraline" for e in by_generic)

    by_brand = search_catalog("zoloft")
    assert any(e.key == "sertraline" for e in by_brand)


def test_catalog_entry_carries_dose_options_from_fda_steps():
    entry = get_catalog_entry("sertraline")
    assert entry.display == "Sertraline (Zoloft)"
    assert entry.med_class == "SSRI"
    assert entry.doses == ["25 mg", "50 mg", "100 mg", "150 mg", "200 mg"]


def test_catalog_combination_product_uses_display_doses():
    entry = get_catalog_entry("buprenorphine_naloxone")
    assert entry.doses == ["2mg/0.5mg", "4mg/1mg", "8mg/2mg", "12mg/3mg"]


def test_catalog_empty_query_returns_alphabetical_list():
    entries = search_catalog("", limit=100)
    assert len(entries) > 20
    displays = [e.display for e in entries]
    assert displays == sorted(displays)


def test_catalog_unknown_key_returns_none():
    assert get_catalog_entry("not_a_real_med") is None


# --- recording --------------------------------------------------------------


def test_record_catalog_medication_resolves_name_from_key(db_session):
    patient = make_patient(db_session)
    med = MedicationService(db_session).record_medication(
        patient_id=patient.patient_id,
        medication_key="sertraline",
        dose="50 mg",
        frequency="daily",
        recorded_by="Priya Nandakumar",
    )
    assert med.medication_name == "Sertraline (Zoloft)"
    assert med.is_current is True
    assert med.stop_reason is None


def test_record_free_text_medication_without_catalog_key(db_session):
    patient = make_patient(db_session)
    med = MedicationService(db_session).record_medication(
        patient_id=patient.patient_id,
        medication_name="Metformin",
        dose="500 mg",
        frequency="twice daily",
    )
    assert med.medication_key is None
    assert med.medication_name == "Metformin"


def test_record_medication_rejects_unknown_catalog_key(db_session):
    patient = make_patient(db_session)
    with pytest.raises(ValueError, match="Unknown medication_key"):
        MedicationService(db_session).record_medication(
            patient_id=patient.patient_id, medication_key="not_a_real_med"
        )


def test_record_medication_requires_key_or_name(db_session):
    patient = make_patient(db_session)
    with pytest.raises(ValueError, match="medication_key or medication_name"):
        MedicationService(db_session).record_medication(patient_id=patient.patient_id)


def test_record_past_medication_with_stop_reason(db_session):
    patient = make_patient(db_session)
    med = MedicationService(db_session).record_medication(
        patient_id=patient.patient_id,
        medication_key="fluoxetine",
        is_current=False,
        stop_reason="GI side effects",
    )
    assert med.is_current is False
    assert med.stop_reason == "GI side effects"


def test_stop_reason_on_current_medication_is_rejected(db_session):
    patient = make_patient(db_session)
    with pytest.raises(ValueError, match="only valid on a past medication"):
        MedicationService(db_session).record_medication(
            patient_id=patient.patient_id,
            medication_key="sertraline",
            is_current=True,
            stop_reason="should not be allowed",
        )


def test_record_medication_unknown_patient_is_rejected(db_session):
    with pytest.raises(ValueError, match="Patient 99999 not found"):
        MedicationService(db_session).record_medication(
            patient_id=99999, medication_key="sertraline"
        )


# --- updating ---------------------------------------------------------------


def test_stopping_a_medication_records_the_reason(db_session):
    patient = make_patient(db_session)
    service = MedicationService(db_session)
    med = service.record_medication(patient_id=patient.patient_id, medication_key="sertraline")

    updated = service.update_medication(
        med.medication_id, is_current=False, stop_reason="Achieved remission"
    )
    assert updated.is_current is False
    assert updated.stop_reason == "Achieved remission"


def test_restarting_a_medication_clears_the_stop_reason(db_session):
    patient = make_patient(db_session)
    service = MedicationService(db_session)
    med = service.record_medication(
        patient_id=patient.patient_id,
        medication_key="sertraline",
        is_current=False,
        stop_reason="Cost",
    )

    restarted = service.update_medication(med.medication_id, is_current=True)
    assert restarted.is_current is True
    assert restarted.stop_reason is None


def test_update_cannot_change_identity_fields(db_session):
    patient = make_patient(db_session)
    service = MedicationService(db_session)
    med = service.record_medication(patient_id=patient.patient_id, medication_key="sertraline")

    with pytest.raises(ValueError, match="Cannot update fields"):
        service.update_medication(med.medication_id, medication_name="Something Else")


def test_dose_change_on_past_medication_keeps_stop_reason(db_session):
    patient = make_patient(db_session)
    service = MedicationService(db_session)
    med = service.record_medication(
        patient_id=patient.patient_id,
        medication_key="sertraline",
        dose="50 mg",
        is_current=False,
        stop_reason="Switched to SNRI",
    )

    updated = service.update_medication(med.medication_id, dose="100 mg")
    assert updated.dose == "100 mg"
    assert updated.stop_reason == "Switched to SNRI"


# --- listing ----------------------------------------------------------------


def test_list_by_patient_orders_current_first(db_session):
    patient = make_patient(db_session)
    service = MedicationService(db_session)
    service.record_medication(
        patient_id=patient.patient_id,
        medication_key="fluoxetine",
        is_current=False,
        stop_reason="Ineffective",
    )
    service.record_medication(patient_id=patient.patient_id, medication_key="sertraline")

    meds = MedicationRepository(db_session).list_by_patient(patient.patient_id)
    assert [m.medication_key for m in meds] == ["sertraline", "fluoxetine"]

    current = MedicationRepository(db_session).list_current_by_patient(patient.patient_id)
    assert [m.medication_key for m in current] == ["sertraline"]


# --- reporting integration ---------------------------------------------------


def test_active_patients_psychotropic_column(db_session):
    from app.services.episode_service import EpisodeService
    from app.services.reporting import build_active_patients_report

    patient = make_patient(db_session, mrn="MRN-MED-RPT")
    EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1)
    )
    service = MedicationService(db_session)

    # A free-text (non-catalog) med can't be classified — doesn't count.
    service.record_medication(patient_id=patient.patient_id, medication_name="Metformin")
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 1))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.psychotropic_medications is False

    # A past catalog med doesn't count either; a current one does.
    stopped = service.record_medication(
        patient_id=patient.patient_id,
        medication_key="fluoxetine",
        is_current=False,
        stop_reason="Ineffective",
    )
    sertraline = service.record_medication(
        patient_id=patient.patient_id, medication_key="sertraline"
    )
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 1))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.psychotropic_medications is True

    service.update_medication(
        sertraline.medication_id, is_current=False, stop_reason="Achieved remission"
    )
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 1))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.psychotropic_medications is False
    assert stopped.is_current is False


def test_clinical_dashboard_includes_medications(db_session):
    from app.services.reporting import build_clinical_dashboard

    patient = make_patient(db_session, mrn="MRN-MED-DASH")
    service = MedicationService(db_session)
    service.record_medication(
        patient_id=patient.patient_id,
        medication_key="sertraline",
        dose="50 mg",
        frequency="daily",
    )
    service.record_medication(
        patient_id=patient.patient_id,
        medication_key="fluoxetine",
        is_current=False,
        stop_reason="GI side effects",
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)

    assert [m.medication_key for m in dashboard.medications] == ["sertraline", "fluoxetine"]
    current = dashboard.medications[0]
    assert current.medication_name == "Sertraline (Zoloft)"
    assert current.dose == "50 mg"
    assert current.frequency == "daily"
    assert current.is_current is True
    past = dashboard.medications[1]
    assert past.stop_reason == "GI side effects"
