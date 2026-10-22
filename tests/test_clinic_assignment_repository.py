from datetime import date

from app.models.clinic_assignment import ClinicAssignment
from app.models.patient import Patient
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.patient import PatientRepository


def make_patient(db_session, mrn="MRN-CLA-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Clinic Assignment Test Patient",
            payer="Medicaid",
            date_of_birth=date(1990, 6, 15),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 2),
        )
    )


def test_is_primary_defaults_to_false(db_session):
    patient = make_patient(db_session)
    repo = ClinicAssignmentRepository(db_session)

    assignment = repo.create(
        ClinicAssignment(
            patient_id=patient.patient_id,
            clinic_id="clinic-a",
            service_begin_date=date(2026, 1, 1),
        )
    )

    assert assignment.is_primary is False


def test_patient_can_belong_to_more_than_one_clinic_over_time(db_session):
    patient = make_patient(db_session, mrn="MRN-CLA-2")
    repo = ClinicAssignmentRepository(db_session)

    ended = repo.create(
        ClinicAssignment(
            patient_id=patient.patient_id,
            clinic_id="clinic-old",
            is_primary=True,
            service_begin_date=date(2025, 1, 1),
            service_end_date=date(2026, 1, 1),
        )
    )
    current = repo.create(
        ClinicAssignment(
            patient_id=patient.patient_id,
            clinic_id="clinic-new",
            is_primary=True,
            service_begin_date=date(2026, 1, 1),
        )
    )

    assert {a.clinic_assignment_id for a in repo.list_by_patient(patient.patient_id)} == {
        ended.clinic_assignment_id,
        current.clinic_assignment_id,
    }
    current_only = repo.list_current_by_patient(patient.patient_id)
    assert [a.clinic_assignment_id for a in current_only] == [current.clinic_assignment_id]


def test_list_patient_ids_for_clinic_only_considers_current_assignments(db_session):
    patient_repo = PatientRepository(db_session)
    p1 = patient_repo.create(
        Patient(
            mrn="MRN-CLA-3", name="P1", payer="Medicaid", date_of_birth=date(1990, 1, 1),
            consent_date=date(2026, 1, 1), enrollment_date=date(2026, 1, 2),
        )
    )
    p2 = patient_repo.create(
        Patient(
            mrn="MRN-CLA-4", name="P2", payer="Medicaid", date_of_birth=date(1990, 1, 1),
            consent_date=date(2026, 1, 1), enrollment_date=date(2026, 1, 2),
        )
    )
    repo = ClinicAssignmentRepository(db_session)
    # p1 has a current assignment to clinic-a
    repo.create(
        ClinicAssignment(
            patient_id=p1.patient_id, clinic_id="clinic-a", service_begin_date=date(2026, 1, 1),
        )
    )
    # p2's assignment to clinic-a already ended
    repo.create(
        ClinicAssignment(
            patient_id=p2.patient_id, clinic_id="clinic-a",
            service_begin_date=date(2025, 1, 1), service_end_date=date(2026, 1, 1),
        )
    )

    assert repo.list_patient_ids_for_clinic("clinic-a") == [p1.patient_id]
