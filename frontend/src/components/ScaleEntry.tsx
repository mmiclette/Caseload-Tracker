import { SCALES } from '../lib/scales'
import type { MeasureType } from '../api/types'
import './ScaleEntry.css'

/**
 * One scale block on the contact form.
 *
 * Mirrors the CTMS's scale-driven entry: a titled block whose header carries
 * the running total, a question matrix where each row is one item and each
 * column one response option (with its numeric value shown beside the
 * radio), and the trailing functional-impairment question that displays but
 * doesn't score. Clicking answers recomputes the total automatically; the
 * total can also be typed directly, which is the only option for measures
 * whose items we don't have verified wording for (see lib/scales.ts).
 */

export interface ScaleResponse {
  /** Item index → selected value. Empty until the clinician answers. */
  answers: Record<number, number>
  /** Functional-impairment answer, displayed but never added to the total. */
  impairment: number | null
  /** Directly-typed total, which overrides the computed one when set. */
  manualTotal: number | null
}

export const EMPTY_RESPONSE: ScaleResponse = { answers: {}, impairment: null, manualTotal: null }

/**
 * The score this scale will submit, or null if nothing has been entered.
 * A manually-typed total always wins; otherwise every item must be answered
 * before a total counts — a partially completed scale isn't a valid score.
 */
export function resolveScore(
  measureType: MeasureType,
  response: ScaleResponse,
): number | null {
  if (response.manualTotal !== null) return response.manualTotal
  const definition = SCALES[measureType]
  if (!definition.items) return null
  const answered = Object.keys(response.answers).length
  if (answered < definition.items.length) return null
  return definition.items.reduce((sum, _item, i) => sum + (response.answers[i] ?? 0), 0)
}

export function ScaleEntry({
  measureType,
  response,
  onChange,
  onRemove,
}: {
  measureType: MeasureType
  response: ScaleResponse
  onChange: (next: ScaleResponse) => void
  onRemove: () => void
}) {
  const definition = SCALES[measureType]
  const items = definition.items
  const answeredCount = Object.keys(response.answers).length
  const computed = items
    ? items.reduce((sum, _item, i) => sum + (response.answers[i] ?? 0), 0)
    : null
  const complete = items ? answeredCount === items.length : response.manualTotal !== null
  const displayTotal = response.manualTotal ?? (items && answeredCount > 0 ? computed : null)

  return (
    <section className="scale">
      <header className="scale__header">
        <h3 className="scale__title">{definition.blockLabel}</h3>
        <div className="scale__total">
          <label className="scale__total-label" htmlFor={`total-${measureType}`}>
            Score
          </label>
          <input
            id={`total-${measureType}`}
            className="input scale__total-input"
            type="number"
            min={0}
            max={definition.maxScore}
            inputMode="numeric"
            value={displayTotal ?? ''}
            placeholder={items ? '—' : 'total'}
            onChange={(e) =>
              onChange({
                ...response,
                manualTotal: e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
          {definition.maxScore && <span className="scale__max">/ {definition.maxScore}</span>}
          {items && (
            <span className={`scale__progress${complete ? ' is-complete' : ''}`}>
              {answeredCount}/{items.length} answered
            </span>
          )}
          <button type="button" className="btn btn--ghost btn--sm" onClick={onRemove}>
            Remove
          </button>
        </div>
      </header>

      {items && definition.options ? (
        <>
          <table className="scale__matrix">
            <thead>
              <tr>
                <th scope="col" className="scale__prompt">
                  {definition.prompt}
                </th>
                {definition.options.map((option) => (
                  <th scope="col" key={option.value} className="scale__option-head">
                    {option.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => {
                const answered = response.answers[index] !== undefined
                return (
                  <tr key={index} className={answered ? 'is-answered' : undefined}>
                    <th scope="row" className="scale__item">
                      <span className="scale__item-number">{index + 1}.</span> {item}
                    </th>
                    {definition.options!.map((option) => (
                      <td key={option.value} className="scale__cell">
                        <label className="scale__radio">
                          <input
                            type="radio"
                            name={`${measureType}-${index}`}
                            checked={response.answers[index] === option.value}
                            onChange={() =>
                              onChange({
                                ...response,
                                answers: { ...response.answers, [index]: option.value },
                                // A fresh item answer resumes auto-totalling.
                                manualTotal: null,
                              })
                            }
                          />
                          <span className="scale__radio-value">{option.value}</span>
                        </label>
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>

          {definition.impairmentQuestion && definition.impairmentOptions && (
            <div className="scale__impairment">
              <p className="scale__impairment-question">
                {items.length + 1}. {definition.impairmentQuestion}
                <span className="scale__impairment-note">Not included in the total</span>
              </p>
              <div className="scale__impairment-options">
                {definition.impairmentOptions.map((option) => (
                  <label key={option.value} className="scale__impairment-option">
                    <input
                      type="radio"
                      name={`${measureType}-impairment`}
                      checked={response.impairment === option.value}
                      onChange={() => onChange({ ...response, impairment: option.value })}
                    />
                    {option.label}
                    <span className="scale__radio-value">{option.value}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {definition.attribution && (
            <p className="scale__attribution">{definition.attribution}</p>
          )}
        </>
      ) : (
        <p className="scale__direct-entry">{definition.directEntryReason}</p>
      )}
    </section>
  )
}
