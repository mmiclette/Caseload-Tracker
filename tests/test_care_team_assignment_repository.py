from datetime import date

from app.models.care_team_assignment import CareTeamAssignment
from app.models.enums import CareTeamRole, ProviderRole
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository


def make_patient(db_session, mrn="MRN-CTA-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Care Team Test Patient",
            payer="Medicaid",
            date_of_birth=date(1990, 6, 15),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 2),
        )
    )


def make_provider(db_session, name="Care Manager A", role=ProviderRole.CARE_MANAGER):
    return ProviderRepository(db_session).create(Provider(name=name, role=role))


def test_current_assignment_has_no_end_date(db_session):
    patient = make_patient(db_session)
    provider = make_provider(db_session)
    repo = CareTeamAssignmentRepository(db_session)

    assignment = repo.create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )

    assert assignment.service_end_date is None
    assert repo.list_current_by_patient(patient.patient_id) == [assignment]


def test_ended_assignment_excluded_from_current(db_session):
    patient = make_patient(db_session, mrn="MRN-CTA-2")
    old_provider = make_provider(db_session, name="Care Manager B")
    new_provider = make_provider(db_session, name="Care Manager C")
    repo = CareTeamAssignmentRepository(db_session)

    ended = repo.create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=old_provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2025, 1, 1),
            service_end_date=date(2026, 1, 1),
        )
    )
    current = repo.create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=new_provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )

    all_assignments = repo.list_by_patient(patient.patient_id)
    assert {a.care_team_assignment_id for a in all_assignments} == {
        ended.care_team_assignment_id,
        current.care_team_assignment_id,
    }
    current_only = repo.list_current_by_patient(patient.patient_id)
    assert [a.care_team_assignment_id for a in current_only] == [current.care_team_assignment_id]


def test_patient_can_have_more_than_one_current_provider(db_session):
    """
    A patient's Care Manager and Psychiatric Consultant are both "current"
    at once — the Clinical Dashboard's "Current Providers" table shows one
    row per role, not one row total.
    """
    patient = make_patient(db_session, mrn="MRN-CTA-3")
    care_manager = make_provider(db_session, name="Care Manager D", role=ProviderRole.CARE_MANAGER)
    consultant = make_provider(
        db_session, name="Consultant D", role=ProviderRole.PSYCHIATRIC_CONSULTANT
    )
    repo = CareTeamAssignmentRepository(db_session)

    repo.create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=care_manager.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )
    repo.create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=consultant.provider_id,
            role=CareTeamRole.PSYCHIATRIC_CONSULTANT,
            service_begin_date=date(2026, 1, 1),
        )
    )

    current = repo.list_current_by_patient(patient.patient_id)
    assert {a.role for a in current} == {CareTeamRole.CARE_MANAGER, CareTeamRole.PSYCHIATRIC_CONSULTANT}
