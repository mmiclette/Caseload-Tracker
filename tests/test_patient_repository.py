from datetime import date, timedelta

from app.models.clinic_assignment import ClinicAssignment
from app.models.patient import Patient
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.patient import PatientRepository


def make_patient(**overrides):
    defaults = dict(
        mrn="MRN-0001",
        name="Jane Doe",
        payer="Medicaid",
        program_eligibility={"integrated_care": True},
        date_of_birth=date(1990, 6, 15),
        consent_date=date(2026, 1, 5),
        enrollment_date=date(2026, 1, 6),
    )
    defaults.update(overrides)
    return Patient(**defaults)


def test_create_and_get_by_id(db_session):
    repo = PatientRepository(db_session)
    created = repo.create(make_patient())

    assert created.patient_id is not None
    fetched = repo.get_by_id(created.patient_id)
    assert fetched is not None
    assert fetched.mrn == "MRN-0001"
    assert fetched.name == "Jane Doe"


def test_get_by_id_missing_returns_none(db_session):
    repo = PatientRepository(db_session)
    assert repo.get_by_id(999_999) is None


def test_get_by_mrn_is_case_insensitive(db_session):
    repo = PatientRepository(db_session)
    repo.create(make_patient(mrn="MrN-0002"))

    found = repo.get_by_mrn("mrn-0002")
    assert found is not None
    assert found.mrn == "MrN-0002"


def test_list_by_clinic_filters_correctly(db_session):
    """
    Phase 2 replaced Patient.clinic_id with the Clinic Assignment table (a
    patient can belong to more than one clinic over time) — see
    ClinicAssignmentRepository.list_patient_ids_for_clinic. PatientRepository
    .list_by_clinic now joins through that table and only considers current
    (service_end_date IS NULL) assignments.
    """
    patient_repo = PatientRepository(db_session)
    assignment_repo = ClinicAssignmentRepository(db_session)

    p1 = patient_repo.create(make_patient(mrn="MRN-1"))
    p2 = patient_repo.create(make_patient(mrn="MRN-2"))
    p3 = patient_repo.create(make_patient(mrn="MRN-3"))

    assignment_repo.create(
        ClinicAssignment(
            patient_id=p1.patient_id, clinic_id="clinic-a", is_primary=True,
            service_begin_date=date(2026, 1, 1),
        )
    )
    assignment_repo.create(
        ClinicAssignment(
            patient_id=p2.patient_id, clinic_id="clinic-b", is_primary=True,
            service_begin_date=date(2026, 1, 1),
        )
    )
    assignment_repo.create(
        ClinicAssignment(
            patient_id=p3.patient_id, clinic_id="clinic-a", is_primary=True,
            service_begin_date=date(2026, 1, 1),
        )
    )

    clinic_a_patients = patient_repo.list_by_clinic("clinic-a")
    assert {p.mrn for p in clinic_a_patients} == {"MRN-1", "MRN-3"}


def test_update_changes_fields_and_bumps_updated_at(db_session):
    repo = PatientRepository(db_session)
    patient = repo.create(make_patient(mrn="MRN-4"))
    original_updated_at = patient.updated_at

    updated = repo.update(patient, payer="Medicare", deactivation_date=date(2026, 6, 1))

    assert updated.payer == "Medicare"
    assert updated.deactivation_date == date(2026, 6, 1)
    assert updated.updated_at >= original_updated_at


def test_list_respects_limit_and_offset(db_session):
    repo = PatientRepository(db_session)
    for i in range(5):
        repo.create(make_patient(mrn=f"MRN-PAGE-{i}"))

    page1 = repo.list(limit=2, offset=0)
    page2 = repo.list(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {p.patient_id for p in page1}.isdisjoint({p.patient_id for p in page2})


def test_flags_default_to_off(db_session):
    repo = PatientRepository(db_session)
    patient = repo.create(make_patient(mrn="MRN-FLAGS-1"))

    assert patient.needs_psychiatric_review is False
    assert patient.safety_risk is False
    assert patient.custom_flag_active is False
    assert patient.custom_flag_label is None


def test_flags_can_be_set_and_updated(db_session):
    repo = PatientRepository(db_session)
    patient = repo.create(make_patient(mrn="MRN-FLAGS-2"))

    updated = repo.update(
        patient,
        needs_psychiatric_review=True,
        safety_risk=True,
        custom_flag_active=True,
        custom_flag_label="Housing instability",
    )

    assert updated.needs_psychiatric_review is True
    assert updated.safety_risk is True
    assert updated.custom_flag_active is True
    assert updated.custom_flag_label == "Housing instability"


def test_race_ethnicity_is_optional_and_multi_select(db_session):
    repo = PatientRepository(db_session)
    with_selection = repo.create(
        make_patient(mrn="MRN-RE-1", race_ethnicity=["asian", "white"])
    )
    without_selection = repo.create(make_patient(mrn="MRN-RE-2"))

    assert with_selection.race_ethnicity == ["asian", "white"]
    assert without_selection.race_ethnicity is None


def test_age_is_computed_from_date_of_birth_not_stored(db_session):
    repo = PatientRepository(db_session)
    today = date.today()

    just_had_birthday = repo.create(
        make_patient(
            mrn="MRN-AGE-1",
            date_of_birth=date(today.year - 30, today.month, today.day),
        )
    )
    birthday_not_yet_this_year = repo.create(
        make_patient(
            mrn="MRN-AGE-2",
            date_of_birth=(
                date(today.year - 30, today.month, today.day) + timedelta(days=1)
            ),
        )
    )

    assert just_had_birthday.age == 30
    assert birthday_not_yet_this_year.age == 29
