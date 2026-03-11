from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from pitchcopytrade.api.deps.auth import get_current_subscriber_user
from pitchcopytrade.api.deps.repositories import get_access_repository
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.repositories.contracts import AccessRepository
from pitchcopytrade.services.acl import (
    get_user_visible_recommendation,
    list_user_visible_recommendations,
    user_has_active_access,
)
from pitchcopytrade.storage.local import LocalFilesystemStorage
from pitchcopytrade.storage.minio import MinioStorage
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/app", tags=["app"])


@router.get("/feed", response_class=HTMLResponse)
async def app_feed(
    request: Request,
    user: User = Depends(get_current_subscriber_user),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    recommendations = await list_user_visible_recommendations(repository, user_id=user.id)
    has_access = await user_has_active_access(repository, user_id=user.id)
    return templates.TemplateResponse(
        request,
        "app/feed.html",
        {
            "title": "Лента рекомендаций",
            "user": user,
            "recommendations": recommendations,
            "has_access": has_access,
        },
    )


@router.get("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_detail_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(get_current_subscriber_user),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    recommendation = await get_user_visible_recommendation(
        repository,
        user_id=user.id,
        recommendation_id=recommendation_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return templates.TemplateResponse(
        request,
        "app/recommendation_detail.html",
        {
            "title": recommendation.title or "Рекомендация",
            "user": user,
            "recommendation": recommendation,
            "preview_mode": False,
            "attachment_download_enabled": True,
        },
    )


@router.get("/recommendations/{recommendation_id}/attachments/{attachment_id}")
async def recommendation_attachment_download(
    recommendation_id: str,
    attachment_id: str,
    user: User = Depends(get_current_subscriber_user),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    recommendation = await get_user_visible_recommendation(
        repository,
        user_id=user.id,
        recommendation_id=recommendation_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    attachment = next((item for item in recommendation.attachments if item.id == attachment_id), None)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    storage_provider = attachment.storage_provider or "local_fs"

    if storage_provider == "local_fs":
        payload = LocalFilesystemStorage(bucket_name=attachment.bucket_name).download_bytes(attachment.object_key)
    elif storage_provider == "minio":
        payload = MinioStorage(bucket_name=attachment.bucket_name).download_bytes(attachment.object_key)
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unsupported storage provider")
    headers = {"Content-Disposition": f'attachment; filename="{attachment.original_filename}"'}
    return StreamingResponse(iter([payload]), media_type=attachment.content_type, headers=headers)
