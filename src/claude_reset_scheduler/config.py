from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    work_start_time: str = Field(default="09:00")
    active_days: list[int] = Field(default=[0, 1, 2, 3, 4])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_file: str = Field(default="~/.local/share/claude-reset-scheduler/scheduler.log")
    ping_message: str = Field(default="ping")
    ping_timeout: int = Field(default=30)

    @field_validator("work_start_time")
    @classmethod
    def validate_work_start_time(cls, v: str) -> str:
        if len(v) != 5 or v[2] != ":":
            raise ValueError("work_start_time must be in HH:MM format")
        hours, minutes = v.split(":")
        try:
            h = int(hours)
            m = int(minutes)
            if not (0 <= h <= 23):
                raise ValueError("hours must be between 0 and 23")
            if not (0 <= m <= 59):
                raise ValueError("minutes must be between 0 and 59")
        except ValueError:
            raise ValueError("work_start_time must be in HH:MM format")
        return v

    @field_validator("active_days")
    @classmethod
    def validate_active_days(cls, v: list[int]) -> list[int]:
        if not all(0 <= day <= 6 for day in v):
            raise ValueError("active_days must contain values between 0 and 6")
        if len(v) != len(set(v)):
            raise ValueError("active_days must not contain duplicates")
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
