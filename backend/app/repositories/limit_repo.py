from __future__ import annotations

from app.models.entities import DynamicTestLimit
from app.repositories.base import FilterSpec, Page, PageParams, Repository, SortParams


class DynamicTestLimitRepository(Repository[DynamicTestLimit]):
    model = DynamicTestLimit

    async def list_limits(
        self,
        *,
        tester_id: str | None = None,
        site_id: str | None = None,
        lot_id: str | None = None,
        status: str | None = None,
        page: PageParams | None = None,
    ) -> Page[DynamicTestLimit]:
        return await self.paginate(
            filters=FilterSpec(
                equals={
                    "tester_id": tester_id,
                    "site_id": site_id,
                    "lot_id": lot_id,
                    "status": status,
                },
                time_field="updated_at",
            ),
            sort=SortParams(field="updated_at", direction="desc"),
            page=page,
            default_sort_field="updated_at",
        )
