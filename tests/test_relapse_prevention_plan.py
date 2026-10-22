"""
Relapse Prevention Plan content (Phase 10).

The CTMS's RPP form is a full plan document, not just a date + scores:
four free-text plan fields plus a tri-state confirmation of the patient's
medication list (docs/ctms-reference/README.md). These tests lock in that
the plan content persists on the RPP contact, is retrievable later, and
can't be attached to a non-RPP contact type.
"""

from datetime import date

import pytest

from app.models.enums import (
    ConditionType,
    ContactType,
    MeasureType,
    MedicationConfirmation,
    TreatmentStatusEnum,
)
from app.models.patient import Patient
from app.repositories.contact import ContactRepository
from app.repositories.patient import PatientRepository
from app.repositories.treatment_status import TreatmentStatusRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService


def make_enrolled_patient(db_session, mrn="MRN-RPP-1"):
    patient = PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="RPP Test Patient",
            payer="Medicaid",
            date_of_birth=date(1980, 6, 15),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.DEPRESSION,
    )
    return patient, episode


def test_rpp_plan_content_persists_and_is_retrievable(db_session):
    patient, episode = make_enrolled_patient(db_session)
    service = ContactService(db_session)

    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 6, 1),
        duration_minutes=25,
        notes="RPP session completed.",
        other_treatments="Weekly counseling at Community Counseling Collective",
        personal_warning_signs="Sleeping past noon; skipping walks; avoiding phone calls",
        stress_reduction_plan="Daily 20-minute walk; Saturday hiking group; weekly call with sister",
        additional_comments="Copy of plan given to patient and PCP.",
        medications_confirmation=MedicationConfirmation.CONFIRMED_WITH_PATIENT,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 3}],
    )

    contacts = ContactRepository(db_session).list_by_patient(patient.patient_id)
    rpp = next(c for c in contacts if c.contact_type == ContactType.RELAPSE_PREVENTION_PLAN)
    assert rpp.other_treatments.startswith("Weekly counseling")
    assert "Sleeping past noon" in rpp.personal_warning_signs
    assert "hiking group" in rpp.stress_reduction_plan
    assert rpp.additional_comments == "Copy of plan given to patient and PCP."
    assert rpp.medications_confirmation == MedicationConfirmation.CONFIRMED_WITH_PATIENT
    # The Phase 1 status cascade still fires — plan content didn't disturb it.
    current = TreatmentStatusRepository(db_session).get_current(patient.patient_id)
    assert current.status == TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN


def test_all_three_confirmation_values_round_trip(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-RPP-2")
    service = ContactService(db_session)

    for i, value in enumerate(MedicationConfirmation):
        contact = service.record_contact(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
            contact_date=date(2026, 6, 1 + i),
            duration_minutes=20,
            medications_confirmation=value,
        )
        assert contact.medications_confirmation == value


def test_plan_content_is_optional_on_an_rpp_contact(db_session):
    """A date-only RPP contact stays valid — the CTMS's own minimum."""
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-RPP-3")
    contact = ContactService(db_session).record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 6, 1),
    )
    assert contact.personal_warning_signs is None
    assert contact.medications_confirmation is None


@pytest.mark.parametrize(
    "contact_type",
    [
        ContactType.INITIAL_ASSESSMENT,
        ContactType.FOLLOW_UP,
        ContactType.CONTACT_ATTEMPT,
        ContactType.CARE_TEAM_COLLABORATION,
    ],
)
def test_plan_fields_rejected_on_non_rpp_contacts(db_session, contact_type):
    patient, episode = make_enrolled_patient(db_session, mrn=f"MRN-RPP-{contact_type.value}")
    with pytest.raises(ValueError, match="only apply to a relapse_prevention_plan"):
        ContactService(db_session).record_contact(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_type=contact_type,
            contact_date=date(2026, 6, 1),
            personal_warning_signs="should be rejected",
        )


def test_error_names_every_offending_field(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-RPP-MULTI")
    with pytest.raises(ValueError, match="additional_comments"):
        ContactService(db_session).record_contact(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_type=ContactType.FOLLOW_UP,
            contact_date=date(2026, 6, 1),
            additional_comments="nope",
            other_treatments="also nope",
        )


def test_successive_rpp_contacts_each_carry_their_own_plan_version(db_session):
    """
    An episode can have more than one RPP contact; each keeps that
    session's plan rather than overwriting a single shared record.
    """
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-RPP-4")
    service = ContactService(db_session)

    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 6, 1),
        personal_warning_signs="First version: poor sleep",
        medications_confirmation=MedicationConfirmation.DEFERRED,
    )
    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 7, 1),
        personal_warning_signs="Revised: poor sleep plus social withdrawal",
        medications_confirmation=MedicationConfirmation.CONFIRMED_IN_MEDICAL_RECORD,
    )

    rpps = [
        c
        for c in ContactRepository(db_session).list_by_patient(patient.patient_id)
        if c.contact_type == ContactType.RELAPSE_PREVENTION_PLAN
    ]
    assert len(rpps) == 2
    assert rpps[0].personal_warning_signs.startswith("First version")
    assert rpps[0].medications_confirmation == MedicationConfirmation.DEFERRED
    assert rpps[1].personal_warning_signs.startswith("Revised")
    assert rpps[1].medications_confirmation == MedicationConfirmation.CONFIRMED_IN_MEDICAL_RECORD
