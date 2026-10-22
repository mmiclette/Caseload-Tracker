import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { useAuth } from './auth/AuthContext'
import { ActivePatients } from './pages/ActivePatients'
import { CaseloadStatistics } from './pages/CaseloadStatistics'
import { ClinicalDashboard } from './pages/ClinicalDashboard'
import { CompletedEpisodes } from './pages/CompletedEpisodes'
import { DeactivatePatient } from './pages/DeactivatePatient'
import { DrrReport } from './pages/DrrReport'
import { EnrollPatient } from './pages/EnrollPatient'
import { InactivePatients } from './pages/InactivePatients'
import { Login } from './pages/Login'
import { Medications } from './pages/Medications'
import { PatientProfile } from './pages/PatientProfile'
import { QualityMetrics } from './pages/QualityMetrics'
import { RecordConsultation } from './pages/RecordConsultation'
import { RecordContact } from './pages/RecordContact'
import { Reminders } from './pages/Reminders'
import { TimeTracker } from './pages/TimeTracker'
import { TreatmentHistory } from './pages/TreatmentHistory'

export function App() {
  const { provider } = useAuth()

  // The token lives in memory only (see api/client.ts), so an unauthenticated
  // app state is the login screen — there's no session to rehydrate.
  if (!provider) return <Login />

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/reminders" replace />} />
        <Route path="/reminders" element={<Reminders />} />

        {/* Caseload. Static segments outrank the dynamic :patientId route. */}
        <Route path="/patients" element={<ActivePatients />} />
        <Route path="/patients/inactive" element={<InactivePatients />} />
        <Route path="/patients/new" element={<EnrollPatient />} />
        <Route path="/patients/:patientId" element={<ClinicalDashboard />} />
        <Route path="/patients/:patientId/contacts" element={<TreatmentHistory />} />
        <Route path="/patients/:patientId/contacts/new" element={<RecordContact />} />
        <Route path="/patients/:patientId/consultations/new" element={<RecordConsultation />} />
        <Route path="/patients/:patientId/medications" element={<Medications />} />
        <Route path="/patients/:patientId/profile" element={<PatientProfile />} />
        <Route path="/patients/:patientId/deactivate" element={<DeactivatePatient />} />

        {/* Reports */}
        <Route path="/reports/caseload-statistics" element={<CaseloadStatistics />} />
        <Route path="/reports/quality-metrics" element={<QualityMetrics />} />
        <Route path="/reports/completed-episodes" element={<CompletedEpisodes />} />
        <Route path="/reports/drr" element={<DrrReport />} />
        <Route path="/reports/time-tracker" element={<TimeTracker />} />

        <Route path="*" element={<Navigate to="/reminders" replace />} />
      </Route>
    </Routes>
  )
}
