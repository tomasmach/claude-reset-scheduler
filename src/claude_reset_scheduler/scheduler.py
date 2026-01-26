import json
import logging
import signal
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config
from .pinger import send_ping

STATE_DIR = Path("~/.local/state/claude-reset-scheduler").expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
LAST_PINGS_FILE = STATE_DIR / "last_pings.json"


def calculate_ping_times(config: Config) -> list[str]:
    start_hour, start_minute = map(int, config.work_start_time.split(":"))
    start_time_minutes = start_hour * 60 + start_minute
    end_time_minutes = 17 * 60

    workday_minutes = end_time_minutes - start_time_minutes
    ping_interval_minutes = workday_minutes // 3

    times = []
    for i in range(3):
        minutes = start_time_minutes + ping_interval_minutes * i
        hour = minutes // 60
        minute = minutes % 60
        times.append(f"{hour:02d}:{minute:02d}")

    return times


def should_run_today(config: Config) -> bool:
    today = datetime.now().weekday()
    return today in config.active_days


def is_time_to_ping(scheduled_time: str) -> bool:
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute

    scheduled_hour, scheduled_minute = map(int, scheduled_time.split(":"))
    scheduled_minutes = scheduled_hour * 60 + scheduled_minute

    diff = abs(now_minutes - scheduled_minutes)
    return diff <= 15


def was_ping_sent_today(time_str: str) -> bool:
    if not LAST_PINGS_FILE.exists():
        return False

    with open(LAST_PINGS_FILE, "r") as f:
        data = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    return data.get(today, {}).get(time_str, False)


def mark_ping_sent_today(time_str: str) -> None:
    data = {}

    if LAST_PINGS_FILE.exists():
        with open(LAST_PINGS_FILE, "r") as f:
            data = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in data:
        data[today] = {}

    data[today][time_str] = True

    with open(LAST_PINGS_FILE, "w") as f:
        json.dump(data, f)


def should_rate_limit() -> bool:
    if not LAST_PINGS_FILE.exists():
        return False

    with open(LAST_PINGS_FILE, "r") as f:
        data = json.load(f)

    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)

    for date_str, times in data.items():
        for time_str, sent in times.items():
            if sent:
                ping_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                if ping_time > one_hour_ago:
                    return True

    return False


class SignalHandler:
    def __init__(self):
        self.shutdown_requested = False

    def __call__(self, signum: int, frame) -> None:
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
                    import time

                    time.sleep(wait_time)

            else:
                logger.error(f"Failed to send ping after {max_retries} attempts")

    return False
