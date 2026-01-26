import fcntl
import json
import logging
import os
import signal
import tempfile
import time
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import Config
from pinger import send_ping

STATE_DIR = Path("~/.local/state/claude-reset-scheduler").expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
LAST_PINGS_FILE = STATE_DIR / "last_pings.json"


def calculate_ping_times(config: Config, num_pings: int = 3) -> list[str]:
    """Calculate ping times based on start time and number of pings.

    Args:
        config: Configuration containing work_start_time
        num_pings: Number of pings per day (default 3)

    Returns:
        List of time strings in HH:MM format, spaced 5 hours apart
    """
    start_hour, start_minute = map(int, config.work_start_time.split(":"))
    start_time_minutes = start_hour * 60 + start_minute

    ping_interval_minutes = 5 * 60  # 5 hours

    times = []
    current_time_minutes = start_time_minutes
    for _ in range(num_pings):
        hour = current_time_minutes // 60
        minute = current_time_minutes % 60
        times.append(f"{hour:02d}:{minute:02d}")
        current_time_minutes += ping_interval_minutes

    return times


def should_run_today(config: Config) -> bool:
    today = datetime.now().weekday()
    return today in config.active_days


def is_time_to_ping(scheduled_time: str) -> bool:
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute

    scheduled_hour, scheduled_minute = map(int, scheduled_time.split(":"))
    scheduled_minutes = scheduled_hour * 60 + scheduled_minute

    # Calculate difference using modulo arithmetic to handle midnight crossing
    # The difference should be the minimum of the forward and backward distance
    diff = (now_minutes - scheduled_minutes) % (24 * 60)
    if diff > 12 * 60:
        diff = (24 * 60) - diff

    return diff <= 15


def _read_pings_file() -> dict[str, Any]:
    """Read pings file with file locking and error recovery."""
    logger = logging.getLogger("claude_reset_scheduler")

    if not LAST_PINGS_FILE.exists():
        return {}

    try:
        with open(LAST_PINGS_FILE, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data: dict[str, Any] = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {LAST_PINGS_FILE}: {e}")
        backup_path = LAST_PINGS_FILE.with_suffix(".json.backup")
        try:
            LAST_PINGS_FILE.rename(backup_path)
            logger.info(f"Backed up corrupted file to {backup_path}")
        except Exception as backup_error:
            logger.error(f"Failed to backup corrupted file: {backup_error}")
        return {}
    except Exception as e:
        logger.error(f"Error reading pings file: {e}")
        return {}


def _cleanup_old_records(data: dict[str, Any]) -> dict[str, Any]:
    """Remove records older than 7 days."""
    cutoff_date = datetime.now() - timedelta(days=7)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    cleaned_data = {
        date_str: times
        for date_str, times in data.items()
        if date_str >= cutoff_str
    }

    return cleaned_data


def was_ping_sent_today(time_str: str) -> bool:
    data = _read_pings_file()
    today = datetime.now().strftime("%Y-%m-%d")
    return bool(data.get(today, {}).get(time_str, False))


def mark_ping_sent_today(time_str: str) -> None:
    """Mark ping as sent using atomic write with file locking."""
    logger = logging.getLogger("claude_reset_scheduler")

    lock_file = LAST_PINGS_FILE.with_suffix(".json.lock")
    lock_fd = None

    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        data = _read_pings_file()

        today = datetime.now().strftime("%Y-%m-%d")
        if today not in data:
            data[today] = {}

        data[today][time_str] = True

        data = _cleanup_old_records(data)

        temp_fd, temp_path = tempfile.mkstemp(
            dir=STATE_DIR,
            prefix=".last_pings_",
            suffix=".json.tmp",
        )

        try:
            with os.fdopen(temp_fd, "w") as temp_f:
                json.dump(data, temp_f, indent=2)
                temp_f.flush()
                os.fsync(temp_f.fileno())

            os.chmod(temp_path, 0o600)
            os.replace(temp_path, LAST_PINGS_FILE)

        except Exception as e:
            logger.error(f"Error writing pings file: {e}")
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise

    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            try:
                os.unlink(lock_file)
            except Exception:
                pass


def should_rate_limit() -> bool:
    data = _read_pings_file()

    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)

    for date_str, times in data.items():
        for time_str, sent in times.items():
            if sent:
                try:
                    ping_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    if ping_time > one_hour_ago:
                        return True
                except ValueError:
                    continue

    return False


class SignalHandler:
    def __init__(self) -> None:
        self.shutdown_requested = False

    def __call__(self, signum: int, frame: types.FrameType | None) -> None:
        logger = logging.getLogger("claude_reset_scheduler")
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True


def run(config: Config) -> None:
    logger = logging.getLogger("claude_reset_scheduler")

    signal_handler = SignalHandler()
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if not should_run_today(config):
        logger.info("Not scheduled to run today")
        return

    ping_times = calculate_ping_times(config)

    for time_str in ping_times:
        if signal_handler.shutdown_requested:
            break

        if is_time_to_ping(time_str) and not was_ping_sent_today(time_str):
            if should_rate_limit():
                logger.info("Rate limited: ping sent within the last hour")
                continue

            logger.info(f"Time to ping at {time_str}")

            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                if signal_handler.shutdown_requested:
                    break

                logger.info(f"Sending ping (attempt {attempt + 1}/{max_retries})")

                if send_ping(config.ping_message, config.ping_timeout):
                    mark_ping_sent_today(time_str)
                    logger.info(f"Ping sent successfully at {time_str}")
                    break

                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")

                    start_time = datetime.now()
                    while (datetime.now() - start_time).total_seconds() < wait_time:
                        if signal_handler.shutdown_requested:
                            return

            else:
                logger.error(f"Failed to send ping after {max_retries} attempts")


def run_once(config: Config) -> bool:
    logger = logging.getLogger("claude_reset_scheduler")

    if not should_run_today(config):
        logger.info("Not scheduled to run today")
        return False

    ping_times = calculate_ping_times(config)

    for time_str in ping_times:
        if is_time_to_ping(time_str) and not was_ping_sent_today(time_str):
            if should_rate_limit():
                logger.info("Rate limited: ping sent within the last hour")
                continue

            logger.info(f"Time to ping at {time_str}")

            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                logger.info(f"Sending ping (attempt {attempt + 1}/{max_retries})")

                if send_ping(config.ping_message, config.ping_timeout):
                    mark_ping_sent_today(time_str)
                    logger.info(f"Ping sent successfully at {time_str}")
                    return True

                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

            else:
                logger.error(f"Failed to send ping after {max_retries} attempts")

    return False
