from sqlalchemy import func, select

from app.models.provider import Provider
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[Provider]):
    model = Provider

    def list_by_role(self, role) -> list[Provider]:
        stmt = select(Provider).where(Provider.role == role)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_email(self, email: str) -> Provider | None:
        """Case-insensitive lookup, same pattern as PatientRepository.get_by_mrn."""
        stmt = select(Provider).where(func.lower(Provider.email) == func.lower(email))
        return self.db.execute(stmt).scalar_one_or_none()
