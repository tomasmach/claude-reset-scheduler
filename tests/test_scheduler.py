import json
import pytest
import subprocess
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from claude_reset_scheduler.config import Config
from claude_reset_scheduler.scheduler import (
    calculate_ping_times,
    should_run_today,
    is_time_to_ping,
    was_ping_sent_today,
    mark_ping_sent_today,
    should_rate_limit,
    run_once,
)
from claude_reset_scheduler.pinger import send_ping


@pytest.fixture
def valid_config_dict():
    return {
        "work_start_time": "09:00",
        "work_end_time": "17:00",
        "active_days": [0, 1, 2, 3, 4],
        "log_level": "INFO",
        "log_file": "~/.local/share/claude-reset-scheduler/test-scheduler.log",
        "ping_message": "ping",
        "ping_timeout": 30,
    }


@pytest.fixture
def temp_config_file(tmp_path, valid_config_dict):
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(valid_config_dict, f)
    return str(config_path)


@pytest.fixture
def temp_state_dir(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


class TestConfig:
    def test_create_config_default(self):
        config = Config()
        assert config.work_start_time == "09:00"
        assert config.active_days == [0, 1, 2, 3, 4]
        assert config.log_level == "INFO"
        assert config.ping_message == "ping"
        assert config.ping_timeout == 30

    def test_create_config_from_dict(self, valid_config_dict):
        config = Config(**valid_config_dict)
        assert config.work_start_time == "09:00"
        assert config.active_days == [0, 1, 2, 3, 4]
        assert config.ping_message == "ping"

    def test_create_config_from_yaml(self, temp_config_file):
        config = Config.from_yaml(temp_config_file)
        assert config.work_start_time == "09:00"
        assert config.active_days == [0, 1, 2, 3, 4]
        assert config.ping_timeout == 30

    def test_invalid_time_format(self, tmp_path):
        config_dict = {
            "work_start_time": "invalid",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "HH:MM format" in str(exc_info.value)

    def test_invalid_hour_value(self, tmp_path):
        config_dict = {
            "work_start_time": "25:00",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "HH:MM format" in str(exc_info.value)

    def test_invalid_minute_value(self, tmp_path):
        config_dict = {
            "work_start_time": "09:60",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "HH:MM format" in str(exc_info.value)

    def test_invalid_day_value(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0, 7],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "between 0 and 6" in str(exc_info.value)

    def test_duplicate_days(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0, 1, 1],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "duplicates" in str(exc_info.value).lower()

    def test_all_days(self):
        config = Config(active_days=[0, 1, 2, 3, 4, 5, 6])
        assert len(config.active_days) == 7

    def test_weekend_only(self):
        config = Config(active_days=[5, 6])
        assert config.active_days == [5, 6]

    def test_work_end_time_validation(self):
        config = Config(work_start_time="09:00", work_end_time="18:00")
        assert config.work_end_time == "18:00"

    def test_work_end_time_before_start_time(self, tmp_path):
        config_dict = {
            "work_start_time": "17:00",
            "work_end_time": "09:00",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "work_start_time must be before work_end_time" in str(exc_info.value)

    def test_work_end_time_equal_start_time(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "work_end_time": "09:00",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "work_start_time must be before work_end_time" in str(exc_info.value)


class TestCalculatePingTimes:
    def test_standard_9_to_5(self):
        config = Config(work_start_time="09:00", work_end_time="17:00")
        times = calculate_ping_times(config)
        assert len(times) == 3
        assert all(len(t) == 5 and t[2] == ":" for t in times)

    def test_late_start(self):
        config = Config(work_start_time="12:00", work_end_time="17:00")
        times = calculate_ping_times(config)
        assert len(times) == 3
        hour = int(times[0].split(":")[0])
        assert hour >= 12

    def test_early_start(self):
        config = Config(work_start_time="06:00", work_end_time="17:00")
        times = calculate_ping_times(config)
        assert len(times) == 3
        hour = int(times[0].split(":")[0])
        assert hour >= 6

    def test_custom_work_end_time(self):
        config = Config(work_start_time="09:00", work_end_time="18:00")
        times = calculate_ping_times(config)
        assert len(times) == 3
        start_minutes = 9 * 60
        end_minutes = 18 * 60
        interval = (end_minutes - start_minutes) // 3
        assert times[0] == "09:00"
        assert times[1] == f"{(start_minutes + interval) // 60:02d}:{(start_minutes + interval) % 60:02d}"
        assert times[2] == f"{(start_minutes + 2 * interval) // 60:02d}:{(start_minutes + 2 * interval) % 60:02d}"

    def test_short_workday(self):
        config = Config(work_start_time="09:00", work_end_time="12:00")
        times = calculate_ping_times(config)
        assert len(times) == 3
        assert times[0] == "09:00"
        assert times[1] == "10:00"
        assert times[2] == "11:00"


class TestShouldRunToday:
    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_monday(self, mock_datetime, temp_config_file):
        config = Config.from_yaml(temp_config_file)
        mock_datetime.now.return_value.weekday.return_value = 0
        assert should_run_today(config) is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_saturday(self, mock_datetime, temp_config_file):
        config = Config.from_yaml(temp_config_file)
        mock_datetime.now.return_value.weekday.return_value = 5
        assert should_run_today(config) is False

    def test_weekend_config(self, tmp_path):
        home_test_dir = Path.home() / ".test-claude-scheduler"
        home_test_dir.mkdir(exist_ok=True)

        try:
            log_file_path = home_test_dir / "test.log"
            config_dict = {
                "work_start_time": "10:00",
                "active_days": [5, 6],
                "log_level": "INFO",
                "log_file": str(log_file_path),
            }
            config_path = tmp_path / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config_dict, f)

            config = Config.from_yaml(str(config_path))

            with patch("claude_reset_scheduler.scheduler.datetime") as mock_datetime:
                mock_datetime.now.return_value.weekday.return_value = 5
                assert should_run_today(config) is True

                mock_datetime.now.return_value.weekday.return_value = 0
                assert should_run_today(config) is False
        finally:
            import shutil
            if home_test_dir.exists():
                shutil.rmtree(home_test_dir)


class TestIsTimeToPing:
    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_exact_time(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 30
        assert is_time_to_ping("09:30") is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_within_window(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 35
        assert is_time_to_ping("09:30") is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_outside_window(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 46
        assert is_time_to_ping("09:30") is False

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_midnight_crossing(self, mock_datetime):
        mock_datetime.now.return_value.hour = 0
        mock_datetime.now.return_value.minute = 5
        assert is_time_to_ping("23:55") is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_edge_case_exactly_15_minutes(self, mock_datetime):
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 45
        assert is_time_to_ping("09:30") is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_midnight_crossing_reverse(self, mock_datetime):
        mock_datetime.now.return_value.hour = 23
        mock_datetime.now.return_value.minute = 55
        assert is_time_to_ping("00:05") is True

    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_midnight_crossing_outside_window(self, mock_datetime):
        mock_datetime.now.return_value.hour = 0
        mock_datetime.now.return_value.minute = 21
        assert is_time_to_ping("23:55") is False


class TestPingTracking:
    @patch("claude_reset_scheduler.scheduler.LAST_PINGS_FILE")
    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_was_ping_sent_today_no_file(self, mock_datetime, mock_file):
        mock_file.exists.return_value = False
        assert was_ping_sent_today("09:00") is False

    @patch("claude_reset_scheduler.scheduler.LAST_PINGS_FILE")
    @patch("claude_reset_scheduler.scheduler.datetime")
    def test_was_ping_sent_today_with_file(self, mock_datetime, mock_file, tmp_path):
        mock_file.exists.return_value = True
        today = "2026-01-27"
        mock_datetime.now.return_value.strftime.return_value = today

        test_file = tmp_path / "last_pings.json"
        data = {today: {"09:00": True}}
        test_file.write_text(json.dumps(data))

        mock_file.__str__ = lambda self: str(test_file)
        mock_file.read = lambda: test_file.read_text()

        with open(test_file, "r") as f:
            original_open = open

            def custom_open(path, *args, **kwargs):
                if str(path) == str(test_file):
                    return original_open(str(path), *args, **kwargs)
                return mock_file

            with patch("builtins.open", side_effect=custom_open):
                assert was_ping_sent_today("09:00") is True

    def test_mark_ping_sent_today_new_entry(self, tmp_path):
        from claude_reset_scheduler.scheduler import LAST_PINGS_FILE, mark_ping_sent_today, _cleanup_old_records
        import shutil

        test_file = tmp_path / "last_pings.json"
        original_file = LAST_PINGS_FILE

        def no_op_cleanup(data):
            return data

        try:
            shutil.rmtree(LAST_PINGS_FILE.parent, ignore_errors=True)
            test_file.parent.mkdir(parents=True, exist_ok=True)

            with patch.object(
                sys.modules["claude_reset_scheduler.scheduler"], "LAST_PINGS_FILE", test_file
            ):
                with patch.object(
                    sys.modules["claude_reset_scheduler.scheduler"], "STATE_DIR", tmp_path
                ):
                    with patch("claude_reset_scheduler.scheduler.datetime") as mock_datetime:
                        mock_datetime.now.return_value.strftime.return_value = "2026-01-27"
                        with patch("claude_reset_scheduler.scheduler._cleanup_old_records", side_effect=no_op_cleanup):
                            mark_ping_sent_today("09:00")

            with open(test_file, "r") as f:
                data = json.load(f)
            assert data["2026-01-27"]["09:00"] is True
        finally:
            if original_file != test_file and test_file.exists():
                test_file.unlink()


class TestRateLimiting:
    def test_should_rate_limit_recent_ping(self, tmp_path):
        from claude_reset_scheduler.scheduler import LAST_PINGS_FILE, should_rate_limit

        now = datetime(2026, 1, 27, 10, 30, 0)

        test_file = tmp_path / "last_pings.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "2026-01-27": {
                "10:00": True,
            }
        }
        test_file.write_text(json.dumps(data))

        original_datetime = datetime

        class MockDatetime:
            @staticmethod
            def now():
                return now

            @staticmethod
            def strptime(date_string, format_string):
                return original_datetime.strptime(date_string, format_string)

        with patch.object(
            sys.modules["claude_reset_scheduler.scheduler"], "LAST_PINGS_FILE", test_file
        ):
            with patch("claude_reset_scheduler.scheduler.datetime", MockDatetime):
                assert should_rate_limit() is True

    def test_should_rate_limit_old_ping(self, tmp_path):
        from claude_reset_scheduler.scheduler import LAST_PINGS_FILE, should_rate_limit

        now = datetime(2026, 1, 27, 10, 30, 0)

        test_file = tmp_path / "last_pings.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "2026-01-27": {
                "09:00": True,
            }
        }
        test_file.write_text(json.dumps(data))

        original_datetime = datetime

        class MockDatetime:
            @staticmethod
            def now():
                return now

            @staticmethod
            def strptime(date_string, format_string):
                return original_datetime.strptime(date_string, format_string)

        with patch.object(
            sys.modules["claude_reset_scheduler.scheduler"], "LAST_PINGS_FILE", test_file
        ):
            with patch("claude_reset_scheduler.scheduler.datetime", MockDatetime):
                assert should_rate_limit() is False


class TestPinger:
    @patch("claude_reset_scheduler.pinger.subprocess.run")
    def test_send_ping_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"
        mock_run.return_value = mock_result

        result = send_ping("ping", 30)
        assert result is True

    @patch("claude_reset_scheduler.pinger.subprocess.run")
    def test_send_ping_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"
        mock_run.return_value = mock_result

        result = send_ping("ping", 30)
        assert result is False

    @patch("claude_reset_scheduler.pinger.subprocess.run")
    def test_send_ping_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("claude-code", 30)

        result = send_ping("ping", 30)
        assert result is False

    @patch("claude_reset_scheduler.pinger.subprocess.run")
    def test_send_ping_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = send_ping("ping", 30)
        assert result is False


class TestNegativeWorkday:
    def test_work_start_after_end_rejected(self, tmp_path):
        config_dict = {
            "work_start_time": "18:00",
            "work_end_time": "17:00",
            "active_days": [0],
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "work_start_time must be before work_end_time" in str(exc_info.value)


class TestFileLocking:
    def test_concurrent_writes_no_data_corruption(self, tmp_path):
        import threading
        import claude_reset_scheduler.scheduler as scheduler_module

        test_file = tmp_path / "last_pings.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)

        original_state_dir = scheduler_module.STATE_DIR
        original_last_pings_file = scheduler_module.LAST_PINGS_FILE

        try:
            scheduler_module.STATE_DIR = tmp_path
            scheduler_module.LAST_PINGS_FILE = test_file

            def no_op_cleanup(data):
                return data

            with patch("claude_reset_scheduler.scheduler.datetime") as mock_datetime:
                mock_datetime.now.return_value.strftime.return_value = "2026-01-27"
                with patch("claude_reset_scheduler.scheduler._cleanup_old_records", side_effect=no_op_cleanup):
                    threads = []
                    for i in range(10):
                        t = threading.Thread(
                            target=scheduler_module.mark_ping_sent_today, args=(f"{9 + i:02d}:00",)
                        )
                        threads.append(t)
                        t.start()

                    for t in threads:
                        t.join()

            with open(test_file, "r") as f:
                data = json.load(f)

            assert "2026-01-27" in data
            assert len(data["2026-01-27"]) == 10
            for i in range(10):
                assert data["2026-01-27"][f"{9 + i:02d}:00"] is True
        finally:
            scheduler_module.STATE_DIR = original_state_dir
            scheduler_module.LAST_PINGS_FILE = original_last_pings_file


class TestCleanup:
    def test_old_entries_removed_after_7_days(self, tmp_path):
        from claude_reset_scheduler.scheduler import LAST_PINGS_FILE, _cleanup_old_records

        test_file = tmp_path / "last_pings.json"
        test_file.parent.mkdir(parents=True, exist_ok=True)

        now = datetime(2026, 1, 27, 10, 30, 0)
        old_date = (now - timedelta(days=8)).strftime("%Y-%m-%d")
        recent_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        data = {
            old_date: {"09:00": True},
            recent_date: {"10:00": True},
            today: {"11:00": True},
        }

        with patch("claude_reset_scheduler.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            cleaned_data = _cleanup_old_records(data)

            assert old_date not in cleaned_data
            assert recent_date in cleaned_data
            assert today in cleaned_data


class TestPathValidation:
    def test_path_outside_home_rejected(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "log_file": "/etc/passwd",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "must be within home directory" in str(exc_info.value)

    def test_path_traversal_blocked(self, tmp_path):
        home_test_dir = Path.home() / ".test-claude-scheduler"
        home_test_dir.mkdir(exist_ok=True)

        try:
            target_file = home_test_dir / "target.log"
            target_file.touch()

            config_dict = {
                "work_start_time": "09:00",
                "active_days": [0],
                "log_file": "/etc/passwd",
            }
            config_path = tmp_path / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config_dict, f)

            with pytest.raises(ValueError) as exc_info:
                Config.from_yaml(str(config_path))
            assert "must be within home directory" in str(exc_info.value)
        finally:
            import shutil
            if home_test_dir.exists():
                shutil.rmtree(home_test_dir)

    def test_symlink_rejected(self, tmp_path):
        home_test_dir = Path.home() / ".test-claude-scheduler"
        home_test_dir.mkdir(exist_ok=True)

        try:
            real_file = home_test_dir / "real_log.log"
            real_file.touch()
            symlink = home_test_dir / "symlink.log"
            if symlink.exists():
                symlink.unlink()
            symlink.symlink_to(real_file)

            config_dict = {
                "work_start_time": "09:00",
                "active_days": [0],
                "log_file": str(symlink),
            }
            config_path = tmp_path / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config_dict, f)

            with pytest.raises(ValueError) as exc_info:
                Config.from_yaml(str(config_path))
            assert "Symlinks are not allowed" in str(exc_info.value)
        finally:
            import shutil
            if home_test_dir.exists():
                shutil.rmtree(home_test_dir)


class TestMessageValidation:
    def test_empty_message_rejected(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_message": "",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "alphanumeric" in str(exc_info.value)

    def test_long_message_rejected(self, tmp_path):
        long_message = "a" * 101
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_message": long_message,
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "100 characters" in str(exc_info.value)

    def test_special_chars_rejected(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_message": "ping && rm -rf /",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "alphanumeric" in str(exc_info.value)

    def test_valid_message_accepted(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_message": "Hello Claude! How are you?",
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        config = Config.from_yaml(str(config_path))
        assert config.ping_message == "Hello Claude! How are you?"


class TestTimeoutValidation:
    def test_timeout_too_low(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_timeout": 0,
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "between 1 and 300" in str(exc_info.value)

    def test_timeout_too_high(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_timeout": 301,
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        with pytest.raises(ValueError) as exc_info:
            Config.from_yaml(str(config_path))
        assert "between 1 and 300" in str(exc_info.value)

    def test_valid_timeout_min(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_timeout": 1,
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        config = Config.from_yaml(str(config_path))
        assert config.ping_timeout == 1

    def test_valid_timeout_max(self, tmp_path):
        config_dict = {
            "work_start_time": "09:00",
            "active_days": [0],
            "ping_timeout": 300,
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)

        config = Config.from_yaml(str(config_path))
        assert config.ping_timeout == 300


class TestRunOnce:
    @patch("claude_reset_scheduler.scheduler.should_run_today")
    @patch("claude_reset_scheduler.scheduler.calculate_ping_times")
    def test_run_once_inactive_day(self, mock_calc_times, mock_should_run, temp_config_file):
        config = Config.from_yaml(temp_config_file)
        mock_should_run.return_value = False

        result = run_once(config)
        assert result is False
        mock_calc_times.assert_not_called()

    @patch("claude_reset_scheduler.scheduler.mark_ping_sent_today")
    @patch("claude_reset_scheduler.scheduler.should_run_today")
    @patch("claude_reset_scheduler.scheduler.calculate_ping_times")
    @patch("claude_reset_scheduler.scheduler.is_time_to_ping")
    @patch("claude_reset_scheduler.scheduler.was_ping_sent_today")
    @patch("claude_reset_scheduler.scheduler.should_rate_limit")
    @patch("claude_reset_scheduler.scheduler.send_ping")
    def test_run_once_success(
        self,
        mock_send_ping,
        mock_rate_limit,
        mock_was_sent,
        mock_is_time,
        mock_calc_times,
        mock_should_run,
        mock_mark_sent,
        temp_config_file,
    ):
        config = Config.from_yaml(temp_config_file)
        mock_should_run.return_value = True
        mock_calc_times.return_value = ["09:00", "13:00", "16:00"]
        mock_is_time.return_value = True
        mock_was_sent.return_value = False
        mock_rate_limit.return_value = False
        mock_send_ping.return_value = True

        result = run_once(config)
        assert result is True
        mock_send_ping.assert_called_once()
        mock_mark_sent.assert_called_once()

    @patch("claude_reset_scheduler.scheduler.should_run_today")
    @patch("claude_reset_scheduler.scheduler.calculate_ping_times")
    @patch("claude_reset_scheduler.scheduler.is_time_to_ping")
    @patch("claude_reset_scheduler.scheduler.was_ping_sent_today")
    @patch("claude_reset_scheduler.scheduler.should_rate_limit")
    def test_run_once_rate_limited(
        self,
        mock_rate_limit,
        mock_was_sent,
        mock_is_time,
        mock_calc_times,
        mock_should_run,
        temp_config_file,
    ):
        config = Config.from_yaml(temp_config_file)
        mock_should_run.return_value = True
        mock_calc_times.return_value = ["09:00", "13:00", "16:00"]
        mock_is_time.return_value = True
        mock_was_sent.return_value = False
        mock_rate_limit.return_value = True

        result = run_once(config)
        assert result is False

    @patch("claude_reset_scheduler.scheduler.should_run_today")
    @patch("claude_reset_scheduler.scheduler.calculate_ping_times")
    @patch("claude_reset_scheduler.scheduler.is_time_to_ping")
    def test_run_once_not_time_yet(
        self,
        mock_is_time,
        mock_calc_times,
        mock_should_run,
        temp_config_file,
    ):
        config = Config.from_yaml(temp_config_file)
        mock_should_run.return_value = True
        mock_calc_times.return_value = ["09:00", "13:00", "16:00"]
        mock_is_time.return_value = False

        result = run_once(config)
        assert result is False
