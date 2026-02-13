from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.enums import AddonCategory
from reservas_api.infrastructure.db.models import RentalAddonModel


class MySQLAddonCatalogRepository:
    """Reads active add-ons from the rental_addons catalog table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_active_addons_by_codes(
        self, codes: list[str]
    ) -> dict[str, dict[str, str]]:
        """Return {code: {"name": ..., "category": ...}} for active addons."""
        async with self._session_factory() as session:
            result = await session.exec(
                select(RentalAddonModel).where(
                    RentalAddonModel.code.in_(codes),
                    RentalAddonModel.is_active == True,  # noqa: E712
                )
            )
            return {
                row.code: {"name": row.name, "category": row.category}
                for row in result.all()
            }

    async def get_all_active(
        self, category: AddonCategory | None = None
    ) -> list[RentalAddonModel]:
        """Return all active add-ons, optionally filtered by category."""
        async with self._session_factory() as session:
            query = select(RentalAddonModel).where(
                RentalAddonModel.is_active == True,  # noqa: E712
            )
            if category is not None:
                query = query.where(RentalAddonModel.category == category)
            query = query.order_by(RentalAddonModel.sort_order)
            result = await session.exec(query)
            return list(result.all())
