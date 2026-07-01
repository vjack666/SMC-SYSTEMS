from __future__ import annotations

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from automation.permissions import PermissionManager
from automation.session import SessionManager
from automation.task_queue import TaskQueue
from automation.notifications import NotificationManager
from automation.execution_layer import ExecutionLayer
from automation.command_router import CommandRouter

logger = logging.getLogger("automation.telegram_agent")


DANGEROUS_COMMANDS = {"reset", "shutdown", "clean", "hard_reset"}


class TelegramAgent:
    def __init__(self, repository_root: str | Path | None = None):
        load_dotenv()
        self._repository_root = Path(repository_root or os.getenv("REPOSITORY_PATH", Path.cwd())).resolve()
        self._setup_logging()
        self._pending_confirmations: dict[int, str] = {}
        self._permissions = PermissionManager()
        self._session = SessionManager(repository_root=self._repository_root)
        self._queue = TaskQueue()
        self._notifications = NotificationManager()
        self._execution = ExecutionLayer(repository_root=self._repository_root)
        self._router = CommandRouter(
            execution_layer=self._execution,
            task_queue=self._queue,
            notifications=self._notifications,
            session=self._session,
            permissions=self._permissions,
            repository_root=self._repository_root,
        )
        self._queue.on_progress(self._on_task_progress)
        self._notifications.on_notify(self._on_notification)
        self._application: Application | None = None

    def _setup_logging(self) -> None:
        log_dir = self._repository_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "telegram.log"
        logging.basicConfig(
            level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            handlers=[
                logging.FileHandler(str(log_file), encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self._log_file = log_file

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not self._permissions.is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return
        self._session.refresh()
        s = self._session.state
        msg = (
            f"*SMC-SYSTEMS Telegram Agent*\n"
        )
        if s.current_branch:
            msg += f"Branch: {s.current_branch}\n"
        msg += f"Provider: {self._execution.active_provider}\n"
        msg += "Type /help for commands."
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not self._permissions.is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return
        command = update.message.text[1:].strip()
        cmd_parts = command.split(maxsplit=1)
        cmd_name = cmd_parts[0].lower()
        cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ""
        confirmation_key = f"CONFIRM {cmd_name.upper()}"
        if user.id in self._pending_confirmations:
            if command.upper() == confirmation_key:
                del self._pending_confirmations[user.id]
                result = self._router.route(cmd_name, cmd_args, requires_confirmation=False)
                await update.message.reply_text(result, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"Cancelled. Expected:\n{confirmation_key}"
                )
                del self._pending_confirmations[user.id]
            return
        if cmd_name in DANGEROUS_COMMANDS:
            self._pending_confirmations[user.id] = cmd_name
            result = self._router.route(cmd_name, cmd_args, requires_confirmation=True)
            await update.message.reply_text(result, parse_mode="Markdown")
            return
        result = self._router.route(cmd_name, cmd_args)
        if cmd_name == "help" and cmd_args.strip():
            result = self._router.route(cmd_args, "")
        await update.message.reply_text(result, parse_mode="Markdown")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not self._permissions.is_authorized(user.id):
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        if user.id in self._pending_confirmations:
            cmd_name = self._pending_confirmations[user.id]
            confirmation_key = f"CONFIRM {cmd_name.upper()}"
            if text.upper() == confirmation_key:
                del self._pending_confirmations[user.id]
                result = self._router.route(cmd_name, "")
                await update.message.reply_text(result, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"Cancelled. Expected:\n{confirmation_key}"
                )
                del self._pending_confirmations[user.id]
            return
        task = self._queue.enqueue(
            description=f"Message: {text[:100]}",
            target=self._handle_message_task,
            text,
        )
        await update.message.reply_text(
            f"Task #{task.id} queued.\nProcessing: '{text[:100]}'",
        )

    def _handle_message_task(self, task, text: str) -> str:
        self._queue.update_progress(task.id, 30, "Processing...")
        result = self._execution.execute(text)
        self._queue.update_progress(task.id, 100, "Done")
        return result.output

    async def _send_to_user(self, message: str, level: str = "info") -> None:
        if not self._application:
            return
        for uid in self._permissions.authorized_users:
            try:
                await self._application.bot.send_message(
                    chat_id=uid, text=message, parse_mode="Markdown"
                )
            except Exception as exc:
                logger.error("Failed to send notification to %s: %s", uid, exc)

    def _on_task_progress(self, task) -> None:
        if task.status.value in ("completed", "failed", "cancelled"):
            logger.info("Task %s: %s", task.id, task.status.value)

    def _on_notification(self, message: str, level: str) -> None:
        if self._application:
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(self._send_to_user(message, level))
            except RuntimeError:
                pass

    def run(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not set in .env")
            print("ERROR: TELEGRAM_BOT_TOKEN not set. Create a .env file.")
            print("See .env.example for reference.")
            sys.exit(1)
        auth_count = len(self._permissions.authorized_users)
        if auth_count == 0:
            logger.warning("No authorized users configured. Bot will reject all messages.")
        self._application = Application.builder().token(token).build()
        self._application.add_handler(CommandHandler("start", self._start))
        self._application.add_handler(MessageHandler(filters.COMMAND, self._handle_command))
        self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        logger.info("Starting Telegram agent...")
        print(f"Telegram agent started.")
        print(f"Repository: {self._repository_root}")
        print(f"Provider: {self._execution.active_provider}")
        print(f"Authorized users: {auth_count}")
        self._application.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    root = os.getenv("REPOSITORY_PATH")
    if root:
        agent = TelegramAgent(repository_root=root)
    else:
        agent = TelegramAgent()
    agent.run()


if __name__ == "__main__":
    main()
