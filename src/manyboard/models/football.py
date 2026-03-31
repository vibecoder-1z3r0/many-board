"""Football game state models."""

import uuid
from datetime import UTC, datetime
from enum import Enum, StrEnum

from sqlmodel import Field, SQLModel


class Half(StrEnum):
    FIRST = "first"
    HALFTIME = "halftime"
    SECOND = "second"
    FINAL = "final"


class Down(int, Enum):
    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4


class Distance(StrEnum):
    MIDFIELD = "midfield"
    GOAL = "goal"


class Possession(StrEnum):
    HOME = "home"
    AWAY = "away"


class FootballGame(SQLModel, table=True):
    __tablename__ = "football_games"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    home_team: str
    away_team: str
    home_score: int = Field(default=0, ge=0)
    away_score: int = Field(default=0, ge=0)
    half: Half = Field(default=Half.FIRST)
    down: int = Field(default=1, ge=1, le=4)
    distance: Distance = Field(default=Distance.MIDFIELD)
    possession: Possession = Field(default=Possession.HOME)
    home_timeouts: int = Field(default=3, ge=0)
    away_timeouts: int = Field(default=3, ge=0)
    play_clock: int = Field(default=40, ge=0)
    play_clock_running: bool = Field(default=False)
    no_run_zone: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FootballGameCreate(SQLModel):
    home_team: str
    away_team: str
    home_timeouts: int = Field(default=3, ge=0)
    away_timeouts: int = Field(default=3, ge=0)
    play_clock: int = Field(default=40, ge=0)
