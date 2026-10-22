from sqlalchemy import select

from app.models.enums import ProfileSection
from app.models.profile_entry import ProfileEntry
from app.repositories.base import BaseRepository


class ProfileEntryRepository(BaseRepository[ProfileEntry]):
    model = ProfileEntry

    def list_by_patient(
        self, patient_id: int, section: ProfileSection | None = None
    ) -> list[ProfileEntry]:
        """
        Ordered for display: grouped by section and sub-field, newest entry
        first within each sub-field (the newest is the "current" value; the
        rest are its history — the table is append-only, so ordering is how
        supersession is expressed). profile_entry_id breaks same-day ties:
        the later insert wins.
        """
        stmt = select(ProfileEntry).where(ProfileEntry.patient_id == patient_id)
        if section is not None:
            stmt = stmt.where(ProfileEntry.section == section)
        stmt = stmt.order_by(
            ProfileEntry.section,
            ProfileEntry.sub_field,
            ProfileEntry.recorded_date.desc(),
            ProfileEntry.profile_entry_id.desc(),
        )
        return list(self.db.execute(stmt).scalars().all())
