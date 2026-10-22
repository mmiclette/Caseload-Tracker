# CTMS Design Reference (AIMS Caseload Tracker demo)

Extracted 2026-08-07 from the AIMS Center's "AIMS Caseload Tracker: Demo"
video (https://youtu.be/dcRPqgwoCa0, 15:44, 720p) — the same walkthrough
CLAUDE.md's data model was built from. `frame_MMmSSs.png` files are distinct
frames (2-second sampling, difference-threshold dedupe); `sheet_NN.png`
files are labeled contact sheets of the same frames, nine per sheet.

These frames are the layout source of truth for the frontend build,
alongside any higher-resolution screenshots Matt supplies. Per CLAUDE.md:
same data, same columns, same report structure — modern visual execution
with the NeuroFlow palette instead of the CTMS's dated green-on-white.

## Screen map (timestamp → screen)

| Time | Screen | Canonical frames |
|---|---|---|
| 02:03–02:09 | Login page | frame_02m03s |
| 02:11 | **Reminders** (BHCM landing page after login) | frame_02m11s |
| 03:11–07:03 | **Active Patients** caseload list (04:57 shows pediatric SCARED/SMFQ columns — measure columns are org-configurable) | frame_03m13s, frame_04m57s, frame_07m03s |
| 07:19–07:55 | **Patient Enrollment** form, then saved read view | frame_07m39s, frame_07m43s |
| 07:59–08:59 | **Initial Assessment** contact form (scale-driven entry) | frame_08m13s, frame_08m27s, frame_08m57s |
| 09:01 | **Follow Up** contact form (same layout as Initial Assessment) | frame_09m01s |
| 09:21 | **Relapse Prevention Plan** contact form | frame_09m21s |
| 09:41 | **Deactivation** form | frame_09m41s |
| 09:49–09:55 | **Inactive Patients** list + Caseload menu open (report list) | frame_09m49s, frame_09m55s |
| 10:17 | **Psychiatric Consultation** form | frame_10m17s |
| 11:11–11:33 | **Clinical Dashboard** (sidebar + cards + PHQ-9 graph + treatment history) | frame_11m11s, frame_11m27s, frame_11m31s, frame_11m33s |
| 11:43–12:31 | **Caseload Statistics** report | frame_11m45s, frame_12m31s |
| 12:43–13:17 | **CoCM Quality Metrics** report (monthly columns) | frame_12m45s, frame_13m17s |
| 13:21–13:23 | **Completed Episode Statistics** report | frame_13m23s |
| 13:55–13:57 | **DRR Report** | frame_13m57s |
| 14:21 | **Monthly Time Tracker** report | frame_14m21s |

Everything before 02:03 and after 14:59 is slideware (intro, account roles,
training resources), not product UI.

## Global UI patterns observed

- **App chrome**: dark navy top bar — Home icon; `Patient ▾`, `Caseload ▾`,
  `Tools ▾` dropdown menus; centered patient search box ("Patient: ID,
  Name, MRN"); right side "Hello, {user}", Help, Logout. The `Patient ▾`
  menu holds per-patient actions (New Patient, New Contact ▸ Initial
  Assessment / Follow-Up / Psychiatric Consultation / Relapse Prevention
  Plan / Deactivation, Contact Attempt, Care Team Collaboration, Treatment
  History, Clinical Dashboard, Search Patient); the `Caseload ▾` menu holds
  the lists and reports (Active Patients, Inactive Patients, Caseload
  Statistics, Completed Episode Statistics, CoCM Quality Metrics, DRR
  Report, Monthly Time Tracker, Custom Search).
- **Page title band**: full-width navy bar with white page title. On
  patient screens, a top-right patient-context card (Name | Status /
  Patient ID / MRN / Age / DOB). On reports, a top-right card with
  "Export for:" dropdown and "Report Created on:" timestamp.
- **Tables**: dense, striped (white / pale green), pale-green header rows
  with sort arrows, per-page selector and pager bottom-right. Red text for
  overdue dates and "CONSIDER"; small green/red circular icon-links jump
  to per-patient actions. Grouped super-headers (PHQ-9 / GAD-7 / PCL-5
  each spanning First+Last; "Contacts" spanning I/A, F/U, P/C, RPP).
- **Forms**: gray/green section-band headers (Program Information,
  Demographic Information, Providers); two-column field layout; small
  blue Add/Cancel buttons; inline "today" quick-fill next to date fields;
  race/ethnicity is a "Select all that apply" multi-select list.
- **Scale entry** (contact forms): checkboxes choose which measures show
  (chosen measures carry forward to next contact); each scale is a
  question matrix — highlighted question column, radio columns scored
  0–3, auto-calculated total in the scale header (total can also be typed
  directly), History button per scale. "Discuss with Psychiatric
  Consultant" checkbox + notes textarea at the bottom of contact forms,
  followed by contact metadata (duration, location, etc.).
- **Clinical Dashboard**: left sidebar of small panels ("Customize
  Dashboard View" checkbox list controlling section visibility, Reminders,
  Last Contact, Flags, Status) + main column of cards: Patient
  Information, Current Providers, Current Clinics, Clinical Measures
  (score line-graph plotted against weeks in treatment, with the scale's
  question matrix below), Psychiatric Consultant, Treatment History table
  (Date, Type, Weeks in Tx, Location, Minutes, PHQ-9, GAD-7, PCL-5).
- **Reports**: same navy title band + export card; a "Report is being
  generated. Please, wait." interstitial; monthly reports use one column
  per month, oldest left; each report footer carries methodology notes.

## Matt-supplied annotated screenshots (2026-08-07, older purple-theme CTMS)

Matt provided annotated training-deck screenshots of an earlier CTMS
version (purple title bands, gray menu bar). Style is NOT to be copied —
the standing instruction remains modern execution with the NeuroFlow
palette — but the interaction details and column semantics below are
confirmed product behavior the frontend must reproduce:

- **Nav structure (older version)**: `Caseload ▾` → Caseload Lists ▸ (New
  Patients / Active Patients / Inactive Patients / Custom Search),
  Caseload Statistics, "Depression Remission or Response 2020" (the DRR
  report's menu name), Monthly Time Tracker. The newer video adds CoCM
  Quality Metrics and Completed Episode Statistics.
- **Older caseload columns**: Flags, Patient ID, MRN, Name, Status, PHQ-9
  First/Last, B/C, P/C, R/P, # Sess, Wks since first B/C, Minutes This
  Month — where **B/C** = date of most recent BH Contact ("excluding those
  marked as care team collaboration/no contact"), **P/C** = most recent
  Psychiatric Consultation, **R/P** = most recent Relapse Prevention Plan.
  The newer video splits B/C into I/A + F/U, which is what the backend
  implements.
- **Status tooltip vocabulary (older)**: E - Enrolled, T - Treatment,
  RPP - Relapse Prevention Plan, D - Discharged. Note "Enrolled" is a
  pre-first-contact state and "Discharged" the older name for
  deactivation; our TreatmentStatusEnum has no enrolled state — open
  question below.
- **Score cell semantics (confirmed, PHQ-9)**: asterisk (*) when the score
  is more than 30 days old (needs re-administration). First-score number
  renders gray when only one score exists (First and Last are the same
  contact). Last-score color: **red** = most recent ≥ 10 AND not improved
  50% from baseline; **yellow** = 5-9 OR improved 50%+; **green** = ≤ 4.
  Equivalent GAD-7/PCL-5 color rules were not shown — do not invent them.
- **Interactive cells**: every service date is a link to that encounter's
  details; a green (+) icon in an empty cell quick-adds a new encounter of
  that column's type ("only date of service and assessment scores are
  added"). All columns sortable ("bring highest scores or oldest visit
  dates to the top").
- **Minutes This Month tooltip (confirmed)**: "Sum of session duration
  minutes for the patient during the current calendar month. Includes Care
  Manager contacts, including those marked 'care team collaboration/no
  contact', and Psychiatric Consultations." Two data-model gaps fall out
  of this: Consultation has no duration_minutes, and there is no
  care-team-collaboration contact type — open questions below.
- **"Report for:" dropdown (confirmed)**: grouped options — Care Manager
  list, Primary Care Provider list, Psychiatric Consultant list, Site,
  Clinic(s) in site — "able to look at reports from other providers to
  cover for each other." Note the Site → Clinics hierarchy; the backend
  models clinics only.
- **Discharge form (older name for Deactivation)**: single date field +
  "Entering this contact will change the patient's status to Discharged";
  moves patient from active to inactive caseload. RPP form annotation
  confirms the cadence change (reminders 2 → 4 weeks) and status cascade
  the backend already implements.

### Resolutions (Matt, 2026-08-07): the newer video wins on conflicts;
### these screenshots serve as field-definition alignment

1. **Enrolled status** — conflict with the newer version's vocabulary →
   resolved per the newer video: TreatmentStatus stays three-state
   (active_treatment / relapse_prevention_plan / deactivated), and
   "Deactivation" (not "Discharge") is the canonical name. No enrolled
   state.
2. **Consultation.duration_minutes** — a definition, not a conflict →
   adopted (Phase 9). Minutes This Month and Monthly Time Tracker include
   psychiatric-consultation minutes.
3. **care_team_collaboration ContactType** — appears in BOTH versions'
   Patient menus → adopted (Phase 9). Billable minutes; never carries
   scores; not a session, not engagement; doesn't reset the attempt
   counter or the reminder cadence clock.
4. **PHQ-9 cell indicators** — adopted (Phase 9): scoring.phq9_score_color
   plus the 30-day staleness asterisk and single-score/gray-first rules,
   computed server-side on the Active Patients report. GAD-7/PCL-5 color
   rules remain UNKNOWN — still awaiting source material; do not invent.

## Second annotated batch (Matt, 2026-08-07) — forms, reports, dashboard

Higher-resolution training-deck screenshots. Three carry NeuroFlow's own
footer, so parts of this deck are NeuroFlow-authored material about the
product being mimicked. Same rule as batch one: **the newer video wins on
conflicts; these confirm field semantics.**

### Session footer (every contact form, confirmed)
One sentence: "This session was [location ▾] with [provider ▾] and took
[minutes ▾] minutes", then Add / Cancel. Confirmed details:
- **Minutes is a dropdown in 5-minute increments** (5, 10, 15, … 60, 70),
  not a free-text number. Our duration_minutes is a plain integer, which
  accepts those values — the increment list is a frontend concern.
- **Confirmed location values**: "in clinic", "by phone", and — on the
  Psychiatric Consultation Note — "case review with CM". This partially
  resolves ContactLocation's placeholder status: in_person/phone are
  confirmed (as "in clinic"/"by phone"); **video is still unconfirmed**,
  and "case review with CM" is a consultation-specific location we don't
  model. Provider is picked per contact (matches Contact.provider_id).

### Initial Assessment / Follow-Up ("Subsequent Encounters")
Confirmed identical layouts — the deck says follow-ups "are essentially
the same thing". Scale block per measure: title bar "Anxiety Scale: GAD-7
(Score: [ ])" with a `history` button, the question matrix (green header
row, one column per response option with its numeric value beside the
radio), and the functional-impairment question rendered as a wider final
row. "Discuss with Psychiatric Consultant" is its own titled section with
its checkbox ("Would you like to discuss this patient with the psychiatric
consultant?") and a Notes textarea, then the session footer.

### Psychiatric Consultation Note ("Case Reviews")
Title band, Date of Contact, then a **read-only "Comments from Care
Manager"** section replaying the flagging contact's notes_for_consultant
(with a "Last updated by" provenance line), then the session footer with
location "case review with CM". The deck notes it can be "recorded by
either the BHCM or Psych Consult" — our Consultation.provider_id is
nullable and unconstrained by role, so this already works.

### Relapse Prevention Plan — richer than a date + scores (BUILT, Phase 10)
Confirmed sections: Date of Contact; **Current Medications** with a
tri-state confirmation above it ("Confirmed with the patient" /
"Confirmed in the patient's medical record" / "Deferred") and a
name+dosage table with add/remove row controls and a searchable name field
(our med picker already covers the search + dose-steps behavior); **Other
Treatments** (e.g., Counseling); **Personal Warning Signs**; **How to
Minimize Stress from Depression or Anxiety**; **Additional Comments**.
Each free-text section has its own `history` button. Built as five new
Contact columns + MedicationConfirmation enum (Phase 10).

### Caseload Statistics — full confirmed column list (BUILT)
`Care Manager | Current Caseload | CARE MANAGER CONTACTS: Pts w/ B/C, Avg
# B/C, Contacts w/ Scale | PSYCHIATRIC CONSULTATION: # in R/P, # Flagged,
# w/ P/C, Not Imprv w/o P/C | AVERAGE PHQ: First, Last | PHQ: No Response,
No Remission`, with an **"All" summary row**. Note the CTMS frames its two
outcome columns *negatively* (No Response / No Remission); we report them
positively (response/remission counts), which is the same information —
the frontend can present either. Matt's instruction (2026-08-07):
**combined response/remission first, then depression and anxiety** — built
as combined_* pooling the disjoint per-condition buckets, then the
per-condition fields.

### DRR Report — window corrected to 4-8 months (BUILT)
The Follow-Up PHQ-9 tooltip, verbatim: *Denominator* — patients with a
PHQ-9 of 10+ any time in the reporting year (use the first elevated score
in the period as the start date); *Numerator* — patients with a PHQ-9
documented **4-8 months** after that initial elevated score, **regardless
of episode**; included only if 4 months have elapsed since the first
elevated score **and they were age 12+** at period start. Matt confirmed
4-8 is authoritative → FOLLOW_UP_WINDOW_END_MONTHS is now 8.

**Still-open DRR differences (not changed unilaterally):**
1. Cohort definition: ours is "index episodes whose PHQ-9 baseline falls
   in the year"; the CTMS's is "first PHQ-9 ≥10 in the year, regardless of
   episode" — a patient whose baseline was below 10, or whose elevated
   score sits mid-episode, is treated differently by each.
2. Age ≥12 at period start is not applied at all in our version.
3. Ours excludes an episode until its window fully closes; the tooltip
   says include once **4 months** have elapsed (window opened, not closed).
Each would change reported denominators, so they need Matt's call.

### Monthly Time Tracker (confirmed)
`Patient ID | MRN | Name | MINUTES PER MONTH: one column per month, oldest
left | All` summary row — 13 columns, matching our current-plus-trailing-12
implementation. The deck confirms our billing-minutes interpretation and
adds an important caveat: without EHR integration it lists "all the
minutes that are being recorded" and "does not distinguish what is
billable or not, so providers have to take a look themselves". So the
frontend must NOT label this column "billable minutes".

### Patient Information / enrollment (confirmed)
Create form: Program Information (Clinic ▾, Enrollment Date, Care
Manager ▾, Patient ID, MRN, Psychiatric Consultant ▾) + Demographic
Information (First/Last Name, DOB) → Add/Cancel. **Care Manager is
required at enrollment; Psychiatric Consultant is optional** — a useful
frontend validation detail our API doesn't enforce (care team assignment
is a separate call). The saved view adds Insurance, Current Providers
(Type/Name/Phone/Email/Service Begin/Service End + **Deactivate** action,
with "Select new provider type/name" + Assign), and Current Clinics
(**Site** / Clinic / MRN / Primary / Service Begin/End + Deactivate). Two
gaps confirmed again: we model clinics without the **Site** parent, and
MRN is per-clinic in the CTMS but a single unique column on our Patient.

### Clinical Dashboard (confirmed, richer than ours)
Left rail: "Customize Dashboard View" with **ON/OFF toggle pills** per
section, then Reminders, Last Contact, **Next Appointment** (red when
near/overdue), Flags (with an inline "Flag" action), Status. Main column
sections seen: Patient Information (Enrollment / Demographic / Current
Providers / Current Clinics, each with its own "Last updated by … date"
provenance line and an `update` button), **Current Concerns** ("Patient
Concerns", "None recorded", `history`), **Medications** (Current
Medications table: Name / **Instruction** / Start Date), **Clinical
Measures** (per measure: "PHQ-9 Score: 5/27, Mild" with `history` and
`expand`/`collapse`; expanded shows the **score line graph plotted against
"Weeks in Treatment (0 = First BH Contact)"** plus that scale's question
matrix), **Problem List** (Name / Start Date), **Psychiatric Consultant**
(flag + notes with `history`/`update`), **Treatment History** (Date of
Contact / Contact Type / Weeks in Tx / Session Duration / PHQ-9 / GAD-7 —
"clicking on the date will expand to pt concerns noted on that date"),
Appointments, Discharge Information.

**Notable**: one dashboard variant is clearly EHR-integrated (Athena
provenance, med Instruction strings, a Problem List of ICD-style
diagnoses) — that content is *fed in*, not entered in the registry. Our
Medication entity is dose+frequency, not a free-text Instruction sig; our
Problem List equivalent is Episode primary/secondary diagnosis, which is
narrower by design.

**Gaps between this dashboard and ours, for the frontend build:**
- Treatment History as a first-class dashboard section (we return
  episodes + scores but never contacts) — this is the Bucket A
  composition work already queued.
- Next Appointment (we have pending Reminders; needs to surface as its
  own rail item), Appointments section, Current Concerns, Problem List,
  Discharge Information, and per-section provenance ("Last updated by").
  Provenance would need an audit-trail read API — CLAUDE.md's PHI rules
  already require audit entries for status/flag/score writes.
- Contact-type vocabulary in Treatment History is "BH Contact / Other
  Contact / Psychiatric Consultation" — a display grouping over our
  ContactType values, not a new enum.

## What to keep vs. modernize (per CLAUDE.md)

Keep: every column, grouping, and report shape above; the scale-driven
contact entry; the dashboard's section structure and customize toggle.
Modernize: typography, spacing, color (NeuroFlow palette — navy `#161B4A`
anchors chrome; accent red `#F16061` reserved for safety flags and true
CTAs), replace the green striping and 2010-era density with a modern
data-grid treatment at equivalent information density.
