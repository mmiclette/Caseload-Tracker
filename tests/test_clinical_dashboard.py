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
from app.services.reporting import build_clinical_dashboard


def make_patient(db_session, mrn="MRN-CD-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Dashboard Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_missing_patient_raises(db_session):
    with pytest.raises(ValueError):
        build_clinical_dashboard(db_session, 999_999)


def test_dashboard_includes_demographics_and_flags(db_session):
    patient = make_patient(db_session)

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)

    assert dashboard.mrn == "MRN-CD-1"
    assert dashboard.age == patient.age
    assert dashboard.needs_psychiatric_review is False
    assert dashboard.current_status is None  # no episode yet


def test_dashboard_shows_current_providers_and_clinics(db_session):
    patient = make_patient(db_session, mrn="MRN-CD-2")
    provider = ProviderRepository(db_session).create(
        Provider(name="Dashboard CM", role=ProviderRole.CARE_MANAGER)
    )
    CareTeamAssignmentRepository(db_session).create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )
    ClinicAssignmentRepository(db_session).create(
        ClinicAssignment(
            patient_id=patient.patient_id,
            clinic_id="dashboard-clinic",
            is_primary=True,
            service_begin_date=date(2026, 1, 1),
        )
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)

    assert [p.provider_id for p in dashboard.current_providers] == [provider.provider_id]
    assert dashboard.current_providers[0].role == ProviderRole.CARE_MANAGER
    assert [c.clinic_id for c in dashboard.current_clinics] == ["dashboard-clinic"]


def test_dashboard_includes_episode_history_and_scores_over_time(db_session):
    patient = make_patient(db_session, mrn="MRN-CD-3")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 1, 15),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)

    assert len(dashboard.episodes) == 1
    assert dashboard.episodes[0].baseline_score == 20
    assert [s.score_value for s in dashboard.symptom_scores] == [20, 10]
    assert dashboard.current_status.value == "active_treatment"
