from fastapi import FastAPI

from app.routes import (
    audit_log,
    auth,
    care_team_assignments,
    clinic_assignments,
    consultations,
    contacts,
    episodes,
    medications,
    patients,
    profile_entries,
    providers,
    referrals,
    reminders,
    reports,
)

app = FastAPI(title="CoCM Registry API", version="0.1.0")

app.include_router(auth.router)
app.include_router(audit_log.router)
app.include_router(patients.router)
app.include_router(episodes.router)
app.include_router(providers.router)
app.include_router(contacts.router)
app.include_router(care_team_assignments.router)
app.include_router(clinic_assignments.router)
app.include_router(consultations.router)
app.include_router(reminders.router)
app.include_router(referrals.router)
app.include_router(medications.router)
app.include_router(profile_entries.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
