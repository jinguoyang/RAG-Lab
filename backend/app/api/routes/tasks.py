"""后台任务管理端点。"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.task import TaskDetailDTO, TaskListResponse, TaskSummaryDTO
from app.services.task_manager import task_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks() -> TaskListResponse:
    tasks = task_manager.get_all_tasks()
    return TaskListResponse(tasks=[TaskSummaryDTO(**t.to_summary()) for t in tasks])


@router.get("/{task_id}", response_model=TaskDetailDTO)
def get_task(task_id: str) -> TaskDetailDTO:
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TASK_NOT_FOUND")
    return TaskDetailDTO(**task.to_dict())


@router.get("/{task_id}/stream")
async def stream_task(task_id: str) -> StreamingResponse:
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TASK_NOT_FOUND")

    async def event_generator() -> AsyncGenerator[str, None]:
        async for data in task_manager.subscribe(task_id):
            event = data.get("event", "message")
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str) -> TaskSummaryDTO:
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TASK_NOT_FOUND")
    if not task_manager.cancel_task(task_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TASK_NOT_CANCELLABLE")
    return TaskSummaryDTO(**task.to_summary())


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(task_id: str) -> None:
    if not task_manager.remove_task(task_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TASK_NOT_REMOVABLE")
