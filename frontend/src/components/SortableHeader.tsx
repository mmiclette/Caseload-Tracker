import { useMemo, useState } from 'react'

export type SortDirection = 'asc' | 'desc'

export interface SortState<K extends string> {
  key: K
  direction: SortDirection
}

/**
 * Column sorting for the caseload and report tables.
 *
 * The AIMS design-considerations guide is explicit that "all columns should
 * be sortable, allowing providers to quickly rank patients by symptom scores
 * or by the date of last contact" — so sorting is a requirement, not polish.
 * Nulls always sort last regardless of direction: an empty cell means "not
 * recorded", which shouldn't crowd the top of a list a BHCM is triaging.
 */
export function useSort<T, K extends string>(
  rows: T[],
  accessors: Record<K, (row: T) => string | number | null>,
  initial: SortState<K>,
) {
  const [sort, setSort] = useState<SortState<K>>(initial)

  const sorted = useMemo(() => {
    const accessor = accessors[sort.key]
    const factor = sort.direction === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const left = accessor(a)
      const right = accessor(b)
      if (left === null && right === null) return 0
      if (left === null) return 1
      if (right === null) return -1
      if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor
      return String(left).localeCompare(String(right)) * factor
    })
    // accessors is a literal recreated each render; sort state is the real input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort])

  function toggle(key: K) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' },
    )
  }

  return { sorted, sort, toggle }
}

export function SortHeader<K extends string>({
  label,
  sortKey,
  sort,
  onSort,
  align,
  title,
}: {
  label: string
  sortKey: K
  sort: SortState<K>
  onSort: (key: K) => void
  align?: 'numeric' | 'center'
  title?: string
}) {
  const active = sort.key === sortKey
  const className = align === 'numeric' ? 'is-numeric' : align === 'center' ? 'is-center' : undefined
  return (
    <th className={className} title={title} aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="data-table__sort" onClick={() => onSort(sortKey)}>
        {label}
        <span
          className={`data-table__sort-arrow${active ? '' : ' data-table__sort-arrow--inactive'}`}
          aria-hidden="true"
        >
          {active && sort.direction === 'desc' ? '▼' : '▲'}
        </span>
      </button>
    </th>
  )
}
