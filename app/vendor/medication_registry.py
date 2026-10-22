"""
Medication Registry
===================
Complete medication knowledge base for the follow-up form.

Covers all conditions: MDD, GAD, PTSD, ADHD, Bipolar I/II, SUD.

Each entry includes:
  key          — Lowercase snake_case identifier (matches MED_KB in algorithm.py where present)
  display      — Patient-facing name (generic + brand)
  class        — Medication class
  role         — "primary" | "augmentation" | "secondary"
                 primary     = first-line or established monotherapy
                 augmentation = added to a primary medication
                 secondary   = off-label, adjunctive, or condition-specific add-on
  dose_steps   — Available tablet/capsule strengths in mg (FDA-approved)
                 For combination products (buprenorphine/naloxone) the buprenorphine
                 component is listed; display_doses shows the full combination string.
  display_doses — Optional list of patient-facing dose labels when dose_steps alone
                  is insufficient (e.g. combination products, fixed-dose formulations).
  conditions   — List of condition keys this medication is appropriate for.
  side_effect_module — Module key for get_side_effect_module() in side_effect_modules.py.
  notes        — Optional clinical note shown to provider, not patient.

dose_steps values are real FDA-approved tablet/capsule strengths sourced from:
  - FDA label data (accessdata.fda.gov)
  - StatPearls / NCBI
  - Drugs.com prescribing information
"""

from typing import Any


# ---------------------------------------------------------------------------
# Medication definitions
# ---------------------------------------------------------------------------

MEDICATIONS: dict[str, dict[str, Any]] = {

    # ── SSRIs ────────────────────────────────────────────────────────────────

    "sertraline": {
        "display": "Sertraline (Zoloft)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [25, 50, 100, 150, 200],
        "conditions": ["mdd", "gad", "ptsd", "panic", "adjustment", "bipolar_i", "bipolar_ii", "sud"],
        "side_effect_module": "ssri",
        "notes": "FDA-approved for MDD, PTSD. Co-preferred first-line for panic disorder. First-line for most anxiety disorders. In adjustment disorder, a symptomatic bridge only (not disorder-modifying). Use with mood stabilizer in bipolar.",
    },
    "fluoxetine": {
        "display": "Fluoxetine (Prozac)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [10, 20, 40, 60, 80],
        "conditions": ["mdd", "gad", "panic", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "ssri",
        "notes": "Long half-life; useful when adherence is variable. First-line (less preferred) for panic disorder. Avoid in geriatric/cardiac per existing MED_KB. "
                 "Not carried forward for PTSD (dropped per current guidelines) — excluded from PTSD selection.",
    },
    "escitalopram": {
        "display": "Escitalopram (Lexapro)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [5, 10, 20],
        "conditions": ["mdd", "gad", "panic", "bipolar_i", "bipolar_ii", "sud"],
        "side_effect_module": "ssri",
        "notes": "Co-preferred first-line for panic disorder. Max 10 mg in geriatric and hepatic impairment. QTc risk at higher doses. "
                 "Not guideline-concordant for PTSD (off-label) — excluded from PTSD selection.",
    },
    "citalopram": {
        "display": "Citalopram (Celexa)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [10, 20, 40],
        "conditions": ["mdd", "gad", "panic"],
        "side_effect_module": "ssri",
        "notes": "First-line (less preferred) for panic disorder. Max 20 mg in geriatric/hepatic (and age >= 60). Known QTc risk.",
    },
    "paroxetine": {
        "display": "Paroxetine (Paxil)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [10, 20, 30, 40, 50],
        "conditions": ["mdd", "gad", "ptsd", "panic"],
        "side_effect_module": "ssri",
        "notes": "FDA-approved for PTSD. In panic disorder, reserved as the alternative-SSRI option after first failure (discontinuation syndrome, CYP2D6 inhibition, pregnancy category D). Highest discontinuation syndrome risk of SSRIs.",
    },
    "fluvoxamine": {
        "display": "Fluvoxamine (Luvox)",
        "class": "SSRI",
        "role": "primary",
        "dose_steps": [50, 100, 150, 200, 300],
        "conditions": ["mdd", "gad"],
        "side_effect_module": "ssri",
        "notes": "Off-label for MDD. Strong CYP1A2/3A4 inhibitor.",
    },

    # ── SSRIs (SMS — serotonin modulators) ───────────────────────────────────

    "vortioxetine": {
        "display": "Vortioxetine (Trintellix)",
        "class": "SMS",
        "role": "primary",
        "dose_steps": [5, 10, 20],
        "conditions": ["mdd"],
        "side_effect_module": "ssri",
        "notes": "May have cognitive benefits. GI side effects common at initiation.",
    },
    "vilazodone": {
        "display": "Vilazodone (Viibryd)",
        "class": "SMS",
        "role": "primary",
        "dose_steps": [10, 20, 40],
        "conditions": ["mdd"],
        "side_effect_module": "ssri",
        "notes": "Take with food. GI side effects at initiation.",
    },

    # ── SNRIs ────────────────────────────────────────────────────────────────

    "venlafaxine_xr": {
        "display": "Venlafaxine XR (Effexor XR)",
        "class": "SNRI",
        "role": "primary",
        "dose_steps": [37.5, 75, 150, 225],
        "conditions": ["mdd", "gad", "ptsd", "panic", "adhd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "snri",
        "notes": "BP monitoring required. Back-of-first-line for panic disorder (geriatric target 75 mg; renal cap 112.5 mg). Off-label for ADHD and bipolar depression (with mood stabilizer).",
    },
    "duloxetine": {
        "display": "Duloxetine (Cymbalta)",
        "class": "SNRI",
        "role": "primary",
        "dose_steps": [30, 60],
        "conditions": ["mdd", "gad"],
        "side_effect_module": "snri",
        "notes": "Max 60 mg/day. Avoid in hepatic impairment. BP monitoring.",
    },
    "desvenlafaxine": {
        "display": "Desvenlafaxine (Pristiq)",
        "class": "SNRI",
        "role": "primary",
        "dose_steps": [50, 100],
        "conditions": ["mdd"],
        "side_effect_module": "snri",
    },
    "levomilnacipran_er": {
        "display": "Levomilnacipran ER (Fetzima)",
        "class": "SNRI",
        "role": "primary",
        "dose_steps": [20, 40, 80, 120],
        "conditions": ["mdd"],
        "side_effect_module": "snri",
    },

    # ── NDRIs ────────────────────────────────────────────────────────────────

    "bupropion_xl": {
        "display": "Bupropion XL (Wellbutrin XL)",
        "class": "NDRI",
        "role": "primary",
        "dose_steps": [150, 300, 450],
        "conditions": ["mdd", "adhd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "bupropion",
        "notes": "Off-label for ADHD and bipolar depression. Lowers seizure threshold. Avoid in eating disorders.",
    },

    # ── NaSSA ────────────────────────────────────────────────────────────────

    "mirtazapine": {
        "display": "Mirtazapine (Remeron)",
        "class": "NaSSA",
        "role": "primary",
        "dose_steps": [15, 30, 45],
        "conditions": ["mdd", "gad", "ptsd", "panic"],
        "side_effect_module": "mirtazapine",
        "notes": "Sedating — useful for insomnia comorbidity. In panic disorder, second-choice monotherapy after two SSRI/SNRI failures (not the default augmentation). Weight gain common. Avoid in obesity.",
    },

    # ── TCAs ─────────────────────────────────────────────────────────────────

    "nortriptyline": {
        "display": "Nortriptyline (Pamelor)",
        "class": "TCA",
        "role": "primary",
        "dose_steps": [10, 25, 50, 75, 100, 150],
        "conditions": ["mdd"],
        "side_effect_module": "ssri",
        "notes": "Later-line. Therapeutic drug monitoring recommended. Cardiac monitoring required.",
    },
    "desipramine": {
        "display": "Desipramine (Norpramin)",
        "class": "TCA",
        "role": "primary",
        "dose_steps": [10, 25, 50, 75, 100, 150],
        "conditions": ["mdd", "ptsd"],
        "side_effect_module": "ssri",
        "notes": "Later-line. Less anticholinergic than other TCAs.",
    },

    # ── Atypical antipsychotics (augmentation/primary for bipolar) ───────────

    "aripiprazole": {
        "display": "Aripiprazole (Abilify)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [2, 5, 10, 15, 20, 30],
        "conditions": ["mdd", "ptsd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "FDA-approved augmentation for MDD. First-line for bipolar I mania. "
                 "PTSD: preferred antipsychotic in obesity (lower metabolic risk).",
    },
    "brexpiprazole": {
        "display": "Brexpiprazole (Rexulti)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [0.5, 1, 2, 3, 4],
        "conditions": ["mdd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
    },
    "quetiapine": {
        "display": "Quetiapine (Seroquel)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [25, 50, 100, 150, 200, 300, 400],
        "conditions": ["mdd", "gad", "ptsd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "FDA-approved for bipolar depression and mania. Sedating at lower doses.",
    },
    "cariprazine": {
        "display": "Cariprazine (Vraylar)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [1.5, 3, 4.5, 6],
        "conditions": ["mdd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "FDA-approved for bipolar depression and mania.",
    },
    "risperidone": {
        "display": "Risperidone (Risperdal)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [0.25, 0.5, 1, 2, 3, 4],
        "conditions": ["mdd", "ptsd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
    },
    "olanzapine": {
        "display": "Olanzapine (Zyprexa)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [2.5, 5, 7.5, 10, 15, 20],
        "conditions": ["mdd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "Significant metabolic side effects. Weight monitoring required.",
    },
    "lurasidone": {
        "display": "Lurasidone (Latuda)",
        "class": "Atypical antipsychotic",
        "role": "augmentation",
        "dose_steps": [20, 40, 60, 80, 120, 160],
        "conditions": ["mdd", "bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "FDA-approved for bipolar depression. Take with food (350+ calories).",
    },

    # ── Azapirones ───────────────────────────────────────────────────────────

    "buspirone": {
        "display": "Buspirone (Buspar)",
        "class": "Azapirone",
        "role": "primary",
        "dose_steps": [5, 10, 15, 30],
        "conditions": ["gad", "adjustment"],
        "side_effect_module": "generic",
        "notes": "Non-benzodiazepine anxiolytic. Takes 2-4 weeks for effect. No dependence risk. In adjustment disorder, a symptomatic bridge for anxiety-predominant presentations.",
    },

    # ── Alpha-1 antagonist (PTSD adjunct) ────────────────────────────────────

    "prazosin": {
        "display": "Prazosin (Minipress)",
        "class": "Alpha-1 antagonist",
        "role": "secondary",
        "dose_steps": [1, 2, 5],
        "conditions": ["ptsd"],
        "side_effect_module": "prazosin",
        "notes": "Off-label for PTSD nightmares. Always secondary to SSRI/SNRI. First-dose hypotension risk — take at bedtime.",
    },

    # ── Stimulants (ADHD) ────────────────────────────────────────────────────

    "methylphenidate": {
        "display": "Methylphenidate (Ritalin / Concerta)",
        "class": "Stimulant",
        "role": "primary",
        "dose_steps": [5, 10, 18, 20, 27, 36, 54],
        "conditions": ["adhd"],
        "side_effect_module": "stimulant",
        "notes": "Schedule II controlled substance. Multiple formulations — IR and XR.",
    },
    "lisdexamfetamine": {
        "display": "Lisdexamfetamine (Vyvanse)",
        "class": "Stimulant",
        "role": "primary",
        "dose_steps": [20, 30, 40, 50, 60, 70],
        "conditions": ["adhd"],
        "side_effect_module": "stimulant",
        "notes": "Schedule II controlled substance. Prodrug — lower abuse potential than amphetamine salts.",
    },
    "amphetamine_salts": {
        "display": "Amphetamine salts (Adderall)",
        "class": "Stimulant",
        "role": "primary",
        "dose_steps": [5, 7.5, 10, 12.5, 15, 20, 25, 30],
        "conditions": ["adhd"],
        "side_effect_module": "stimulant",
        "notes": "Schedule II controlled substance. IR and XR formulations available.",
    },

    # ── Non-stimulant ADHD ───────────────────────────────────────────────────

    "atomoxetine": {
        "display": "Atomoxetine (Strattera)",
        "class": "Non-stimulant NRI",
        "role": "primary",
        "dose_steps": [10, 18, 25, 40, 60, 80, 100],
        "conditions": ["adhd"],
        "side_effect_module": "snri",
        "notes": "Not a controlled substance. Takes 4-6 weeks for full effect. FDA black box warning for suicidality in pediatric patients.",
    },
    "viloxazine_er": {
        "display": "Viloxazine ER (Qelbree)",
        "class": "Non-stimulant SNRI-like",
        "role": "primary",
        "dose_steps": [100, 200, 400, 600],
        "conditions": ["adhd"],
        "side_effect_module": "snri",
        "notes": "Not a controlled substance. Adult max 600 mg/day (higher than the 400 mg pediatric max). "
                 "Assess HR/BP before initiation and after each increase; screen bipolar/suicidality. "
                 "No hepatic dose adjustment needed at any Child-Pugh tier (dedicated PK study).",
    },
    "guanfacine_er": {
        "display": "Guanfacine ER (Intuniv)",
        "class": "Non-stimulant alpha-2 agonist",
        "role": "secondary",
        "dose_steps": [1, 2, 3, 4],
        "conditions": ["adhd"],
        "side_effect_module": "alpha2_agonist",
        "notes": "No US adult ADHD approval — off-label, extrapolated from pediatric labeling (thin, "
                 "third-choice evidence). Requires taper at discontinuation (rebound hypertension). "
                 "CYP3A4: halve dose with strong inhibitors. Lowers BP (distinct from BP-raising agents).",
    },
    "clonidine_er": {
        "display": "Clonidine ER (Kapvay)",
        "class": "Non-stimulant alpha-2 agonist",
        "role": "secondary",
        "dose_steps": [0.1, 0.2, 0.3, 0.4],
        "conditions": ["adhd"],
        "side_effect_module": "alpha2_agonist",
        "notes": "No US adult ADHD approval — weakest evidence in the ADHD algorithm (no adult trial "
                 "base; pediatric extrapolation only). Requires taper at discontinuation (rebound "
                 "hypertension). Lowers BP.",
    },

    # ── Mood stabilizers (Bipolar) ───────────────────────────────────────────

    "lithium": {
        "display": "Lithium carbonate (Lithobid)",
        "class": "Mood stabilizer",
        "role": "primary",
        "dose_steps": [150, 300, 600],
        "conditions": ["bipolar_i", "bipolar_ii"],
        "side_effect_module": "mood_stabilizer",
        "notes": "Narrow therapeutic index. Serum level monitoring required. Reduces suicidality.",
    },
    "divalproex": {
        "display": "Divalproex (Depakote)",
        "class": "Mood stabilizer",
        "role": "primary",
        "dose_steps": [125, 250, 500],
        "conditions": ["bipolar_i", "bipolar_ii"],
        "side_effect_module": "mood_stabilizer",
        "notes": "Serum level monitoring. Teratogenic — requires REMS in women of childbearing potential.",
    },
    "lamotrigine": {
        "display": "Lamotrigine (Lamictal)",
        "class": "Mood stabilizer",
        "role": "primary",
        "dose_steps": [25, 50, 100, 150, 200],
        "conditions": ["bipolar_i", "bipolar_ii", "ptsd"],
        "side_effect_module": "mood_stabilizer",
        "notes": "FDA-approved for bipolar I maintenance. Best evidence for bipolar depression. Slow titration required to reduce SJS risk.",
    },
    "carbamazepine": {
        "display": "Carbamazepine (Tegretol)",
        "class": "Mood stabilizer",
        "role": "primary",
        "dose_steps": [200, 400, 600, 800],
        "conditions": ["bipolar_i", "bipolar_ii"],
        "side_effect_module": "mood_stabilizer",
        "notes": "Serum level monitoring (goal 4-12 mcg/mL). Auto-induces metabolism. HLA-B*1502 screening in patients of Asian descent. Excluded in hepatic impairment; tiered cardiac gate.",
    },

    # ── Atypical antipsychotics used primarily for bipolar mania/mixed ────────

    "asenapine": {
        "display": "Asenapine (Saphris)",
        "class": "Atypical antipsychotic",
        "role": "primary",
        "dose_steps": [5, 10],
        "conditions": ["bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "Sublingual — do not swallow; avoid eating/drinking for 10 min after. First-line for DSM-IV mixed episodes. Contraindicated in Child-Pugh C.",
    },
    "ziprasidone": {
        "display": "Ziprasidone (Geodon)",
        "class": "Atypical antipsychotic",
        "role": "primary",
        "dose_steps": [40, 80],
        "conditions": ["bipolar_i", "bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "Take with ≥500-calorie meal for absorption. Own QTc-prolongation risk — dropped from the cardiac less-severe-symptom manic pool.",
    },

    # ── Bipolar II-specific medications (BD-II depression tier) ───────────────
    # None tagged bipolar_i: these are genuinely BD-II-only per the algorithm spec.

    "lumateperone": {
        "display": "Lumateperone (Caplyta)",
        "class": "Atypical antipsychotic",
        "role": "primary",
        "dose_steps": [42],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "augmentation",
        "notes": "FDA-approved for bipolar depression. Fixed 42 mg once daily (no titration). Preferred over quetiapine when metabolic risk is a concern. Child-Pugh B/C: 21 mg. Dose-reduce with CYP3A4 inhibitors.",
    },
    "tranylcypromine": {
        "display": "Tranylcypromine (Parnate)",
        "class": "MAOI",
        "role": "secondary",
        "dose_steps": [10, 30, 60],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "Third-line for anergic BD-II depression. Requires a dedicated safety gate: never monotherapy (co-prescribe mood stabilizer/antipsychotic), tyramine dietary restriction, washout math, hard exclusion in uncontrolled HTN/cerebrovascular disease. Contraindicated with SSRIs/SNRIs/bupropion/carbamazepine.",
    },
    "pramipexole": {
        "display": "Pramipexole (Mirapex)",
        "class": "Dopamine agonist",
        "role": "augmentation",
        "dose_steps": [0.25, 0.5, 1.5, 2.5],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "Adjunctive for anergic/anhedonic BD-II depression. Hypomania risk — mitigate with concurrent antipsychotic.",
    },
    "iv_ketamine": {
        "display": "IV Ketamine",
        "class": "NMDA receptor antagonist",
        "role": "augmentation",
        "dose_steps": [0.5],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "0.5 mg/kg IV over 40 min, single infusion. Transient relief only (dissipates by 1-2 weeks) — a crisis/bridge intervention, not standing maintenance.",
    },
    "t3_liothyronine": {
        "display": "T3/Liothyronine (Cytomel)",
        "class": "Thyroid hormone",
        "role": "augmentation",
        "dose_steps": [25, 50],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "Adjunctive for treatment-resistant depression, especially with subclinical hypothyroidism/rapid cycling. Thyroid function monitoring; caution in cardiovascular disease/arrhythmias.",
    },
    "nac": {
        "display": "N-Acetylcysteine",
        "class": "Antioxidant/glutamate modulator",
        "role": "augmentation",
        "dose_steps": [1000],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "1000 mg twice daily. Low-confidence adjunct: initial positive trial not replicated; current evidence does not support efficacy. Favorable safety profile.",
    },
    "epa_omega3": {
        "display": "EPA/Omega-3",
        "class": "Fatty acid supplement",
        "role": "augmentation",
        "dose_steps": [1000, 2000],
        "conditions": ["bipolar_ii"],
        "side_effect_module": "generic",
        "notes": "1-2 g/day EPA (≥60% of EPA+DHA). Weakest evidence of the third-line tier — essentially a low-risk supplement.",
    },

    # ── SUD medications ──────────────────────────────────────────────────────

    "naltrexone": {
        "display": "Naltrexone (ReVia / Vivitrol)",
        "class": "Opioid antagonist",
        "role": "primary",
        "dose_steps": [25, 50],
        "conditions": ["sud"],
        "side_effect_module": "generic",
        "notes": "Oral: 50 mg daily. Must be opioid-free for 7-10 days before starting. Also FDA-approved for AUD.",
    },
    "buprenorphine_naloxone": {
        "display": "Buprenorphine/Naloxone (Suboxone)",
        "class": "Partial opioid agonist",
        "role": "primary",
        "dose_steps": [2, 4, 8, 12],
        "display_doses": ["2mg/0.5mg", "4mg/1mg", "8mg/2mg", "12mg/3mg"],
        "conditions": ["sud"],
        "side_effect_module": "generic",
        "notes": "Sublingual film. DEA X-waiver required. Dose listed as buprenorphine component.",
    },
    "acamprosate": {
        "display": "Acamprosate (Campral)",
        "class": "NMDA modulator",
        "role": "primary",
        "dose_steps": [333, 666],
        "display_doses": ["333 mg (1 tablet)", "666 mg (2 tablets — standard dose)"],
        "conditions": ["sud"],
        "side_effect_module": "generic",
        "notes": "AUD maintenance. Standard dose is 666 mg (2 tablets) TID. Requires abstinence at initiation.",
    },

    # ── GAD second-line / adjunctive agents ───────────────────────────────────
    # Added for the GAD algorithm (gad.py). Dose steps sourced from gad.py's
    # MED_KB (FDA-labeled strengths). No dedicated side-effect module exists yet
    # for GABA-analog / TCA / benzodiazepine / antihistamine classes, so these
    # fall back to GENERIC_MODULE via get_side_effect_module() — a known gap,
    # not a blocker (flagged in the summary).
    "pregabalin": {
        "display": "Pregabalin (Lyrica)",
        "class": "GABA analog",
        "role": "secondary",
        "dose_steps": [25, 50, 75, 100, 150, 200, 225, 300],
        "conditions": ["gad"],
        "side_effect_module": "generic",
        "notes": "GAD second-line. Renal dose-adjusted (tiered caps in gad.py). Preferred over mirtazapine in obesity.",
    },
    "gabapentin": {
        "display": "Gabapentin (Neurontin)",
        "class": "GABA analog",
        "role": "secondary",
        "dose_steps": [100, 300, 400, 600, 800],
        "conditions": ["gad"],
        "side_effect_module": "generic",
        "notes": "GAD off-label. Shares the GABA-analog slot with pregabalin (one trial opportunity). Renal dose-adjusted.",
    },
    "imipramine": {
        "display": "Imipramine (Tofranil)",
        "class": "TCA",
        "role": "secondary",
        "dose_steps": [10, 25, 50],
        "conditions": ["gad", "ptsd", "panic"],
        "side_effect_module": "generic",
        "notes": "GAD refractory switch. Panic third-choice TCA — titrate SLOWER than GAD/PTSD (panic patients are sensitive to activating side effects; see panic.py). Excluded in cardiac/geriatric paths. ECG monitoring.",
    },
    "clonazepam": {
        "display": "Clonazepam (Klonopin)",
        "class": "Benzodiazepine",
        "role": "augmentation",
        "dose_steps": [0.5, 1, 2],
        "conditions": ["gad", "panic"],
        "side_effect_module": "generic",
        "notes": "Adjunctive for severe anxiety (GAD-7 ≥ 15; panic PDSS ≥ 16). Preferred general-case benzo; panic target 1 mg/day (a sweet spot, not a titrate-to-max). Avoid with active substance use.",
    },
    "lorazepam": {
        "display": "Lorazepam (Ativan)",
        "class": "Benzodiazepine",
        "role": "augmentation",
        "dose_steps": [0.5, 1, 2],
        "conditions": ["gad", "panic"],
        "side_effect_module": "generic",
        "notes": "Adjunctive benzo preferred in renal/hepatic/geriatric paths (glucuronidation only, no active metabolites). Avoid with active substance use.",
    },
    "alprazolam": {
        "display": "Alprazolam (Xanax)",
        "class": "Benzodiazepine",
        "role": "augmentation",
        "dose_steps": [0.25, 0.5, 1, 2],
        "conditions": ["panic"],
        "side_effect_module": "generic",
        "notes": "Panic only, PRN carve-out for genuinely infrequent situational panic (<= 3x/month), 0.25-0.5 mg. NOT a standing regimen — short half-life makes it a poor fit for scheduled use. Avoid with substance use.",
    },
    "hydroxyzine": {
        "display": "Hydroxyzine (Vistaril/Atarax)",
        "class": "Antihistamine (H1)",
        "role": "augmentation",
        "dose_steps": [10, 25, 50],
        "conditions": ["gad", "ptsd"],
        "side_effect_module": "generic",
        "notes": "Perinatal insomnia adjunct. Excluded first trimester. Non-dependence-forming.",
    },

    # --- PTSD-specific agents (see ptsd.py MED_KB). No dedicated side-effect
    # modules for alpha-agonists/trazodone → GENERIC fallback (prazosin has its own). ---
    "trazodone": {
        "display": "Trazodone (Desyrel)",
        "class": "Antidepressant used as hypnotic",
        "role": "augmentation",
        "dose_steps": [25, 50, 100, 150, 200],
        "conditions": ["ptsd"],
        "side_effect_module": "generic",
        "notes": "PTSD sleep-initiation insomnia, first-line within that branch. Dropped in cardiac (QT) and hepatic paths.",
    },
    "clonidine_xr": {
        "display": "Clonidine ER (Kapvay)",
        "class": "Alpha-2 agonist",
        "role": "augmentation",
        "dose_steps": [0.1, 0.2, 0.3, 0.4],
        "conditions": ["ptsd"],
        "side_effect_module": "generic",
        "notes": "PTSD hyperarousal augmentation. Dropped in cardiac path (bradycardia/AV-block risk).",
    },
    "guanfacine": {
        "display": "Guanfacine (Intuniv)",
        "class": "Alpha-2 agonist",
        "role": "augmentation",
        "dose_steps": [1, 2, 3, 4],
        "conditions": ["ptsd"],
        "side_effect_module": "generic",
        "notes": "PTSD hyperarousal augmentation. Same cardiac exclusion as clonidine.",
    },
    "amitriptyline": {
        "display": "Amitriptyline (Elavil)",
        "class": "TCA",
        "role": "secondary",
        "dose_steps": [10, 25, 50, 75, 100],
        "conditions": ["ptsd"],
        "side_effect_module": "generic",
        "notes": "PTSD third-choice tier (with imipramine/desipramine). Excluded in geriatric. Hepatic max 100 mg. ECG monitoring.",
    },
}


# ---------------------------------------------------------------------------
# Condition → medication mapping
# ---------------------------------------------------------------------------

def get_medications_for_condition(condition_key: str) -> list[dict[str, Any]]:
    """
    Returns all medications appropriate for a condition, sorted by role priority
    (primary first, then augmentation, then secondary) and alphabetically within role.

    Args:
        condition_key: Condition key (e.g. "mdd", "gad", "ptsd").

    Returns:
        List of medication dicts with key added.
    """
    role_order = {"primary": 0, "augmentation": 1, "secondary": 2}

    meds = [
        {"key": k, **v}
        for k, v in MEDICATIONS.items()
        if condition_key in v.get("conditions", [])
    ]

    return sorted(meds, key=lambda m: (role_order.get(m["role"], 9), m["display"]))


def get_medications_for_conditions(condition_keys: list[str]) -> dict[str, list[dict[str, Any]]]:
    """
    Returns medications grouped by condition for the dropdown UI.

    Each condition gets its own group with a header. Medications that appear
    in multiple active conditions are included under each relevant condition
    so the patient can find them by condition context.

    Args:
        condition_keys: List of active condition keys from FollowUpSchedule.

    Returns:
        Dict of {condition_key: [medication dicts]} preserving condition order.
    """
    return {
        condition: get_medications_for_condition(condition)
        for condition in condition_keys
        if condition in CONDITION_DISPLAY_NAMES
    }


def get_dose_steps(medication_key: str) -> list:
    """
    Returns the dose steps for a medication.
    Uses display_doses if present, otherwise formats dose_steps as mg strings.

    Args:
        medication_key: Medication key.

    Returns:
        List of dose strings for the dropdown.
    """
    med = MEDICATIONS.get(medication_key)
    if not med:
        return []

    if "display_doses" in med:
        return med["display_doses"]

    return [f"{d} mg" for d in med["dose_steps"]]


def medication_picker_groups(condition_keys: list[str] | None) -> dict[str, list[dict]]:
    """
    Slim medication list for the picker UI, grouped by condition and filtered to
    the given condition keys (short keys, e.g. "mdd"). If no conditions are given
    (no diagnosis selected), returns a single "all" group with every medication.

    Each item: {key, display, role, doses} where doses is the display-dose list
    (e.g. ["25 mg", "50 mg", ...]) for that medication.
    """
    def _slim(meds: list[dict]) -> list[dict]:
        return [
            {"key": m["key"], "display": m["display"], "role": m.get("role"), "doses": get_dose_steps(m["key"])}
            for m in meds
        ]

    keys = [k for k in (condition_keys or []) if k in CONDITION_DISPLAY_NAMES]
    if keys:
        return {cond: _slim(get_medications_for_condition(cond)) for cond in keys}

    all_meds = [
        {"key": k, "display": v["display"], "role": v.get("role"), "doses": get_dose_steps(k)}
        for k, v in sorted(MEDICATIONS.items(), key=lambda kv: kv[1]["display"])
    ]
    return {"all": all_meds}


def get_side_effect_module_key(medication_key: str) -> str:
    """Returns the side effect module key for a medication."""
    med = MEDICATIONS.get(medication_key)
    if not med:
        return "generic"
    return med.get("side_effect_module", "generic")


# ---------------------------------------------------------------------------
# Condition display names
# ---------------------------------------------------------------------------

CONDITION_DISPLAY_NAMES = {
    "mdd":        "Depression (MDD)",
    "gad":        "Anxiety (GAD)",
    "ptsd":       "PTSD",
    "adhd":       "ADHD",
    "bipolar_i":  "Bipolar I Disorder",
    "bipolar_ii": "Bipolar II Disorder",
    "sud":        "Substance Use Disorder",
}


# ---------------------------------------------------------------------------
# Per-(medication × condition) role map (clinical spec Q0.1).
# ---------------------------------------------------------------------------
# Relocated here from the decision-tool catalog (Q7.2): each drug declares its role for the
# conditions it plays a part in, so the role map lives WITH the shared medication registry
# rather than in a separate central table. The comorbidity BACKBONE RULE stays entirely in
# the reconciliation layer (comorbidity_medication_plan) — this file only supplies per-drug
# role DATA; it does not decide how agents compose across conditions.
#
# Roles: first_line_mono | alt_mono | adjunct_only | contraindicated | symptom_targeted.
# Condition tokens match the registry `conditions` vocabulary. Only pairs that DIFFER from
# the reconciler's default are listed (default: a drug in its engine's `conditions` →
# alt_mono, else not-applicable); antidepressant-in-bipolar is also enforced class-wide in
# the reconciler. A drug's `roles` may name a condition NOT in its `conditions` list — that
# captures an adjunct/augmentation role (e.g. lithium augmenting MDD; buspirone augmenting
# bipolar anxiety) the drug's own engine does not surface.
MEDICATION_ROLES: dict[str, dict[str, str]] = {
    "escitalopram":   {"gad": "first_line_mono", "mdd": "first_line_mono", "ptsd": "alt_mono", "panic": "alt_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "sertraline":     {"gad": "alt_mono", "mdd": "first_line_mono", "ptsd": "first_line_mono", "panic": "first_line_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "paroxetine":     {"gad": "first_line_mono", "mdd": "first_line_mono", "ptsd": "first_line_mono", "panic": "first_line_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "venlafaxine_xr": {"gad": "first_line_mono", "mdd": "first_line_mono", "ptsd": "first_line_mono", "panic": "alt_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "duloxetine":     {"gad": "first_line_mono", "mdd": "first_line_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "fluoxetine":     {"gad": "alt_mono", "mdd": "first_line_mono", "panic": "first_line_mono", "bipolar_i": "contraindicated", "bipolar_ii": "contraindicated"},
    "buspirone":      {"gad": "alt_mono", "mdd": "adjunct_only", "bipolar_i": "adjunct_only", "bipolar_ii": "adjunct_only"},
    "quetiapine":     {"gad": "alt_mono", "mdd": "adjunct_only", "ptsd": "adjunct_only", "bipolar_i": "first_line_mono", "bipolar_ii": "first_line_mono"},
    "aripiprazole":   {"mdd": "adjunct_only", "ptsd": "adjunct_only", "bipolar_i": "first_line_mono", "bipolar_ii": "first_line_mono"},
    "brexpiprazole":  {"mdd": "adjunct_only"},
    "lamotrigine":    {"gad": "adjunct_only", "ptsd": "adjunct_only", "bipolar_i": "first_line_mono", "bipolar_ii": "first_line_mono"},
    "lithium":        {"mdd": "adjunct_only", "bipolar_i": "first_line_mono", "bipolar_ii": "first_line_mono"},
    "divalproex":     {"bipolar_i": "first_line_mono", "bipolar_ii": "first_line_mono"},
    "bupropion_xl":   {"gad": "alt_mono", "mdd": "first_line_mono"},  # GAD: non-first-line, warned (not excluded)
    "pregabalin":     {"gad": "alt_mono"},
    "gabapentin":     {"gad": "adjunct_only"},
    "prazosin":       {"ptsd": "symptom_targeted"},
    "hydroxyzine":    {"gad": "symptom_targeted"},
}

# Inject the declared roles onto each medication entry so any consumer can read
# MEDICATIONS[key]["roles"] directly — the registry is the single source of truth.
for _mk, _roles in MEDICATION_ROLES.items():
    if _mk in MEDICATIONS:
        MEDICATIONS[_mk]["roles"] = _roles
