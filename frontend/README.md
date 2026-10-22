# CoCM Registry — Frontend

React 18 + TypeScript + Vite SPA for the CoCM Registry API. Per CLAUDE.md:
an internal authenticated tool, not a public site — no Next.js, no SSR.

## Running it

The API must be running first, pointed at the **demo** database — eleven
patients with ~18 months of history dated relative to today, which is what
makes every screen look like a live program (see `scripts/seed_demo.py`):

```bash
DATABASE_URL="postgresql+psycopg://cocm:cocm_local_dev@$(ipconfig getifaddr en0):5432/cocm_registry_demo" \
  python3 -m uvicorn app.main:app --port 8000
```

(The LAN IP is deliberate: a native Postgres shadows `localhost:5432` on
this machine. See CLAUDE.md.)

Then:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and sign in as `priya@neuroflow.com` /
`demo-password` (6 active patients), `dana@neuroflow.com` (3 active,
including the flagged one), or `demo@neuroflow.com` for the supervisor
view of the reports.

To create the demo database from scratch:

```bash
createdb cocm_registry_demo   # or via docker exec psql
DATABASE_URL=...cocm_registry_demo alembic upgrade head
DATABASE_URL=...cocm_registry_demo PYTHONPATH=. python3 scripts/seed_demo.py
```

The pressure-test database works too, but its data is hardcoded to
Feb–Jul 2026, so scores show staleness asterisks and reminders read badly
overdue. That's correct behavior on stale data, just a poor demo.

Vite proxies `/api/*` to `http://127.0.0.1:8000` (override with `API_URL`),
so the app is same-origin in dev and the API needs no CORS middleware.

`npm run typecheck` type-checks without emitting.

## Design decisions

**Navigation is a left sidebar, not the CTMS's dropdown menu bar.** This is
the one deliberate structural deviation. The CTMS's information
architecture is preserved exactly — its `Caseload ▾` lists and reports
become the two sidebar groups, and its centered patient search keeps a
prominent top-bar spot — but presented the way a contemporary SaaS product
would, per CLAUDE.md's "should read as a contemporary SaaS product, not a
2010-era intranet tool." Easy to revisit: it's confined to
`components/AppShell.tsx`.

**The token lives in memory only.** No localStorage, no sessionStorage.
CLAUDE.md forbids persisting PHI client-side, and the same reasoning
applies to the credential that unlocks it. The visible tradeoff: a full
page reload returns you to sign-in. A 401 from any request drops to
sign-in too, so the UI never sits in a half-authenticated state.

**Clinical rules are never re-derived here.** The 30-day staleness
asterisk, the gray single-score rule, and the PHQ-9 red/yellow/green
thresholds all arrive precomputed on the API's report rows
(`app/services/reporting.py`, `app/services/scoring.py`). `components/cells.tsx`
only paints them. GAD-7 and PCL-5 render *uncolored* on purpose — the CTMS
never documented their color rules, and reusing PHQ-9's thresholds on a
scale they weren't validated for is exactly the invention CLAUDE.md
prohibits.

**Two reds, kept apart.** `--nf-accent` (#F16061) is reserved for calls to
action and safety-risk flags, per CLAUDE.md. An elevated symptom score uses
a separate `--data-critical`, so a red number never reads as a button.

**No raw hex outside `styles/tokens.css`.** The NeuroFlow palette is
defined once; every surface, border, and data color derives from it.

## Build status

Built and verified against live pressure data:

- **Sign-in** — NeuroFlow-branded, with the PHI access notice.
- **App shell** — sidebar nav, patient search (name / patient ID / MRN),
  signed-in provider, sign out.
- **Reminders** — the BHCM landing page. Pending reminders in due-date
  order with days-until/overdue callouts, sortable columns.
- **Active Patients** — the caseload list, with the confirmed CTMS column
  order and grouping (Flags, Patient ID, MRN, Name, Age, Status, Meds,
  grouped PHQ-9/GAD-7/PCL-5 First+Last, Contacts group I/A · F/U · P/C ·
  R/P, # Sess, Wks, Min/mo), all columns sortable, the CONSIDER badge,
  clickable service dates, green (+) quick-add on empty date cells, and
  the payer / clinic / "Report for" provider filters.
- **Clinical Dashboard** — the single-patient view. Measure trend graphs at
  the top, one per treated diagnosis with the primary first (verified:
  Ben Okafor shows Anxiety/GAD-7 marked Primary alongside
  Depression/PHQ-9), each with baseline → latest → change, server-computed
  response/remission badges, and an SVG line chart plotted against "weeks
  in treatment (0 = first BH contact)" with the confirmed remission
  threshold drawn only for PHQ-9 and GAD-7. Plus patient information
  (enrollment, demographics, current providers, current clinics),
  medications, the append-only patient profile grouped by section with
  per-sub-field history, psychiatric consultations, treatment history
  (contacts and case reviews merged chronologically with weeks-in-Tx), and
  episode history. The CTMS's "Customize Dashboard View" ON/OFF toggles
  control section visibility client-side, exactly as CLAUDE.md describes.

  It composes four endpoints — the dashboard report plus contacts,
  consultations, and reminders — because the report doesn't include the
  last three. That's what powers Treatment History and the Next
  Appointment rail item without a backend change.

- **Record a contact** — the scale-driven encounter form, and the app's
  main write path. One save covers the visit date, every scale collected,
  the consultant checkbox, the encounter note, and the session footer,
  because that's what `POST /contacts` accepts in a single call; splitting
  it would bypass the server-side cascades (baseline recompute, RPP status
  transition, flag set, attempt numbering). Includes:
  - **Scale matrices with auto-totals** for PHQ-9 and GAD-7 — items
    transcribed verbatim from Matt's screenshots, response columns showing
    each option's value, answered rows highlighted, and the trailing
    functional-impairment question displayed but excluded from the total
    (labelled as such).
  - **Direct total entry**, which overrides the computed total and is the
    only mode for PCL-5 / SCARED / SMFQ / Vanderbilt — see `lib/scales.ts`
    for why their items are deliberately absent.
  - **Carry-forward scale selection**: the measures on the patient's last
    scored contact come pre-checked, falling back to the episode's
    diagnoses on a first visit.
  - An incomplete scale is **not** submitted, and says so — a partly
    answered questionnaire isn't a valid score.
  - The **RPP plan fields** (medication-confirmation tri-state plus the
    four free-text sections) appear only when the type is relapse
    prevention plan, matching the server's own rejection rule.
  - Contact-attempt and care-team-collaboration types hide the scale and
    consultant sections entirely and explain their reporting semantics.
  - The **session footer** as one sentence, with minutes in the confirmed
    5-minute increments.
- **Psychiatric Consultation Note** — date, consultant, findings, the
  recommendations-forwarded and flag-for-next-review checkboxes, and a
  read-only replay of the care manager's comments from the flagging
  contact (the CTMS's own layout). No location control, because a
  Consultation has no location column.

- **Patient Enrollment** — the CTMS's Program Information / Demographic
  Information form, plus an Episode of Care section. Enrolling is four API
  calls (patient → episode → care team → clinic) issued in dependency
  order; a mid-sequence failure reports honestly and names the patient ID
  that was created rather than attempting client-side rollback. Three
  fields the CTMS doesn't show here are required because the model requires
  them: payer, consent date, and a primary diagnosis (which is what pins
  outcome reporting to a measure, so collecting it at enrollment prevents
  episodes that can never report).
- **Inactive Patients** — derived as "every patient not on the Active
  Patients report", which is that report's own exclusion rule, so the two
  lists partition the roster without asking the backend the same question
  twice. Shows each patient's last episode outcome and offers
  **re-enrollment**, which opens a NEW episode rather than reopening the
  old one — the AIMS new-baseline rule.

- **All five reports.** Each carries an on-screen “How this is calculated”
  note, because every one of them has an assumption or an unmeasurable
  metric that a bare number would misrepresent.
  - **Caseload Statistics** — the confirmed CTMS column list, aggregated by
    provider or clinic, with outcome rates combined first then split by
    depression and anxiety. The “All groups” row sums the group rows and
    recomputes each percentage from those sums (never averages them), and
    says so, since a patient on two care teams counts in both.
  - **CoCM Quality Metrics** — twelve months as rows. Caseload Reach reads
    **n/a**, and PTSD / pediatric improvement read **“no threshold”** beside
    their real denominators, rather than a 0% that would read as a program
    failing at PTSD care.
  - **Completed Episode Statistics** — stat tiles, outcomes at close, and
    the end-reason breakdown including its “not recorded” bucket.
  - **DRR** — clinic rows with all three rates on the shared denominator,
    and an empty state that explains *why* it is empty (an episode joins
    only once its 4-8 month window closes).
  - **Monthly Time Tracker** — the 13-month matrix with an All-patients
    row, including patients since deactivated. Labelled **recorded**
    minutes, never billable.

- **Medications** — a search-as-you-type picker over the vendored
  behavioral-health catalog. Picking a drug turns the dose field into a
  dropdown of that drug's real FDA strengths (Bupropion XL → 150/300/450 mg)
  and says the entry will count toward the caseload's psychotropic column;
  a name with no catalog match saves as free text and says it won't. Stop a
  medication with an optional reason, restart it (which clears the reason),
  or edit a dose inline. The server owns those rules — this screen just
  calls PATCH.
- **Patient Profile** — the click-a-sub-field, add-a-value model across all
  six sections, with each section's guardrail stated on screen (Current
  Medications offers only allergies/intolerances; Safety & Risk entries
  never touch the red flag; Behavioral Health has no diagnoses or severity
  field because those live on the episode and the score). Append-only is
  explicit in the UI: there are no edit or delete controls, "Update" adds a
  superseding entry, and the previous value collapses into per-field
  history.

- **Treatment History** — every contact and case review for one patient,
  expandable to its full record: the scores collected, the encounter note,
  the notes for the consultant, and the RPP plan block. Scores are fetched
  only when a row is expanded, so the list stays one request. The caseload
  list's clickable service dates land here with `?on=<date>` and open that
  row automatically, which is what makes those dates worth being links.
- **Deactivation** — closes the episode. Despite the CTMS filing this under
  "New Contact", it isn't a contact in this data model: setting `end_date`
  is what the server treats as deactivation, and `EpisodeService` cascades
  from there to the deactivated status and dismisses the pending reminder.
  The form makes one PATCH and lets the cascade run. It states plainly that
  the end reason is a deactivation reason, not a clinical outcome.

**Every route is now a real screen — no placeholders remain.**

### Verified management-screen behavior

- Searching "bupro" returned Bupropion XL from the catalog; selecting it
  populated the real FDA dose list and the catalog-match hint. Saving it,
  then stopping it with the reason "Insomnia at 300 mg", moved it from
  Current to Past with the reason intact.
- Updating Alice's existing `safety_plan` entry made the new value current
  and collapsed the February entry into "1 earlier entry" — the append-only
  contract, visible in the UI.
- Deactivating Emma Tran with "achieved goals" moved her to Inactive
  Patients with the reason shown, and her pending appointment reminder
  disappeared from the Reminders landing page — one PATCH, three
  server-side effects.

### Verified enrollment behavior

Enrolling Marcus Webb (anxiety primary, depression secondary) through the
form produced, in one submit: the patient, an open episode with both
diagnoses, care-manager and psychiatric-consultant assignments, a primary
clinic assignment, an active treatment status, and — from the server's own
cascade — a **7-day enrollment reminder**. Re-enrolling David Kim opened a
new episode and returned him to the caseload with no scores and zero
sessions, because the caseload reports the current episode only. That is
the new-baseline rule visible in the UI.

### Verified write-path behavior

Recording a GAD-7 of 7 and a directly-typed PHQ-9 of 9 on Ben Okafor's
follow-up, then a flagged consultation on Carla Reyes, was checked
end-to-end in the browser:

- The contact saved, redirected to the dashboard, and appeared at the top
  of Treatment History with its note, minutes, and location.
- Both trend charts recomputed: anxiety went from “Remission + Response”
  to “Response” alone (7 is no longer under 5) and depression read “Not yet
  responding” (15→9 is 40%, short of the 50% threshold). The frontend
  displays those verdicts; the server computes them.
- Carla's consultation cleared her review flag and immediately re-set it
  because it flagged a future review, which is the documented
  ConsultationService cascade. The caseload list then showed her yellow
  flag dot and the CONSIDER badge, sorted to the top.
- Consultant minutes flowed into Minutes This Month (Carla 0 → 20),
  confirming the Phase 9 billing behavior through the UI.

## Known gaps

- **Patient search filters client-side** over `GET /patients?limit=500`;
  the API has no search endpoint. Fine at one program's caseload size, but
  the place to add `GET /patients?q=` when it isn't.
- **Payer and clinic filters are free-text inputs**, not pickers — there's
  no endpoint enumerating payers or clinics yet.
- Screens the CTMS has that the API doesn't back yet (Problem List,
  Appointments, Current Concerns, per-section "Last updated by"
  provenance) are documented in `docs/ctms-reference/README.md` and are not
  stubbed here.
