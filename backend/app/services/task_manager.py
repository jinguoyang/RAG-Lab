"""后台任务管理器 - 内存存储，不持久化。"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    PLAN_GENERATION = "plan_generation"
    QUESTION_GENERATION = "question_generation"
    OTHER = "other"


@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "data": self.data,
        }


@dataclass
class Task:
    id: str
    type: TaskType
    title: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    logs: list[LogEntry] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    _subscribers: list[asyncio.Queue] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "logs": [log.to_dict() for log in self.logs],
            "result": self.result,
            "error": self.error,
        }

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class TaskManager:
    _instance: TaskManager | None = None
    _tasks: dict[str, Task]

    def __new__(cls) -> TaskManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
        return cls._instance

    def create_task(self, task_type: TaskType, title: str, task_id: str | None = None) -> Task:
        task_id = task_id or str(uuid.uuid4())
        task = Task(id=task_id, type=task_type, title=title)
        self._tasks[task_id] = task
        logger.info("Task created: %s (%s)", task_id, title)
        self._notify_subscribers(task_id, {"event": "created", "task": task.to_summary()})
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def get_active_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]

    def start_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)
        self._notify_subscribers(task_id, {"event": "started", "task": task.to_summary()})

    def complete_task(self, task_id: str, result: Any = None) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        task.result = result
        summary = task.to_summary()
        summary["result"] = result
        self._notify_subscribers(task_id, {"event": "completed", "task": summary})
        logger.info("Task completed: %s", task_id)

    def fail_task(self, task_id: str, error: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(UTC)
        task.error = error
        self._notify_subscribers(task_id, {"event": "failed", "task": task.to_summary()})
        logger.error("Task failed: %s - %s", task_id, error)

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(UTC)
        self._notify_subscribers(task_id, {"event": "cancelled", "task": task.to_summary()})
        return True

    def append_log(self, task_id: str, level: str, message: str, data: dict[str, Any] | None = None) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        entry = LogEntry(timestamp=datetime.now(UTC), level=level, message=message, data=data)
        task.logs.append(entry)
        self._notify_subscribers(task_id, {"event": "log", "log": entry.to_dict()})

    def append_token(self, task_id: str, token: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        entry = LogEntry(timestamp=datetime.now(UTC), level="token", message=token)
        task.logs.append(entry)
        self._notify_subscribers(task_id, {"event": "token", "token": token})

    def _notify_subscribers(self, task_id: str, data: dict[str, Any]) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        for queue in task._subscribers:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full for task %s", task_id)

    async def subscribe(self, task_id: str) -> AsyncGenerator[dict[str, Any], None]:
        task = self._tasks.get(task_id)
        if not task:
            return

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        task._subscribers.append(queue)

        try:
            yield {"event": "snapshot", "task": task.to_dict()}
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield data
                    if data.get("event") in ("completed", "failed", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat"}
        finally:
            task._subscribers.remove(queue)

    def remove_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False
        del self._tasks[task_id]
        return True


task_manager = TaskManager()
