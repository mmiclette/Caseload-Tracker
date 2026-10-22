from datetime import date

from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.consultation_service import ConsultationService


def make_patient(db_session, mrn="MRN-CON-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Consultation Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 2),
            needs_psychiatric_review=True,
        )
    )


def test_recording_a_consultation_clears_the_yellow_flag(db_session):
    patient = make_patient(db_session)
    service = ConsultationService(db_session)

    service.record_consultation(patient_id=patient.patient_id, consultation_date=date(2026, 6, 1))

    refreshed = service.patients.get_by_id(patient.patient_id)
    assert refreshed.needs_psychiatric_review is False


def test_flagged_for_next_review_resets_the_flag_immediately(db_session):
    """
    "Reviewed today" and "review again next time" are different things — a
    consultation that itself flags a future review should leave the flag
    on, not cleared.
    """
    patient = make_patient(db_session, mrn="MRN-CON-2")
    service = ConsultationService(db_session)

    consultation = service.record_consultation(
        patient_id=patient.patient_id,
        consultation_date=date(2026, 6, 1),
        flagged_for_next_review=True,
        flag_reason="Medication change needs follow-up",
    )

    refreshed = service.patients.get_by_id(patient.patient_id)
    assert refreshed.needs_psychiatric_review is True
    assert consultation.flag_reason == "Medication change needs follow-up"


def test_recommendations_forwarded_defaults_to_false(db_session):
    patient = make_patient(db_session, mrn="MRN-CON-3")
    service = ConsultationService(db_session)

    consultation = service.record_consultation(
        patient_id=patient.patient_id, consultation_date=date(2026, 6, 1)
    )

    assert consultation.recommendations_forwarded is False
