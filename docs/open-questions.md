# Open questions — CoCM Registry

Four decisions we cannot make from the source material we have. Each one
changes numbers the registry reports, so each needs an answer from someone
who can speak for the clinical or measurement definition rather than a
best guess from us.

Last updated 2026-08-19. Each question states what we do today, what we'd
change, and what breaks if we guess wrong.

---

## 1. GAD-7 and PCL-5 score colours on the caseload list

**Confirmed already.** The AIMS Caseload Tracker colours the most recent
PHQ-9 on the caseload list, and its tooltip gives the exact rule:

- **Red** — most recent score is 10 or above *and* has not improved 50% from baseline
- **Yellow** — most recent score is 5–9, *or* has improved 50% or more from baseline
- **Green** — most recent score is 4 or below

It also marks any score older than 30 days with an asterisk, and greys the
"First" value when only one score exists. All of that is implemented.

**What we don't know.** Whether GAD-7 and PCL-5 get the same treatment. No
screenshot or video frame we have shows a coloured GAD-7 or PCL-5 cell.

**What we do today.** GAD-7 and PCL-5 render uncoloured. They still get the
30-day asterisk and the single-score grey. We deliberately did *not* reuse
the PHQ-9 thresholds, because a 10 on a GAD-7 does not mean what a 10 on a
PHQ-9 means, and colouring them as though it did would be inventing a
clinical cut-off.

### The question

> **Does the Caseload Tracker colour the "Last" GAD-7 and PCL-5 cells?**
>
> - If **yes**: what are the exact band rules for each, in the same form as
>   the PHQ-9 rule above?
> - If **no** — it only ever colours PHQ-9 — please confirm that, and we'll
>   record it as settled rather than missing.

**Why it matters.** These colours are what a care manager scans to decide
who to talk about at caseload review. Getting them wrong is worse than
leaving them off; leaving them off when they should exist means a real
signal is missing from the screen.

---

## 2. Depression Remission or Response (DRR) — three cohort differences

We built DRR from the HEDIS-style spec, then found the Caseload Tracker's
own "Follow-Up PHQ-9" tooltip, which reads:

> *Denominator:* Patients with a PHQ-9 score of 10+ any time between
> [period start] – [period end]. (Use first elevated score during this
> period as start date.)
> *Numerator:* Patients with a PHQ-9 score documented at 4-8 months after
> the initial elevated score, regardless of episode.
> Patients are included if 4 months have elapsed since the first elevated
> score, and they were age 12+ on [period start].

The **4-8 month window** is confirmed and implemented. Three other
differences remain, and each moves the denominator.

### 2a. How is the cohort defined?

**Tooltip:** the first PHQ-9 of 10 or above anywhere in the reporting year,
*regardless of episode*.
**Ours:** the baseline (first) PHQ-9 of the patient's index episode, when
that baseline falls in the reporting year.

These diverge for two real patients: someone who enrolled with a PHQ-9 of 8
and later scored 14 (we exclude them; the tooltip includes them from the 14),
and someone whose elevated score arrives mid-episode rather than at intake.

> **Which definition should the report use — first elevated score in the
> period regardless of episode, or the index episode's baseline?**

### 2b. Should the age ≥ 12 criterion apply?

**Tooltip:** patients must be 12 or older at the start of the period.
**Ours:** no age criterion at all.

We track pediatric patients (SCARED, SMFQ, Vanderbilt), so this is not
hypothetical — a 10-year-old with a PHQ-9 would currently be counted.

> **Should DRR exclude patients under 12 at the period start?**

### 2c. When does a patient enter the cohort?

**Tooltip:** once **4 months** have elapsed since the first elevated score —
i.e. as soon as the window *opens*.
**Ours:** once the full **8 months** have elapsed — i.e. once the window
*closes*.

The difference is how you treat a patient whose window is still open. The
tooltip's approach counts them in the denominator and scores them as a miss
until they get a follow-up; ours holds them out until their outcome is
genuinely knowable. Ours produces higher rates early in a year; theirs
produces lower ones. Neither is wrong, but they are not the same measure.

> **Should a patient enter the denominator when the window opens (4 months)
> or when it closes (8 months)?**

**Why all three matter.** DRR is the report most likely to be quoted
externally. If we are reporting a number that claims to be HEDIS DRR, its
cohort rule has to match whatever definition the recipient expects.

---

## 3. Site → Clinic hierarchy

**What the Caseload Tracker has.** Its patient screens show a **Site**
containing **Clinics** ("Test Site" → "Test Clinic"), and its "Report for:"
dropdown offers both levels: individual care managers, PCPs, psychiatric
consultants, then *Site*, then *Clinic(s) in Site*.

**What we have.** Clinics only, as flat string identifiers on a patient's
clinic assignment. No parent, no site-level rollup. Reports can group by
clinic but not by site.

**Why we haven't guessed.** This interacts with a decision already recorded
for multi-tenancy: a future `Organization` is meant to represent one
NeuroFlow customer org. A "Site" could plausibly *be* that Organization, or
could be a layer beneath it (org → site → clinic). Picking wrong means
either a wasted table or a migration through the middle of the tenancy
model.

### The question

> **Do programs need site-level reporting, or is clinic-level enough?**
>
> And if sites are needed: **is a Site the same thing as the customer
> organization, or a grouping beneath it?** Concretely — would a single
> NeuroFlow customer ever have more than one Site?

**Why it matters.** It's cheap to add now and expensive to retrofit once
multi-tenancy exists, because it changes what the tenant boundary is.

---

## 4. GAD-7 remission < 5 — is there a citable source?

**What we implemented.** GAD-7 remission is a score under 5, confirmed
verbally on 2026-08-07. It now drives real reported numbers: the anxiety
remission rate on Caseload Statistics, the remission badge on the Clinical
Dashboard's anxiety trend, and the combined outcome rate.

**Why we're asking.** Every other clinical threshold in the codebase has a
documented origin — PHQ-9 remission < 5 and the 50% response rule come from
the AIMS guide, the GAD-7 5-point improvement rule likewise, and the
unconfirmed ones (PCL-5, SCARED, SMFQ, Vanderbilt) are deliberately left
unimplemented with that fact recorded in the code. GAD-7 remission is the
only threshold in the system resting on a verbal confirmation.

### The question

> **Is GAD-7 remission < 5 traceable to a published source we can cite — a
> paper, an AIMS training document, an NCQA or HEDIS specification?**
>
> If it is your own clinical judgment rather than a published cut-off,
> that's a legitimate answer — we'll record it as an explicit product
> decision attributed to you, the same way we've flagged the two CoCM
> Quality Metrics definitions that are our own reasonable extensions rather
> than confirmed methodology.

**Why it matters.** Not because we doubt it — < 5 is consistent with how
GAD-7 severity bands are usually described. But an outcome rate that gets
shown to a customer or a payer should be able to say where its threshold
came from, and right now this one can only say "Matt told us".

---

## Summary

| # | Question | Blocks |
|---|---|---|
| 1 | GAD-7 / PCL-5 caseload colour rules — or confirmation there are none | Caseload list visual indicators |
| 2a | DRR cohort: first elevated score in period, or index-episode baseline? | DRR denominators |
| 2b | DRR: apply the age ≥ 12 criterion? | DRR denominators |
| 2c | DRR: enter the cohort at 4 months (window opens) or 8 (window closes)? | DRR denominators |
| 3 | Site-level rollup needed? Is a Site the customer org or beneath it? | Reporting grain; multi-tenancy design |
| 4 | Citable source for GAD-7 remission < 5, or record as a product decision? | Provenance of a reported outcome rate |
