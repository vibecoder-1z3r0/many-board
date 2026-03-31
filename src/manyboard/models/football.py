"""Football game state models."""

import uuid
from datetime import UTC, datetime
from enum import Enum, StrEnum

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Naive UTC timestamp for SQLite compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)


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
    # play_clock_default: configured duration, used for reset
    play_clock_default: int = Field(default=40, ge=1)
    # play_clock: remaining seconds as of play_clock_started_at (or now, if stopped)
    play_clock: int = Field(default=40, ge=0)
    play_clock_running: bool = Field(default=False)
    play_clock_started_at: datetime | None = Field(default=None)
    no_run_zone: bool = Field(default=False)
    # Naive UTC datetimes — SQLite does not preserve timezone info
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class FootballGameCreate(SQLModel):
    home_team: str
    away_team: str
    home_timeouts: int = Field(default=3, ge=0)
    away_timeouts: int = Field(default=3, ge=0)
    play_clock: int = Field(default=40, ge=1)


class FootballGameRead(SQLModel):
    """Response schema — exposes computed play_clock, hides started_at."""

    id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    half: Half
    down: int
    distance: Distance
    possession: Possession
    home_timeouts: int
    away_timeouts: int
    play_clock_default: int
    play_clock: int  # current computed value
    play_clock_running: bool
    no_run_zone: bool
    created_at: datetime
    updated_at: datetime
