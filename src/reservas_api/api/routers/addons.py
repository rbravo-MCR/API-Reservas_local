from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from reservas_api.domain.enums import AddonCategory
from reservas_api.infrastructure.db.models import RentalAddonModel
from reservas_api.infrastructure.repositories import MySQLAddonCatalogRepository

router = APIRouter(prefix="/addons", tags=["addons"])


def _get_catalog(request: Request) -> MySQLAddonCatalogRepository:
    return MySQLAddonCatalogRepository(request.app.state.session_factory)


@router.get(
    "",
    summary="List available add-ons",
    description="Returns all active rental add-ons from the catalog, optionally filtered by category.",
)
async def list_addons(
    catalog: Annotated[MySQLAddonCatalogRepository, Depends(_get_catalog)],
    category: AddonCategory | None = Query(default=None, description="Filter by category"),
) -> list[dict]:
    """Return active add-ons, optionally filtered by category."""
    addons = await catalog.get_all_active(category=category)
    return [
        {
            "code": a.code,
            "name": a.name,
            "category": a.category,
            "description": a.description,
            "sort_order": a.sort_order,
        }
        for a in addons
    ]
