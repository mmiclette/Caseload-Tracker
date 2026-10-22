/**
 * Validated measure definitions for the contact form's scale entry.
 *
 * PHQ-9 and GAD-7 items are transcribed verbatim from the CTMS screenshots
 * Matt supplied (docs/ctms-reference/README.md), including their shared
 * response options and the trailing functional-impairment question — which
 * the CTMS displays but does NOT add to the total.
 *
 * PCL-5, SCARED, SMFQ, and Vanderbilt are deliberately item-less. Their
 * question wording has never appeared legibly in any source material we
 * have, and transcribing a validated instrument from a blurry video frame
 * risks altering it — the same "don't invent it" discipline that keeps
 * their remission/response thresholds unimplemented in
 * app/services/scoring.py. They fall back to direct total entry, which is
 * confirmed CTMS behavior anyway ("the total can also be entered
 * directly"). Add items here only from an authoritative copy of the
 * instrument.
 */

import type { MeasureType } from '../api/types'

export interface ResponseOption {
  label: string
  value: number
}

export interface ScaleDefinition {
  measureType: MeasureType
  /** Display name, as the CTMS labels the scale block. */
  title: string
  /** e.g. "Depression Scale: PHQ-9" — the CTMS's own block heading. */
  blockLabel: string
  prompt?: string
  options?: ResponseOption[]
  items?: string[]
  /**
   * Shown after the scored items and excluded from the total, matching the
   * CTMS (PHQ-9's question 10, GAD-7's question 8).
   */
  impairmentQuestion?: string
  impairmentOptions?: ResponseOption[]
  /** Maximum possible total, for validating direct entry. */
  maxScore?: number
  attribution?: string
  /** Why this scale has no item matrix — surfaced in the UI. */
  directEntryReason?: string
}

const FREQUENCY_OPTIONS: ResponseOption[] = [
  { label: 'Not at all', value: 0 },
  { label: 'Several days', value: 1 },
  { label: 'More than half the days', value: 2 },
  { label: 'Nearly every day', value: 3 },
]

const DIFFICULTY_OPTIONS: ResponseOption[] = [
  { label: 'Not difficult at all', value: 0 },
  { label: 'Somewhat difficult', value: 1 },
  { label: 'Very difficult', value: 2 },
  { label: 'Extremely difficult', value: 3 },
]

const IMPAIRMENT_QUESTION =
  'If you checked off any problems on this questionnaire so far, how difficult have these problems made it for you to do your work, take care of things at home, or get along with other people?'

export const SCALES: Record<MeasureType, ScaleDefinition> = {
  PHQ9: {
    measureType: 'PHQ9',
    title: 'PHQ-9',
    blockLabel: 'Depression Scale: PHQ-9',
    prompt:
      'Over the last 2 weeks, how often have you been bothered by any of the following problems?',
    options: FREQUENCY_OPTIONS,
    items: [
      'Little interest or pleasure in doing things',
      'Feeling down, depressed, or hopeless',
      'Trouble falling or staying asleep, or sleeping too much',
      'Feeling tired or having little energy',
      'Poor appetite or overeating',
      'Feeling bad about yourself — or that you are a failure or have let yourself or your family down',
      'Trouble concentrating on things, such as reading the newspaper or watching television',
      'Moving or speaking so slowly that other people could have noticed. Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual',
      'Thoughts that you would be better off dead, or of hurting yourself in some way',
    ],
    impairmentQuestion: IMPAIRMENT_QUESTION,
    impairmentOptions: DIFFICULTY_OPTIONS,
    maxScore: 27,
    attribution: 'Copyright © Pfizer Inc. All rights reserved. Reproduced with permission.',
  },
  GAD7: {
    measureType: 'GAD7',
    title: 'GAD-7',
    blockLabel: 'Anxiety Scale: GAD-7',
    prompt: 'Over the last 2 weeks, how often have you been bothered by the following problems?',
    options: FREQUENCY_OPTIONS,
    items: [
      'Feeling nervous, anxious or on edge',
      'Not being able to stop or control worrying',
      'Worrying too much about different things',
      'Trouble relaxing',
      'Being so restless that it is hard to sit still',
      'Becoming easily annoyed or irritable',
      'Feeling afraid as if something awful might happen',
    ],
    impairmentQuestion: IMPAIRMENT_QUESTION,
    impairmentOptions: DIFFICULTY_OPTIONS,
    maxScore: 21,
    attribution: 'Developed by Drs. Robert L. Spitzer, Janet B.W. Williams, Kurt Kroenke and colleagues.',
  },
  PCL5: {
    measureType: 'PCL5',
    title: 'PCL-5',
    blockLabel: 'PTSD Scale: PCL-5 (Past Month Version)',
    directEntryReason:
      'Item wording is not in our verified source material, so enter the total from the completed instrument.',
  },
  SCARED: {
    measureType: 'SCARED',
    title: 'SCARED',
    blockLabel: 'Pediatric Anxiety Scale: SCARED',
    directEntryReason:
      'Item wording is not in our verified source material, so enter the total from the completed instrument.',
  },
  SMFQ: {
    measureType: 'SMFQ',
    title: 'SMFQ',
    blockLabel: 'Pediatric Depression Scale: SMFQ',
    directEntryReason:
      'Item wording is not in our verified source material, so enter the total from the completed instrument.',
  },
  VANDERBILT: {
    measureType: 'VANDERBILT',
    title: 'Vanderbilt',
    blockLabel: 'Pediatric ADHD Scale: NICHQ Vanderbilt',
    directEntryReason:
      'Item wording is not in our verified source material, so enter the total from the completed instrument.',
  },
  OTHER: {
    measureType: 'OTHER',
    title: 'Other measure',
    blockLabel: 'Other measure',
    directEntryReason: 'Enter the total for this measure.',
  },
}

/** Adult scales first, then pediatric — the order the CTMS lists them in. */
export const SELECTABLE_MEASURES: MeasureType[] = [
  'PHQ9',
  'GAD7',
  'PCL5',
  'SCARED',
  'SMFQ',
  'VANDERBILT',
]

/** Which measures a condition is normally tracked on, for sensible defaults. */
export const CONDITION_DEFAULT_MEASURES: Record<string, MeasureType[]> = {
  depression: ['PHQ9'],
  anxiety: ['GAD7'],
  ptsd: ['PCL5'],
  adhd: ['VANDERBILT'],
  substance_use: [],
}
