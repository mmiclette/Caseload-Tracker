from datetime import date

from app.models.care_team_assignment import CareTeamAssignment
from app.models.clinic_assignment import ClinicAssignment
from app.models.enums import (
    CareTeamRole,
    ContactType,
    MeasureType,
    ProviderRole,
)
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository
from app.services.consultation_service import ConsultationService
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.reporting import build_active_patients_report


def make_patient(db_session, mrn="MRN-RPT-1", payer="Medicaid"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Reporting Test Patient",
            payer=payer,
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_deactivated_patient_excluded_from_report(db_session):
    patient = make_patient(db_session)
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    episode_service.update_episode(episode.episode_id, end_date=date(2026, 2, 1))

    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 15))

    assert patient.patient_id not in {r.patient_id for r in rows}


def test_patient_with_no_open_episode_excluded(db_session):
    patient = make_patient(db_session, mrn="MRN-RPT-2")
    # No episode created at all -> no current status -> excluded.
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 15))
    assert patient.patient_id not in {r.patient_id for r in rows}


def test_active_patient_row_shape_and_score_first_last(db_session):
    patient = make_patient(db_session, mrn="MRN-RPT-3")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 15),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
    )

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 29))
    row = next(r for r in rows if r.patient_id == patient.patient_id)

    assert row.mrn == "MRN-RPT-3"
    assert row.phq9_first == 20
    assert row.phq9_last == 10
    assert row.initial_assessment_date == date(2026, 1, 1)
    assert row.follow_up_date == date(2026, 1, 15)
    assert row.session_count == 2
    assert row.weeks_since_initial_assessment == 4
    assert row.minutes_this_month == 75


def test_contact_attempt_does_not_count_as_a_session(db_session):
    patient = make_patient(db_session, mrn="MRN-RPT-4")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 1, 8),
    )

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 29))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.session_count == 1


def test_needs_review_shows_consider(db_session):
    patient = make_patient(db_session, mrn="MRN-RPT-5")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 5),
        discuss_with_psychiatric_consultant=True,
    )

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 10))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.psychiatric_consultation == "CONSIDER"


def test_consultation_clears_consider_and_shows_date(db_session):
    patient = make_patient(db_session, mrn="MRN-RPT-6")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service = ContactService(db_session)
    consultation_service = ConsultationService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 5),
        discuss_with_psychiatric_consultant=True,
    )
    consultation_service.record_consultation(
        patient_id=patient.patient_id, consultation_date=date(2026, 1, 10)
    )

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 15))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.psychiatric_consultation == "2026-01-10"


def test_filter_by_payer(db_session):
    medicaid_patient = make_patient(db_session, mrn="MRN-RPT-7", payer="Medicaid")
    medicare_patient = make_patient(db_session, mrn="MRN-RPT-8", payer="Medicare")
    episode_service = EpisodeService(db_session)
    episode_service.create_episode(patient_id=medicaid_patient.patient_id, start_date=date(2026, 1, 1))
    episode_service.create_episode(patient_id=medicare_patient.patient_id, start_date=date(2026, 1, 1))

    rows = build_active_patients_report(db_session, payer="Medicaid", as_of=date(2026, 1, 10))
    ids = {r.patient_id for r in rows}
    assert medicaid_patient.patient_id in ids
    assert medicare_patient.patient_id not in ids


def test_filter_by_clinic(db_session):
    patient_a = make_patient(db_session, mrn="MRN-RPT-9")
    patient_b = make_patient(db_session, mrn="MRN-RPT-10")
    episode_service = EpisodeService(db_session)
    episode_service.create_episode(patient_id=patient_a.patient_id, start_date=date(2026, 1, 1))
    episode_service.create_episode(patient_id=patient_b.patient_id, start_date=date(2026, 1, 1))

    ClinicAssignmentRepository(db_session).create(
        ClinicAssignment(
            patient_id=patient_a.patient_id, clinic_id="clinic-a", service_begin_date=date(2026, 1, 1)
        )
    )
    ClinicAssignmentRepository(db_session).create(
        ClinicAssignment(
            patient_id=patient_b.patient_id, clinic_id="clinic-b", service_begin_date=date(2026, 1, 1)
        )
    )

    rows = build_active_patients_report(db_session, clinic_id="clinic-a", as_of=date(2026, 1, 10))
    ids = {r.patient_id for r in rows}
    assert patient_a.patient_id in ids
    assert patient_b.patient_id not in ids


def test_filter_by_provider(db_session):
    patient_a = make_patient(db_session, mrn="MRN-RPT-11")
    patient_b = make_patient(db_session, mrn="MRN-RPT-12")
    episode_service = EpisodeService(db_session)
    episode_service.create_episode(patient_id=patient_a.patient_id, start_date=date(2026, 1, 1))
    episode_service.create_episode(patient_id=patient_b.patient_id, start_date=date(2026, 1, 1))

    provider = ProviderRepository(db_session).create(
        Provider(name="Care Manager Report Test", role=ProviderRole.CARE_MANAGER)
    )
    CareTeamAssignmentRepository(db_session).create(
        CareTeamAssignment(
            patient_id=patient_a.patient_id,
            provider_id=provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )

    rows = build_active_patients_report(
        db_session, provider_id=provider.provider_id, as_of=date(2026, 1, 10)
    )
    ids = {r.patient_id for r in rows}
    assert patient_a.patient_id in ids
    assert patient_b.patient_id not in ids
