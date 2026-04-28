"""
Background scheduler for MobiBot.
Checks for due scheduled tasks every 30 seconds and executes them.
"""
from __future__ import annotations
import asyncio
import logging
from database import get_due_tasks, mark_task_done

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def start_scheduler():
    """Start the background scheduler loop."""
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("📅 Scheduler started — checking for due tasks every 30s")


async def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    logger.info("Scheduler stopped")


async def _scheduler_loop():
    """Main scheduler loop — runs indefinitely."""
    while True:
        try:
            await _process_due_tasks()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
        await asyncio.sleep(30)  # Check every 30 seconds


async def _process_due_tasks():
    """Find and execute all tasks that are due."""
    tasks = get_due_tasks()
    if not tasks:
        return

    for task in tasks:
        try:
            await _execute_task(task)
            mark_task_done(task.id)
            logger.info(
                f"✅ Scheduled task #{task.id} executed: "
                f"sent to {task.target_phone}"
            )
        except Exception as e:
            logger.error(f"Failed to execute task #{task.id}: {e}", exc_info=True)


async def _execute_task(task):
    """Execute a single scheduled task — send message via WhatsApp."""
    from bot_whatsapp import whatsapp_client

    if not whatsapp_client:
        logger.warning(f"Task #{task.id}: WhatsApp client not connected, skipping")
        return

    try:
        from neonize.utils.jid import build_jid

        # Build the recipient JID from phone number
        phone = task.target_phone.lstrip("+")
        jid = build_jid(phone)

        # Send the message
        await whatsapp_client.send_message(jid, task.message)

        logger.info(f"Message sent to {phone}: {task.message[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send scheduled message to {task.target_phone}: {e}")
        raise
