"""
Shared enums for the registry.

These are stored with SQLAlchemy's Enum(..., native_enum=False), which
persists the value as a plain VARCHAR with a CHECK constraint on Postgres
and a plain VARCHAR on Snowflake (which has no native enum type). Using a
native Postgres ENUM type here would break portability to Snowflake.
"""

from enum import Enum


class MeasureType(str, Enum):
    """
    Validated symptom measures, confirmed against the AIMS Caseload Tracker
    (CTMS) walkthrough. PHQ9 and GAD7 have defined remission/response rules
    in app/services/scoring.py. PCL5, SCARED, SMFQ, and VANDERBILT are
    tracked by the CTMS (PTSD, and pediatric anxiety/depression/ADHD
    respectively) but the CTMS walkthrough never stated their numeric
    thresholds — see the "Open question" note in CLAUDE.md. Do not invent
    thresholds for them; the scoring service intentionally leaves them
    unscored (is_remission=False, is_response=False) until AIMS confirms
    the real numbers.
    """

    PHQ9 = "PHQ9"
    GAD7 = "GAD7"
    PCL5 = "PCL5"
    SCARED = "SCARED"
    SMFQ = "SMFQ"
    VANDERBILT = "VANDERBILT"
    OTHER = "OTHER"


class EndReason(str, Enum):
    """
    Why an episode of care ended — this is a deactivation reason, not a
    clinical outcome. Values match the CTMS's Completed Episode Statistics
    report exactly. Remission/response/improvement are computed outcomes
    (see app/services/scoring.py), never stored here.
    """

    ACHIEVED_GOALS = "achieved_goals"
    NOT_ENGAGED = "not_engaged"
    PATIENT_CHOICE = "patient_choice"
    PATIENT_NO_LONGER_AVAILABLE = "patient_no_longer_available"
    PATIENT_DIED = "patient_died"
    PATIENT_DIED_BY_SUICIDE = "patient_died_by_suicide"
    OTHER = "other"


class TreatmentStatusEnum(str, Enum):
    """The three treatment-status values a patient can be in."""

    ACTIVE_TREATMENT = "active_treatment"
    RELAPSE_PREVENTION_PLAN = "relapse_prevention_plan"
    DEACTIVATED = "deactivated"


class ContactType(str, Enum):
    """
    Which kind of visit a Contact represents. CONTACT_ATTEMPT is outreach
    that didn't result in a completed session — it never carries Symptom
    Scores and never affects an episode's baseline. The other three do
    (via ContactService.record_contact), and RELAPSE_PREVENTION_PLAN also
    cascades a Treatment Status transition — see CLAUDE.md.

    This enum lived directly on SymptomScore in Phase 1, as an interim
    bridge before Contact existed (with CONTACT_ATTEMPT deliberately
    excluded then, since attempts never produced a score). Now that
    Contact exists, SymptomScore references a Contact by contact_id
    instead, and this enum moved onto Contact in full, including
    CONTACT_ATTEMPT.
    """

    INITIAL_ASSESSMENT = "initial_assessment"
    FOLLOW_UP = "follow_up"
    RELAPSE_PREVENTION_PLAN = "relapse_prevention_plan"
    CONTACT_ATTEMPT = "contact_attempt"
    # BHCM activity about the patient without the patient present (the
    # CTMS's "care team collaboration/no contact", Phase 9 — it appears in
    # both CTMS versions' Patient menus). Carries billable
    # duration_minutes (Minutes This Month / Time Tracker count it, per
    # the CTMS tooltip) but is NOT a patient encounter: it never carries
    # scores, doesn't count as a session or as engagement, doesn't reset
    # the contact-attempt counter, and doesn't reset the reminder cadence
    # clock.
    CARE_TEAM_COLLABORATION = "care_team_collaboration"


class ProviderRole(str, Enum):
    """
    A Provider's account type, matching the CTMS's account types exactly
    (the video: "There are different account types for behavioral health
    providers, psychiatric consultants, clinic supervisors, and data
    analysts"). This is broader than CareTeamRole below — clinic
    supervisors and data analysts have registry accounts but never appear
    on a patient's care team.
    """

    CARE_MANAGER = "care_manager"
    PRIMARY_CARE_PROVIDER = "primary_care_provider"
    PSYCHIATRIC_CONSULTANT = "psychiatric_consultant"
    CLINIC_SUPERVISOR = "clinic_supervisor"
    DATA_ANALYST = "data_analyst"


class CareTeamRole(str, Enum):
    """
    The role a Provider plays on a specific patient's care team — the
    Clinical Dashboard's "Current Providers" table only ever shows these
    three, never clinic_supervisor or data_analyst (see ProviderRole).
    """

    CARE_MANAGER = "care_manager"
    PRIMARY_CARE_PROVIDER = "primary_care_provider"
    PSYCHIATRIC_CONSULTANT = "psychiatric_consultant"


class ReminderType(str, Enum):
    """
    What a Reminder is nudging a Care Manager to do. appointment covers
    both the initial-assessment-scheduling reminder (within 7 days of
    enrollment) and the ongoing follow-up cadence reminder (every 2 weeks
    in active_treatment, every 4 weeks in relapse_prevention_plan) — the
    CTMS's Reminders page doesn't visually distinguish these, they're both
    "this patient is due for outreach." referral_followup is the separate
    4-weeks-after-a-referral reminder described in CLAUDE.md.
    """

    APPOINTMENT = "appointment"
    REFERRAL_FOLLOWUP = "referral_followup"


class ReminderStatus(str, Enum):
    """
    Placeholder values, not confirmed against the CTMS walkthrough — the
    source material never showed the Reminders page's own status/dismiss
    controls in enough detail to confirm an exact status vocabulary. Same
    "flag it, don't invent it as fact" treatment as ContactLocation: pending
    (the default, still due), completed (the outreach happened), and
    dismissed (a Care Manager explicitly cleared it without a contact, e.g.
    the patient was already reached another way) are a reasonable manual-
    override set, not a confirmed list.
    """

    PENDING = "pending"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class AuditAction(str, Enum):
    """
    What kind of change an AuditLog row describes.

    CLAUDE.md's PHI rule requires an audit entry for every write to patient
    status, a flag, or a score. STATUS_CHANGED, FLAG_SET/FLAG_CLEARED and
    SCORE_RECORDED cover exactly those three. The episode and patient
    lifecycle actions are included because closing an episode IS a status
    change in effect (it cascades one), and because deactivating a patient
    or editing their demographics are PHI writes a reviewer will expect to
    find in the same trail.
    """

    STATUS_CHANGED = "status_changed"
    FLAG_SET = "flag_set"
    FLAG_CLEARED = "flag_cleared"
    SCORE_RECORDED = "score_recorded"
    EPISODE_OPENED = "episode_opened"
    EPISODE_CLOSED = "episode_closed"
    PATIENT_DEACTIVATED = "patient_deactivated"
    PATIENT_UPDATED = "patient_updated"


class MedicationConfirmation(str, Enum):
    """
    How a patient's current medication list was verified during a contact —
    the CTMS's Relapse Prevention Plan form has exactly these three
    mutually-exclusive checkboxes above its Current Medications table
    (docs/ctms-reference/README.md, Matt-supplied screenshots). Unlike
    ContactLocation and ReminderStatus, this vocabulary IS confirmed: the
    screenshot shows all three options with their exact labels.
    """

    CONFIRMED_WITH_PATIENT = "confirmed_with_patient"
    CONFIRMED_IN_MEDICAL_RECORD = "confirmed_in_medical_record"
    DEFERRED = "deferred"


class ConditionType(str, Enum):
    """
    The condition an Episode of Care is treating — set as a primary (and
    optionally secondary) diagnosis on the episode, per the 2026-08
    patient-profile design: the primary diagnosis is what caseload
    response/remission reporting tracks (via CONDITION_MEASURES in
    app/services/scoring.py — anxiety-primary patients are measured on
    GAD-7, depression-primary on PHQ-9), and each diagnosis gets a measure
    trend graph at the top of the Clinical Dashboard.

    SUBSTANCE_USE has no mapped measure yet — AUDIT-C and DAST-10 aren't
    MeasureTypes until the profile design's "Bucket A" work lands — so a
    substance_use diagnosis currently produces no trend graph and no
    response/remission metric. That's a known gap, not a bug.
    """

    DEPRESSION = "depression"
    ANXIETY = "anxiety"
    PTSD = "ptsd"
    ADHD = "adhd"
    SUBSTANCE_USE = "substance_use"


class ProfileSection(str, Enum):
    """
    Patient-profile sections whose content lives in ProfileEntry (the
    "Bucket B" sections of the 2026-08 patient-profile design): free-form,
    date-stamped, append-only entries. The other profile sections from that
    design render from real entities instead — Outcome Measures from
    SymptomScore, Current Medications from Medication, Care Team from
    CareTeamAssignment — and must never get free-text twins here.
    CURRENT_MEDICATIONS appears in this enum only for the
    allergies/intolerances sub-field, which has no home on the Medication
    entity; the medications themselves are never ProfileEntry rows.

    Vitals & Monitoring and Laboratory Results ("Bucket C") are not here
    yet — they'll join this enum when built, with numeric-aware columns.
    """

    BEHAVIORAL_HEALTH = "behavioral_health"
    CURRENT_MEDICATIONS = "current_medications"
    MEDICAL_PROFILE = "medical_profile"
    SAFETY_AND_RISK = "safety_and_risk"
    SUBSTANCE_USE = "substance_use"
    SOCIAL_ENVIRONMENTAL = "social_environmental"


class ContactLocation(str, Enum):
    """
    Where a contact happened — the CTMS's "This session was ___" dropdown.
    No longer a placeholder: Matt confirmed the three values on 2026-08-07
    as phone, in-clinic, and virtual (Phase 11, renamed from Phase 2's
    provisional in_person/phone/video). The CTMS's own screenshots show
    "in clinic" and "by phone" verbatim; "virtual" is Matt's confirmed
    term for the telehealth option.

    Note the Psychiatric Consultation Note's session footer shows a
    consultation-specific option ("case review with CM") that isn't part of
    this enum — a Consultation isn't a Contact and has no location column.
    """

    PHONE = "phone"
    IN_CLINIC = "in_clinic"
    VIRTUAL = "virtual"
