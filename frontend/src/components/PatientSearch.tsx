import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Patient } from '../api/types'
import './PatientSearch.css'

/**
 * The CTMS's centered "Patient: ID, Name, MRN" search box.
 *
 * The API has no search endpoint yet, so this fetches the patient list once
 * per keystroke-debounce and filters client-side. That's fine at a single
 * program's caseload size and keeps us from inventing a backend contract
 * before the search semantics are confirmed; if caseloads grow, this is the
 * spot that wants a real `GET /patients?q=` behind it.
 */
export function PatientSearch() {
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<Patient[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const term = query.trim().toLowerCase()
    if (term.length < 2) {
      setMatches([])
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      api
        .get<Patient[]>('/patients', { limit: 500 })
        .then((patients) => {
          if (cancelled) return
          setMatches(
            patients
              .filter(
                (p) =>
                  p.name.toLowerCase().includes(term) ||
                  p.mrn.toLowerCase().includes(term) ||
                  String(p.patient_id).includes(term),
              )
              .slice(0, 8),
          )
          setOpen(true)
        })
        .catch(() => {
          if (!cancelled) setMatches([])
        })
    }, 200)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  function select(patient: Patient) {
    setQuery('')
    setOpen(false)
    navigate(`/patients/${patient.patient_id}`)
  }

  return (
    <div className="patient-search" ref={containerRef}>
      <span className="patient-search__icon" aria-hidden="true">
        ⌕
      </span>
      <input
        className="patient-search__input"
        type="search"
        value={query}
        placeholder="Search name, patient ID, or MRN"
        aria-label="Search patients by name, patient ID, or MRN"
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => matches.length > 0 && setOpen(true)}
      />
      {open && matches.length > 0 && (
        <ul className="patient-search__results">
          {matches.map((patient) => (
            <li key={patient.patient_id}>
              <button type="button" onClick={() => select(patient)}>
                <span className="patient-search__name">{patient.name}</span>
                <span className="patient-search__meta">
                  MRN {patient.mrn} · ID {patient.patient_id}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
