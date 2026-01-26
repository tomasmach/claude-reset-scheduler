import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config import Config
from logger import setup_logging
from scheduler import (
    calculate_ping_times,
    is_time_to_ping,
    run_once,
    should_run_today,
    was_ping_sent_today,
)


def cmd_run(args: argparse.Namespace) -> None:
    config = Config.load_default() if args.config is None else Config.from_yaml(args.config)
    logger = setup_logging(config)

    logger.info("Starting scheduler run")
    run_once(config)
    logger.info("Scheduler run complete")


def cmd_test(args: argparse.Namespace) -> None:
    config = Config.load_default() if args.config is None else Config.from_yaml(args.config)
    logger = setup_logging(config)

    logger.info("Running in test mode (dry-run)")

    if not should_run_today(config):
        logger.info(f"Not scheduled to run today (today is weekday {datetime.now().weekday()})")
        return

    ping_times = calculate_ping_times(config)
    logger.info(f"Work start time: {config.work_start_time}")
    logger.info(f"Active days: {config.active_days}")
    logger.info(f"Scheduled ping times: {', '.join(ping_times)}")
    logger.info(f"Current time: {datetime.now().strftime('%H:%M')}")

    for time_str in ping_times:
        is_time = is_time_to_ping(time_str)
        already_sent = was_ping_sent_today(time_str)
        status = "NOW" if is_time else "scheduled"
        if already_sent:
            status = "already sent"

        logger.info(f"  {time_str}: {status}")


def cmd_schedule(args: argparse.Namespace) -> None:
    config = Config.load_default() if args.config is None else Config.from_yaml(args.config)

    today = datetime.now()

    print("\nSchedule based on config:")
    print(f"  Work start time: {config.work_start_time}")
    print(f"  Active days: {', '.join(str(d) for d in config.active_days)}")
    print()

    print("Ping times:")
    ping_times = calculate_ping_times(config)
    for i, time_str in enumerate(ping_times, 1):
        print(f"  {i}. {time_str}")
    print()

    print("Upcoming days:")
    for i in range(8):
        date = today + timedelta(days=i)
        day_name = date.strftime("%A")
        day_num = date.weekday()
        is_active = day_num in config.active_days

        status = "ACTIVE" if is_active else "inactive"
        print(f"  {date.strftime('%Y-%m-%d')} ({day_name}): {status}")

        if is_active and i < 7:
            next_date = today + timedelta(days=i + 1)
            next_day_num = next_date.weekday()
            if next_day_num not in config.active_days:
                print(
                    f"    -> Next active day: {(date + timedelta(days=7 - i)).strftime('%Y-%m-%d')}"
                )


def cmd_install(args: argparse.Namespace) -> None:
    Config.load_default() if args.config is None else Config.from_yaml(args.config)

    service_content = """[Unit]
Description=Claude Reset Scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=claude-reset-scheduler run --config {config_path}
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-reset-scheduler

[Install]
WantedBy=multi-user.target
""".format(
        python_path=sys.executable,
        config_path="~/.config/claude-reset-scheduler/config.yaml"
        if args.config is None
        else args.config,
    )

    timer_content = """[Unit]
Description=Claude Reset Scheduler Timer

[Timer]
OnCalendar=*:0/15
Unit=claude-reset-scheduler.service
Persistent=true

[Install]
WantedBy=timers.target
"""

    service_path = Path.cwd() / "claude-reset-scheduler.service"
    timer_path = Path.cwd() / "claude-reset-scheduler.timer"

    service_path.write_text(service_content)
    timer_path.write_text(timer_content)

    print("\nSystemd files generated:")
    print(f"  Service: {service_path}")
    print(f"  Timer:   {timer_path}")
    print("\nTo install and enable:")
    print(f"  sudo cp {service_path} /etc/systemd/system/")
    print(f"  sudo cp {timer_path} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable claude-reset-scheduler.timer")
    print("  sudo systemctl start claude-reset-scheduler.timer")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claude Reset Scheduler - Strategic pings for token limit resets"
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: ~/.config/claude-reset-scheduler/config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Run the scheduler")
    run_parser.set_defaults(func=cmd_run)

    test_parser = subparsers.add_parser("test", help="Test schedule (dry-run)")
    test_parser.set_defaults(func=cmd_test)

    schedule_parser = subparsers.add_parser("schedule", help="Display schedule")
    schedule_parser.set_defaults(func=cmd_schedule)

    install_parser = subparsers.add_parser("install", help="Generate systemd files")
    install_parser.set_defaults(func=cmd_install)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
