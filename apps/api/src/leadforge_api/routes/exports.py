"""Export routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from leadforge_database.models import ExportFormat

from leadforge_api.core.deps import CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.schemas import CreateExportRequest, CreateExportResponse, ExportResponse
from leadforge_api.services import export_service

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=None, status_code=201)
async def create_export(
    body: CreateExportRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    exp = await export_service.create_export(
        session, user_id, ExportFormat(body.format.value), body.filters
    )
    return success(CreateExportResponse(export_id=exp.id).model_dump(mode="json"))


@router.get("", response_model=None)
async def list_exports(user_id: CurrentUserId, session: DBSession) -> dict:
    exports = await export_service.list_exports(session, user_id)
    return success([ExportResponse.model_validate(e).model_dump(mode="json") for e in exports])


@router.get("/{export_id}/download", response_model=None)
async def download_export(
    export_id: str, user_id: CurrentUserId, session: DBSession
) -> FileResponse | Response:
    exp = await export_service.get_export(session, user_id, UUID(export_id))
    if not exp.file_path:
        return Response(
            content='{"success":false,"error":{"code":"NOT_READY","message":"Export not ready"}}',
            media_type="application/json",
            status_code=404,
        )
    path = export_service.resolve_export_path(exp)
    if not path.exists():
        return Response(
            content='{"success":false,"error":{"code":"NOT_FOUND","message":"File missing"}}',
            media_type="application/json",
            status_code=404,
        )
    media_type = {
        "CSV": "text/csv",
        "JSON": "application/json",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(exp.format.value, "application/octet-stream")
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=f"leads.{exp.format.value.lower()}",
    )
