import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationInfo, field_validator


def validate_safe_path(path: Path) -> None:
    """Validate that the path is safe and within the user's home directory.

    Args:
        path: Path to validate

    Raises:
        ValueError: If path is not safe or outside home directory
    """
    if path.is_symlink():
        raise ValueError(f"Symlinks are not allowed: {path}")

    resolved_path = path.resolve()
    home_dir = Path.home().resolve()

    try:
        resolved_path.relative_to(home_dir)
    except ValueError:
        raise ValueError(f"Path must be within home directory: {path}")


class Config(BaseModel):
    work_start_time: str = Field(default="09:00")
    work_end_time: str = Field(default="17:00")
    active_days: list[int] = Field(default=[0, 1, 2, 3, 4])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_file: str = Field(default="~/.local/share/claude-reset-scheduler/scheduler.log")
    ping_message: str = Field(default="ping")
    ping_timeout: int = Field(default=30)

    @field_validator("work_start_time", "work_end_time")
    @classmethod
    def validate_work_time(cls, v: str) -> str:
        if len(v) != 5 or v[2] != ":":
            raise ValueError("work time must be in HH:MM format")
        hours, minutes = v.split(":")
        try:
            h = int(hours)
            m = int(minutes)
            if not (0 <= h <= 23):
                raise ValueError("hours must be between 0 and 23")
            if not (0 <= m <= 59):
                raise ValueError("minutes must be between 0 and 59")
        except ValueError:
            raise ValueError("work time must be in HH:MM format")
        return v

    @field_validator("work_end_time")
    @classmethod
    def validate_work_times_order(cls, v: str, info: ValidationInfo) -> str:
        if "work_start_time" in info.data:
            start_hour, start_minute = map(int, info.data["work_start_time"].split(":"))
            end_hour, end_minute = map(int, v.split(":"))
            start_minutes = start_hour * 60 + start_minute
            end_minutes = end_hour * 60 + end_minute
            if start_minutes >= end_minutes:
                raise ValueError("work_start_time must be before work_end_time")
        return v

    @field_validator("active_days")
    @classmethod
    def validate_active_days(cls, v: list[int]) -> list[int]:
        if not all(0 <= day <= 6 for day in v):
            raise ValueError("active_days must contain values between 0 and 6")
        if len(v) != len(set(v)):
            raise ValueError("active_days must not contain duplicates")
        return v

    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v: str) -> str:
        """Validate log file path for security.

        Ensures the path:
        - Is within the user's home directory
        - Is not a symlink
        - Does not contain path traversal attempts
        """
        log_path = Path(v).expanduser()
        validate_safe_path(log_path)
        return v

    @field_validator("ping_message")
    @classmethod
    def validate_ping_message(cls, v: str) -> str:
        """Validate ping message to prevent command injection.

        Only allows alphanumeric characters, spaces, and basic punctuation.
        Maximum length of 100 characters.
        """
        if len(v) > 100:
            raise ValueError("ping_message must be at most 100 characters")

        if not re.match(r'^[a-zA-Z0-9\s.,!?;:\-_()]+$', v):
            raise ValueError(
                "ping_message can only contain alphanumeric characters, spaces, "
                "and basic punctuation (.,!?;:-_())"
            )

        return v

    @field_validator("ping_timeout")
    @classmethod
    def validate_ping_timeout(cls, v: int) -> int:
        """Validate ping timeout is within reasonable bounds."""
        if not 1 <= v <= 300:
            raise ValueError("ping_timeout must be between 1 and 300 seconds")
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        config_path = Path(path).expanduser()
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def load_default(cls) -> "Config":
        default_path = Path("~/.config/claude-reset-scheduler/config.yaml").expanduser()
        if default_path.exists():
            return cls.from_yaml(default_path)
        return cls()
