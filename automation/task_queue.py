from __future__ import annotations

import uuid
import enum
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Any

logger = logging.getLogger("automation.task_queue")


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    progress_message: str = ""
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    estimated_duration: str = ""
    cancellation_requested: bool = False
    _target: Callable | None = None
    _args: tuple = ()
    _kwargs: dict = field(default_factory=dict)
    _thread: threading.Thread | None = None


class TaskQueue:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._progress_callbacks: list[Callable] = []

    def enqueue(self, description: str, target: Callable, *args, estimated_duration: str = "", **kwargs) -> Task:
        task = Task(
            description=description,
            estimated_duration=estimated_duration,
            _target=target,
            _args=args,
            _kwargs=kwargs,
        )
        with self._lock:
            self._tasks[task.id] = task
        thread = threading.Thread(target=self._run_task, args=(task.id,), daemon=True)
        with self._lock:
            task._thread = thread
        thread.start()
        logger.info("Task %s enqueued: %s", task.id, description)
        return task

    def _run_task(self, task_id: str) -> None:
        task = self._get_task(task_id)
        if task is None:
            return
        task.status = TaskStatus.RUNNING
        try:
            result = task._target(task, *task._args, **task._kwargs)
            if task.cancellation_requested:
                task.status = TaskStatus.CANCELLED
            else:
                task.status = TaskStatus.COMPLETED
                task.result = result
            task.completed_at = time.time()
            logger.info("Task %s completed", task_id)
            self._notify(task)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
            logger.error("Task %s failed: %s", task_id, exc)
            self._notify(task)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return False
            task.cancellation_requested = True
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
        logger.info("Task %s cancelled", task_id)
        return True

    def get_task(self, task_id: str) -> Task | None:
        return self._get_task(task_id)

    def _get_task(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update_progress(self, task_id: str, progress: int, message: str = "") -> None:
        task = self._get_task(task_id)
        if task is None:
            return
        with self._lock:
            task.progress = min(max(progress, 0), 100)
            task.progress_message = message
        self._notify(task)

    @property
    def active_tasks(self) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]

    @property
    def all_tasks(self) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())

    def on_progress(self, callback: Callable) -> None:
        self._progress_callbacks.append(callback)

    def _notify(self, task: Task) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(task)
            except Exception:
                logger.exception("Progress callback error")
