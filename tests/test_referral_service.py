from datetime import date

from app.models.enums import ProviderRole, ReminderType
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository
from app.repositories.reminder import ReminderRepository
from app.services.referral_service import ReferralService


def make_patient(db_session, mrn="MRN-REF-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Referral Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_record_referral_creates_referral_and_linked_reminder(db_session):
    patient = make_patient(db_session)
    care_manager = ProviderRepository(db_session).create(
        Provider(name="Referring CM", role=ProviderRole.CARE_MANAGER)
    )
    service = ReferralService(db_session)

    referral = service.record_referral(
        patient_id=patient.patient_id,
        referral_date=date(2026, 2, 1),
        referred_by_provider_id=care_manager.provider_id,
        referred_to="Community Housing Program",
        reason="Housing instability",
    )

    assert referral.referral_id is not None
    assert referral.referred_to == "Community Housing Program"
    assert referral.referred_by_provider_id == care_manager.provider_id

    reminders = ReminderRepository(db_session).list_by_patient(patient.patient_id)
    referral_reminder = next(r for r in reminders if r.reminder_type == ReminderType.REFERRAL_FOLLOWUP)

    assert referral_reminder.referral_id == referral.referral_id
    assert referral_reminder.due_date == date(2026, 3, 1)  # 2026-02-01 + 28 days
    assert referral_reminder.notes == "Housing instability"


def test_referral_without_a_referring_provider_is_allowed(db_session):
    """An external referral doesn't necessarily originate from this CoCM team."""
    patient = make_patient(db_session, mrn="MRN-REF-2")
    service = ReferralService(db_session)

    referral = service.record_referral(patient_id=patient.patient_id, referral_date=date(2026, 3, 1))

    assert referral.referred_by_provider_id is None
