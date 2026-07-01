from __future__ import annotations

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any, Callable

from automation.execution_layer import ExecutionLayer
from automation.task_queue import TaskQueue, Task
from automation.notifications import NotificationManager
from automation.session import SessionManager
from automation.permissions import PermissionManager

logger = logging.getLogger("automation.command_router")


HandlerFunc = Callable[..., str]


class CommandRouter:
    def __init__(
        self,
        execution_layer: ExecutionLayer,
        task_queue: TaskQueue,
        notifications: NotificationManager,
        session: SessionManager,
        permissions: PermissionManager,
        repository_root: Path,
    ):
        self._execution = execution_layer
        self._queue = task_queue
        self._notifications = notifications
        self._session = session
        self._permissions = permissions
        self._repository_root = repository_root
        self._handlers: dict[str, HandlerFunc] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("status", self._cmd_status)
        self.register("resume", self._cmd_resume)
        self.register("stop", self._cmd_stop)
        self.register("pause", self._cmd_pause)
        self.register("logs", self._cmd_logs)
        self.register("research", self._cmd_research)
        self.register("implement", self._cmd_implement)
        self.register("commit", self._cmd_commit)
        self.register("push", self._cmd_push)
        self.register("pull", self._cmd_pull)
        self.register("summary", self._cmd_summary)
        self.register("document", self._cmd_document)
        self.register("test", self._cmd_test)
        self.register("backtest", self._cmd_backtest)
        self.register("benchmark", self._cmd_benchmark)
        self.register("shutdown", self._cmd_shutdown)
        self.register("restart", self._cmd_restart)
        self.register("help", self._cmd_help)
        self.register("cancel", self._cmd_cancel)
        self.register("tasks", self._cmd_tasks)
        self.register("providers", self._cmd_providers)

    def register(self, command: str, handler: HandlerFunc) -> None:
        self._handlers[command.lower()] = handler

    def route(self, command: str, args: str = "", requires_confirmation: bool = False) -> str:
        cmd = command.lower().strip()
        if cmd not in self._handlers:
            return f"Unknown command: {command}\nType /help for available commands."
        handler = self._handlers[cmd]
        if requires_confirmation:
            return f"This operation modifies repository history.\n\nReply:\nCONFIRM {command.upper()}"
        try:
            return handler(args)
        except Exception as exc:
            logger.exception("Handler error for %s", command)
            self._notifications.exception_occurred(f"command_router.{command}", str(exc))
            return f"Error executing {command}: {exc}"

    def handle_task_result(self, task: Task) -> None:
        if task.status.value == "completed":
            self._notifications.task_completed(task.id, task.description)
        elif task.status.value == "failed":
            self._notifications.task_failed(task.id, task.description, task.error or "Unknown error")

    def _cmd_help(self, args: str = "") -> str:
        commands = sorted(self._handlers.keys())
        return (
            "*Telegram Control - Available Commands*\n\n"
            + "\n".join(f"/{c}" for c in commands)
            + "\n\nUse /help <command> for details."
        )

    def _cmd_status(self, args: str = "") -> str:
        self._session.refresh()
        s = self._session.state
        lines = [
            f"*Branch:* {s.current_branch or 'unknown'}",
            f"*Last commit:* {s.last_commit_hash} {s.last_commit_message}",
            f"*Dirty:* {'Yes' if s.is_dirty else 'No'}",
            f"*Provider:* {self._execution.active_provider}",
        ]
        if s.is_dirty:
            lines.append(f"*Changes:* {len(s.pending_changes)} file(s)")
        return "\n".join(lines)

    def _cmd_resume(self, args: str = "") -> str:
        return "Resume: Not yet implemented."

    def _cmd_stop(self, args: str = "") -> str:
        for t in self._queue.active_tasks:
            self._queue.cancel(t.id)
        return "All active tasks cancelled."

    def _cmd_pause(self, args: str = "") -> str:
        return "Pause: Not yet implemented."

    def _cmd_logs(self, args: str = "") -> str:
        log_file = self._repository_root / "logs" / "telegram.log"
        if not log_file.exists():
            return "No log file found."
        lines = log_file.read_text(encoding="utf-8").splitlines()
        tail = lines[-30:] if len(lines) > 30 else lines
        return f"*Last {len(tail)} log lines:*\n```\n" + "\n".join(tail) + "\n```"

    def _cmd_research(self, args: str = "") -> str:
        if not args.strip():
            return "Usage: /research <topic>"
        task = self._queue.enqueue(
            description=f"Research: {args}",
            target=self._task_research,
            args,
        )
        return f"Task #{task.id} started: Researching '{args}'"

    def _task_research(self, task: Task, topic: str) -> str:
        self._queue.update_progress(task.id, 10, "Analyzing request...")
        result = self._execution.execute(f"research {topic}")
        self._queue.update_progress(task.id, 100, "Research complete")
        return result.output if result.success else f"Research failed: {result.error}"

    def _cmd_implement(self, args: str = "") -> str:
        if not args.strip():
            return "Usage: /implement <description>"
        task = self._queue.enqueue(
            description=f"Implement: {args}",
            target=self._task_implement,
            args,
            estimated_duration="calculating...",
        )
        return f"Task #{task.id} started: Implementing '{args}'"

    def _task_implement(self, task: Task, description: str) -> str:
        self._queue.update_progress(task.id, 5, "Planning...")
        result = self._execution.execute(f"implement {description}")
        if result.success:
            self._queue.update_progress(task.id, 80, "Running tests...")
            test_result = self._execution.execute("test")
            if not test_result.success:
                self._notifications.tests_failed(test_result.error or "Unknown")
            self._queue.update_progress(task.id, 90, "Generating documentation...")
            self._save_task_doc(task.id, description, result)
        self._queue.update_progress(task.id, 100, "Done")
        return result.output

    def _cmd_commit(self, args: str = "") -> str:
        msg = args.strip() or "Update via Telegram"
        task = self._queue.enqueue(
            description=f"Commit: {msg}",
            target=self._task_commit,
            msg,
        )
        return f"Task #{task.id} started: Committing..."

    def _task_commit(self, task: Task, message: str) -> str:
        self._queue.update_progress(task.id, 20, "Staging changes...")
        subprocess.run(["git", "add", "-A"], cwd=self._repository_root, capture_output=True, timeout=30)
        self._queue.update_progress(task.id, 50, "Creating commit...")
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self._repository_root, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            self._queue.update_progress(task.id, 100, "Commit created")
            self._notifications.commit_created("", message)
            return result.stdout
        return f"Commit failed:\n{result.stderr}"

    def _cmd_push(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description="Push to remote",
            target=self._task_push,
        )
        return f"Task #{task.id} started: Pushing..."

    def _task_push(self, task: Task) -> str:
        self._queue.update_progress(task.id, 30, "Pushing...")
        result = subprocess.run(
            ["git", "push"],
            cwd=self._repository_root, capture_output=True, text=True, timeout=120
        )
        self._queue.update_progress(task.id, 100, "Done")
        if result.returncode == 0:
            return result.stdout
        return f"Push failed:\n{result.stderr}"

    def _cmd_pull(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description="Pull from remote",
            target=self._task_pull,
        )
        return f"Task #{task.id} started: Pulling..."

    def _task_pull(self, task: Task) -> str:
        self._queue.update_progress(task.id, 30, "Pulling...")
        result = subprocess.run(
            ["git", "pull"],
            cwd=self._repository_root, capture_output=True, text=True, timeout=60
        )
        if "conflict" in result.stdout.lower() or "conflict" in result.stderr.lower():
            self._notifications.merge_conflict()
            return f"Merge conflict detected.\n{result.stdout}\n{result.stderr}"
        self._queue.update_progress(task.id, 100, "Done")
        return result.stdout or result.stderr or "Pull complete."

    def _cmd_summary(self, args: str = "") -> str:
        self._session.refresh()
        s = self._session.state
        history_dir = self._repository_root / "docs" / "history"
        today_docs = []
        if history_dir.exists():
            today = datetime.now().strftime("%Y-%m-%d")
            today_docs = [p.name for p in sorted(history_dir.glob(f"{today}*.md"))]
        lines = [
            f"*Branch:* {s.current_branch or 'unknown'}",
            f"*Last commit:* {s.last_commit_hash} {s.last_commit_message}",
            f"*Dirty:* {'Yes' if s.is_dirty else 'No'}",
            f"*Provider:* {self._execution.active_provider}",
            f"*Active tasks:* {len(self._queue.active_tasks)}",
            f"*Docs today:* {len(today_docs)}",
            "",
            "*Next recommended:*",
            "  /status - full status",
            "  /tasks - active tasks",
            "  /help - all commands",
        ]
        return "\n".join(lines)

    def _cmd_document(self, args: str = "") -> str:
        if not args.strip():
            return "Usage: /document <topic>"
        task = self._queue.enqueue(
            description=f"Document: {args}",
            target=self._task_document,
            args,
        )
        return f"Task #{task.id} started: Documenting '{args}'"

    def _task_document(self, task: Task, topic: str) -> str:
        self._queue.update_progress(task.id, 30, "Researching...")
        result = self._execution.execute(f"document {topic}")
        if result.success:
            self._save_task_doc(task.id, topic, result)
        self._queue.update_progress(task.id, 100, "Done")
        return result.output

    def _cmd_test(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description="Run tests",
            target=self._task_test,
        )
        return f"Task #{task.id} started: Running tests..."

    def _task_test(self, task: Task) -> str:
        self._queue.update_progress(task.id, 10, "Discovering tests...")
        result = self._execution.execute("test")
        if result.success:
            self._queue.update_progress(task.id, 100, "All tests passed")
        else:
            self._queue.update_progress(task.id, 100, "Tests failed")
            self._notifications.tests_failed(result.error or "Unknown")
        return result.output or result.error or "Tests completed."

    def _cmd_backtest(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description=f"Backtest: {args or 'default'}",
            target=self._task_backtest,
            args,
            estimated_duration="5-30 min",
        )
        return f"Task #{task.id} started: Backtest running..."

    def _task_backtest(self, task: Task, params: str) -> str:
        self._queue.update_progress(task.id, 10, "Loading data...")
        result = self._execution.execute(f"backtest {params}")
        if result.success:
            self._save_task_doc(task.id, f"backtest {params}", result)
        self._queue.update_progress(task.id, 100, "Backtest complete")
        return result.output

    def _cmd_benchmark(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description="Benchmark",
            target=self._task_benchmark,
            args,
            estimated_duration="10-30 min",
        )
        return f"Task #{task.id} started: Benchmarking..."

    def _task_benchmark(self, task: Task, params: str) -> str:
        self._queue.update_progress(task.id, 10, "Setting up benchmark...")
        result = self._execution.execute(f"benchmark {params}")
        self._queue.update_progress(task.id, 100, "Benchmark complete")
        return result.output

    def _cmd_shutdown(self, args: str = "") -> str:
        return "Shutdown cancelled. Use with confirmation: CONFIRM SHUTDOWN"

    def _cmd_restart(self, args: str = "") -> str:
        task = self._queue.enqueue(
            description="Restart bot",
            target=self._task_restart,
        )
        return f"Task #{task.id}: Restarting..."

    def _task_restart(self, task: Task) -> str:
        self._queue.update_progress(task.id, 100, "Restart...")
        python = sys.executable or "python"
        subprocess.Popen(
            [python, "-m", "automation.telegram_agent"],
            cwd=self._repository_root,
        )
        return "Restarting..."

    def _cmd_cancel(self, args: str = "") -> str:
        tid = args.strip()
        if not tid:
            active = self._queue.active_tasks
            for t in active:
                self._queue.cancel(t.id)
            return f"Cancelled {len(active)} active task(s)."
        if self._queue.cancel(tid):
            return f"Task {tid} cancelled."
        return f"Task {tid} not found or already finished."

    def _cmd_tasks(self, args: str = "") -> str:
        active = self._queue.active_tasks
        if not active:
            history = self._queue.all_tasks[-10:] if self._queue.all_tasks else []
            if not history:
                return "No tasks."
            lines = ["*Recent tasks:*"]
            for t in reversed(history):
                lines.append(f"  #{t.id} {t.status.value} - {t.description[:50]}")
            return "\n".join(lines)
        lines = [f"*Active tasks ({len(active)}):*"]
        for t in active:
            lines.append(f"  #{t.id} [{t.progress}%] {t.progress_message or t.description[:50]}")
        return "\n".join(lines)

    def _cmd_providers(self, args: str = "") -> str:
        available = self._execution.available_providers
        lines = ["*Available providers:*"]
        for p in available:
            marker = " ✅ (active)" if p == self._execution.active_provider else ""
            lines.append(f"  - {p}{marker}")
        return "\n".join(lines)

    def _save_task_doc(self, task_id: str, description: str, result) -> None:
        try:
            history_dir = self._repository_root / "docs" / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now().strftime("%Y-%m-%d_%H-%M")
            filename = f"{now}_task_{task_id}.md"
            content = (
                f"# Task Report\n\n"
                f"- **ID:** {task_id}\n"
                f"- **Objective:** {description}\n"
                f"- **Date:** {datetime.now().isoformat()}\n"
                f"- **Status:** {'Success' if result.success else 'Failed'}\n\n"
                f"## Output\n\n```\n{result.output[:2000]}\n```\n"
            )
            if result.error:
                content += f"\n## Error\n\n```\n{result.error}\n```\n"
            if result.files_modified:
                content += "\n## Files Modified\n\n" + "\n".join(f"- {f}" for f in result.files_modified) + "\n"
            (history_dir / filename).write_text(content, encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to save task doc: %s", exc)
