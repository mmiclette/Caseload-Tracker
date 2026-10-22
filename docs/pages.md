# Screens — what each page is for

Every page in `frontend/src/pages/`, what it does, and why it exists.
Written for someone deciding what to change, so each entry says what the
screen is *for* rather than just what's on it, and calls out the design
decisions that aren't obvious from looking at it.

Seventeen page components; sixteen routes. Login isn't routed — `App.tsx`
renders it whenever there's no authenticated provider, so it has no URL.

Verified against `frontend/src/App.tsx` on 2026-09-17.

---

## Navigation at a glance

```
Login  (no route — shown whenever unauthenticated)
│
└─ AppShell  (sidebar + patient search + signed-in provider)
   │
   ├─ CASELOAD
   │  ├─ /reminders ................ Reminders          ← landing page
   │  ├─ /patients ................. Active Patients    ← the caseload list
   │  └─ /patients/inactive ........ Inactive Patients
   │
   ├─ /patients/new ................ Patient Enrollment  (sidebar CTA)
   │
   ├─ /patients/:id ................ Clinical Dashboard  ← the patient hub
   │  ├─ /patients/:id/contacts .......... Treatment History
   │  ├─ /patients/:id/contacts/new ...... Record a Contact
   │  ├─ /patients/:id/consultations/new . Psychiatric Consultation Note
   │  ├─ /patients/:id/medications ....... Medications
   │  ├─ /patients/:id/profile ........... Patient Profile
   │  └─ /patients/:id/deactivate ........ Deactivation
   │
   └─ REPORTS
      ├─ /reports/caseload-statistics
      ├─ /reports/quality-metrics
      ├─ /reports/completed-episodes
      ├─ /reports/drr
      └─ /reports/time-tracker
```

`/` and any unknown path redirect to `/reminders`. The Clinical Dashboard
is the hub: almost every patient-level action is reached from it.

---

## Entry and chrome

### Login — *no route*
**For:** anyone opening the app.
**Does:** email + password against `POST /auth/login`, returns a JWT.
**Intent:** a deliberate front door for an internal clinical tool, carrying
the PHI access notice.

The JWT lives in **module memory only** — never localStorage or
sessionStorage. The PHI rule forbids persisting patient data client-side,
and the credential that unlocks it gets the same treatment. Two visible
consequences, both intended: a page reload returns here, and any 401 from
any request drops straight back here so the UI can never sit
half-authenticated.

### AppShell — *wraps every authenticated route*
**Does:** the left sidebar (Caseload group, Reports group), the patient
search box, the signed-in provider's name and role, sign out, and the
"+ New patient" CTA.
**Intent:** the CTMS's information architecture — its `Patient` /
`Caseload` / `Tools` dropdown menus — presented as a sidebar. This is the
one deliberate structural deviation from the CTMS, taken because the brief
asks for contemporary-SaaS execution. It's confined to
`components/AppShell.tsx`, so reverting to dropdowns is a single-file
change.

Patient search matches name, patient ID, or MRN. It currently filters
client-side over `GET /patients?limit=500` because the API has no search
endpoint — fine at one program's caseload size, and the obvious place to
add `?q=` when it isn't.

---

## Daily workflow

### Reminders — `/reminders`
**For:** the BHCM, first thing. This is the landing page.
**Does:** every pending reminder in due-date order, with a days-until or
days-overdue readout, the patient, the reminder type, and a "Record
contact" shortcut. Sortable by due date, patient, or type.
**Intent:** the AIMS guide's whole rationale for this screen is "patients
that are due for an appointment or who may require more intensive efforts
to engage them in care." It's a worklist, not a dashboard — the actionable
number is how late something is, so overdue rows are called out in red.

Nothing polls. "Overdue" is computed at render time by comparing `due_date`
to today, and the due dates themselves are recomputed server-side whenever
a contact is recorded, an episode opens, or an episode closes.

### Active Patients — `/patients`
**For:** the BHCM scanning their caseload; the supervisor covering someone
else's.
**Does:** one row per patient with an open episode. The confirmed CTMS
column order: Flags, Patient ID, MRN, Name, Age, Status, Meds, then grouped
PHQ-9 / GAD-7 / PCL-5 first+last, then the Contacts group (I/A, F/U, P/C,
R/P), then # Sessions, Weeks since I/A, and Minutes This Month. Every
column sorts. Filters by payer, clinic, and "Report for" provider.
**Intent:** the AIMS guide's caseload-level report — the screen that
answers "who needs attention today," which is why it defaults to sorting
by flags.

Three interaction details carried over from the CTMS:
- a **service date is a link** into Treatment History, deep-linked to that
  date (`?on=`), which auto-expands that encounter;
- an **empty date cell offers a green (+)** that jumps to the contact form
  pre-set to that contact type;
- the P/C column shows **`CONSIDER`** while a patient is flagged and not
  yet reviewed, rather than a date.

Every cell indicator — the 30-day staleness asterisk, the grey
single-score rule, the PHQ-9 red/amber/green — arrives precomputed from the
API. The frontend only paints. GAD-7 and PCL-5 render uncoloured on
purpose: their colour rules were never documented, and reusing PHQ-9's
thresholds on a scale they weren't validated against would be inventing a
clinical cut-off.

### Inactive Patients — `/patients/inactive`
**For:** finding someone who completed care, usually to bring them back.
**Does:** lists patients with their enrollment date, deactivation date, and
last episode outcome, plus a **Re-enroll** action.
**Intent:** the CTMS keeps deactivated patients visible on a separate list
rather than deleting them, and they can return at any time.

Two things worth knowing. The list is **derived** — it's every patient
*not* on the Active Patients report, which is that report's own exclusion
rule, so the two lists partition the roster without asking the backend the
same question twice. And re-enrolling opens a **new episode**, never
reopens the old one, per the AIMS rule that a returning patient is measured
from a new baseline. That's why a re-enrolled patient reappears on the
caseload with no scores and zero sessions.

---

## The patient record

### Clinical Dashboard — `/patients/:patientId`
**For:** everything about one patient. The hub.
**Does:** a left rail — Customize Dashboard View toggles, Flags, Last
Contact, Next Appointment, Status — beside a main column of cards:
- **Clinical Measures** — one trend chart per treated diagnosis, primary
  first, each with baseline → latest → change, response/remission badges,
  and the score series plotted against *weeks in treatment* (not calendar
  dates), which is how the CTMS plots it and what keeps episodes
  comparable.
- **Patient Information** — enrollment, demographics, current providers,
  current clinics.
- **Medications**, **Patient Profile**, **Psychiatric Consultant**,
  **Treatment History**, **Episode History**.

**Intent:** the single-patient view a BHCM opens after spotting someone on
the caseload list. The trend charts sit at the top because "is this patient
getting better" is the question the screen exists to answer.

Two design points: the **Customize Dashboard View** toggles are purely a
frontend concern — the endpoint always returns every section and this page
decides what to render, exactly as the CTMS behaves. And the page
**composes four endpoints** (dashboard, contacts, consultations,
reminders), because the dashboard report doesn't include the last three;
that's what powers Treatment History and the Next Appointment rail item
without a backend change.

### Treatment History — `/patients/:patientId/contacts`
**For:** reading what actually happened at a visit.
**Does:** every contact and case review merged into one chronological list,
each expandable to its full record — the scores collected, the encounter
note, the notes for the consultant, and the RPP plan block.
**Intent:** the dashboard lists these compactly; this is where you open
one.

Scores load only when a row is expanded, so the list stays a single
request. Arriving with `?on=<date>` auto-expands that row — which is what
makes the caseload list's service dates worth being links.

### Medications — `/patients/:patientId/medications`
**For:** maintaining the medication list.
**Does:** search-as-you-type over the vendored behavioural-health catalogue.
Picking a drug turns the dose field into a dropdown of that drug's **real
FDA strengths** (Bupropion XL → 150/300/450 mg). Stop a medication with an
optional reason, restart it (which clears the reason), or edit a dose
inline.
**Intent:** the AIMS guide lists medications on the patient summary and
"whether psychotropic medications are prescribed" on the caseload. The
catalogue picker exists so that column can mean something.

A name with no catalogue match still saves, as free text — and the form
says plainly that it **won't** count toward the psychotropic column, since
an unclassifiable entry can't be counted. That's an assumption surfaced to
the user rather than buried.

### Patient Profile — `/patients/:patientId/profile`
**For:** the narrative context that isn't a score — behavioural health,
medical, safety and risk, substance use, social and environmental, plus
allergies.
**Does:** click a sub-field, add a dated value with optional context.
**Intent:** the click-to-add model from the 2026-08 profile design.

The table is **append-only**, and the UI makes that explicit rather than
merely enforcing it: there are no edit or delete controls, the button says
"Update", and it states that the existing value becomes history. Prior
values collapse into per-field history.

Each section states its own guardrail on screen: Current Medications offers
only allergies/intolerances (medications are real Medication rows), Safety
& Risk entries never touch the red safety flag, and Behavioural Health has
no diagnoses or severity field because those live on the episode and the
score.

---

## Write actions

### Patient Enrollment — `/patients/new`
**For:** getting a consented patient into the registry.
**Does:** Program Information, Demographic Information, and an Episode of
Care section, then one submit.
**Intent:** the CTMS's enrollment form.

That single submit is **four API calls in dependency order** — patient,
episode, care team, clinic — because the API has no transactional
enrollment endpoint. A mid-sequence failure reports honestly and names the
patient ID that was created, rather than attempting client-side rollback.
If that becomes a real problem, the fix is a server-side enrollment
service, not compensation logic here.

Three fields the CTMS doesn't show on this screen are required because the
model requires them: payer, consent date, and a **primary diagnosis** — the
last because it pins which measure the patient's outcome reporting tracks,
so collecting it at enrollment prevents episodes that can never report.

### Record a Contact — `/patients/:patientId/contacts/new`
**For:** the BHCM after a visit. The app's main write path.
**Does:** contact type and date, scale entry, the discuss-with-consultant
checkbox, the encounter note, and the session footer — all in one save.
**Intent:** mirrors the CTMS's contact form, which saves the visit date,
every scale, and the consultant checkbox together.

One save is structural, not cosmetic: `POST /contacts` accepts all of it in
a single call, and splitting it would bypass the server-side cascades that
call triggers — baseline recompute, the RPP status transition, the yellow
flag, attempt numbering.

- **Scale matrices with auto-totals** for PHQ-9 and GAD-7, with the
  functional-impairment question shown but badged "not included in the
  total". **Direct total entry** overrides the computed total, and is the
  only mode for PCL-5 / SCARED / SMFQ / Vanderbilt — whose item wording we
  deliberately don't ship, because transcribing a validated instrument from
  a low-resolution frame risks altering it.
- **Carry-forward selection**: the measures from the patient's last scored
  contact come pre-checked, falling back to the episode's diagnoses.
- An incomplete scale **isn't submitted**, and says so.
- The **RPP plan block** appears only for a relapse prevention plan,
  matching the server's own rejection rule.
- Contact attempt and care team collaboration hide the scale and consultant
  sections entirely and explain their reporting semantics.
- `?type=` preselects the contact type (that's what the caseload's green +
  passes); `?on=` preselects the date.

### Psychiatric Consultation Note — `/patients/:patientId/consultations/new`
**For:** the psychiatric consultant at systematic caseload review — or the
BHCM recording it on their behalf.
**Does:** date, consultant, findings and recommendations, the
recommendations-forwarded and flag-for-next-review checkboxes, and minutes.
**Intent:** the CTMS's own layout, including the **read-only replay of the
care manager's comments** from the flagging contact, so the consultant sees
the question they're answering.

Saving clears the patient's yellow flag — unless "flag for next review" is
checked, which immediately re-sets it, because "we reviewed this today" and
"review this again next time" are different things. No location control:
a Consultation isn't a Contact and has no location column.

### Deactivation — `/patients/:patientId/deactivate`
**For:** closing out a patient who finished, disengaged, or left.
**Does:** a deactivation date and an optional reason.
**Intent:** the CTMS files this under "New Contact", but it isn't a contact
in this data model — setting `end_date` is what the server treats as
deactivation.

The form makes **one PATCH** and lets `EpisodeService` cascade the rest:
treatment status to deactivated, and the pending appointment reminder
dismissed. It states plainly that the end reason is a *deactivation*
reason, not a clinical outcome — "achieved goals" says why treatment
stopped, not that the patient improved.

---

## Reports

All five carry an on-screen **"How this is calculated"** note, because each
one has an assumption or an unmeasurable metric that a bare number would
misrepresent.

### Caseload Statistics — `/reports/caseload-statistics`
**Answers:** how is each care manager's caseload doing right now?
One row per provider or clinic, over currently open episodes only: caseload
size, patients with a contact, average visits, % of contacts with a scale,
number in relapse prevention, number flagged, number with a consultation,
and **"not improving without a P/C"** (not responding *and* not reviewed in
the past two months). Then average first and latest PHQ-9 and GAD-7, and
outcome rates — combined first, then depression and anxiety.

Defaults to **care managers only**. Showing every role at once makes each
patient appear under their care manager, consultant, *and* PCP, so the
summary row would count them three times; picking "All roles" removes the
total row and explains why.

### CoCM Quality Metrics — `/reports/quality-metrics`
**Answers:** is the program improving over time? Twelve rows, one per
month, rolling back from the current month.

Two deliberate refusals to show a number: **Caseload Reach reads "n/a"**
because it needs a count of *eligible* patients and the registry only holds
enrolled ones; and the four unconfirmed-threshold measures (PTSD,
paediatric anxiety/depression/ADHD) show **"no threshold"** beside a real
denominator instead of 0%, because a bare 0% would read as a programme
failing at PTSD care.

### Completed Episodes — `/reports/completed-episodes`
**Answers:** what happened to the patients who finished? Pick a year; the
cohort is every episode closed in it. Stat tiles, outcomes at close, and a
breakdown of why episodes ended — including a **"not recorded"** bucket,
kept visible as a data-quality signal rather than dropped.

### DRR Report — `/reports/drr`
**Answers:** how do we look on the HEDIS-style depression measure? One row
per clinic: follow-up PHQ-9 completion, remission, and response.

**All three rates share one denominator** — the full eligible cohort — so a
missed follow-up counts against remission and response too. That's how real
HEDIS DRR works and what makes the completion rate meaningful on its own.
It will be **empty for the current year until September**, because a
baseline set in January plus an 8-month window lands in September; the
empty state explains this rather than showing a blank table.

### Monthly Time Tracker — `/reports/time-tracker`
**Answers:** how many minutes of service per patient? One row per patient,
thirteen month columns, with an all-patients total.

Minutes include care-manager contacts (care team collaboration among them)
plus psychiatric consultations; contact attempts are excluded because
outreach that never reached the patient isn't service time. Labelled
**recorded** minutes, never billable — the CTMS's own material is explicit
that without EHR integration it can't distinguish the two, and that call
stays with the provider.

---

## Known gaps

- **No frontend tests.** Verified by typecheck and manual browser
  walkthroughs; nothing repeatable by anyone else.
- **Patient search, payer filter, and clinic filter** are client-side or
  free-text because no endpoint backs them.
- **Responsive defect** around 800px: the top-bar user block wraps into its
  own label and table action buttons clip.
- Screens the CTMS has that no API backs yet — Problem List, Appointments,
  Current Concerns, and per-section "last updated by" provenance. The audit
  log (Phase 13) now makes that last one buildable.
