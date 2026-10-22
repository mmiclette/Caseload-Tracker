from datetime import date

import pytest

from app.models.care_team_assignment import CareTeamAssignment
from app.models.clinic_assignment import ClinicAssignment
from app.models.enums import CareTeamRole, ContactType, MeasureType, ProviderRole
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.reporting import build_caseload_statistics


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Caseload Stats Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def assign_to_provider(db_session, patient, provider):
    CareTeamAssignmentRepository(db_session).create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )


def test_invalid_group_by_raises(db_session):
    with pytest.raises(ValueError):
        build_caseload_statistics(db_session, group_by="nonsense")


def test_empty_caseload_when_no_assignments(db_session):
    rows = build_caseload_statistics(db_session, group_by="provider")
    assert rows == []


def test_caseload_size_and_response_rate_for_one_provider(db_session):
    provider = ProviderRepository(db_session).create(
        Provider(name="Stats CM", role=ProviderRole.CARE_MANAGER)
    )

    patient_a = make_patient(db_session, "MRN-STAT-1")
    patient_b = make_patient(db_session, "MRN-STAT-2")
    assign_to_provider(db_session, patient_a, provider)
    assign_to_provider(db_session, patient_b, provider)

    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode_a = episode_service.create_episode(patient_id=patient_a.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient_a.patient_id,
        episode_id=episode_a.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        duration_minutes=50,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    # >= 50% improvement from 20 -> 10 counts as a PHQ-9 response.
    contact_service.record_contact(
        patient_id=patient_a.patient_id,
        episode_id=episode_a.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 15),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
    )

    episode_b = episode_service.create_episode(patient_id=patient_b.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient_b.patient_id,
        episode_id=episode_b.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        duration_minutes=40,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 15}],
    )
    # Only a 1-point improvement -> not a response, not remission (>= 5).
    contact_service.record_contact(
        patient_id=patient_b.patient_id,
        episode_id=episode_b.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 15),
        duration_minutes=20,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 14}],
    )

    rows = build_caseload_statistics(db_session, group_by="provider")
    row = next(r for r in rows if r.group_key == str(provider.provider_id))

    assert row.caseload_size == 2
    assert row.avg_visits_per_patient == 2.0
    assert row.avg_session_duration_minutes == 35.0  # (50+30+40+20)/4
    assert row.pct_contacts_with_completed_scale == 100.0
    # These episodes predate primary_diagnosis — their PHQ-9 baselines fall
    # back to the depression bucket (legacy fallback).
    assert row.depression_response_denominator == 2
    assert row.depression_response_count == 1
    assert row.depression_response_percentage == 50.0
    assert row.depression_remission_count == 0


def test_deactivated_patient_excluded_from_caseload(db_session):
    """
    The Care Team Assignment itself doesn't end just because the patient
    was deactivated (that's a separate, unlinked event a Care Manager would
    handle explicitly) — so the provider still shows up here, just with a
    caseload of 0 rather than counting a deactivated patient.
    """
    provider = ProviderRepository(db_session).create(
        Provider(name="Stats CM 2", role=ProviderRole.CARE_MANAGER)
    )
    patient = make_patient(db_session, "MRN-STAT-3")
    assign_to_provider(db_session, patient, provider)

    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    episode_service.update_episode(episode.episode_id, end_date=date(2026, 2, 1))

    rows = build_caseload_statistics(db_session, group_by="provider")
    row = next(r for r in rows if r.group_key == str(provider.provider_id))
    assert row.caseload_size == 0


def test_group_by_clinic(db_session):
    patient = make_patient(db_session, "MRN-STAT-4")
    ClinicAssignmentRepository(db_session).create(
        ClinicAssignment(
            patient_id=patient.patient_id, clinic_id="stats-clinic", service_begin_date=date(2026, 1, 1)
        )
    )
    EpisodeService(db_session).create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    rows = build_caseload_statistics(db_session, group_by="clinic")
    row = next(r for r in rows if r.group_key == "stats-clinic")
    assert row.caseload_size == 1
    assert row.group_type == "clinic"
