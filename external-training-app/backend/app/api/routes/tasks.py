"""任务管理代理端点 - 转发到平台 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

import httpx
from app.core.config import get_settings
from app.services.platform_client import PlatformClient

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_client() -> PlatformClient:
    settings = get_settings()
    return PlatformClient(settings.platform_base_url, settings.platform_api_key)


@router.get("")
def list_tasks():
    """获取所有任务列表。"""
    try:
        client = _get_client()
        return client.list_tasks()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:200])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{task_id}")
def get_task(task_id: str):
    """获取任务详情。"""
    try:
        client = _get_client()
        return client.get_task(task_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:200])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE 流代理 - 转发平台任务事件流。"""
    settings = get_settings()
    url = f"{settings.platform_base_url}/tasks/{task_id}/stream"
    headers = {"Authorization": f"Bearer {settings.platform_api_key}"}

    async def event_generator():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, headers=headers, timeout=300.0) as resp:
                async for line in resp.aiter_lines():
                    yield line + "\n"
                    if line.strip() == "":
                        yield "\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str):
    """取消任务。"""
    try:
        client = _get_client()
        return client.cancel_task(task_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:200])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(task_id: str):
    """删除任务。"""
    try:
        client = _get_client()
        client.remove_task(task_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:200])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
