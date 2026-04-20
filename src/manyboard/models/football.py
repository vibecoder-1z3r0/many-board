"""Football game state models."""

import json
import uuid
from datetime import UTC, datetime
from enum import Enum, StrEnum

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Naive UTC timestamp for SQLite compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)


def _default_half_scores() -> str:
    # [1H, 2H, OT] — null = not yet played, int = finalized
    return json.dumps({"away": [None, None, None], "home": [None, None, None]})


class Half(StrEnum):
    FIRST = "first"
    HALFTIME = "halftime"
    SECOND = "second"
    OT = "ot"
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


class PAT(StrEnum):
    ONE = "1pt"
    TWO = "2pt"


class DriveDirection(StrEnum):
    LEFT = "left"
    RIGHT = "right"


# HalfScores[team] = [1H, 2H, OT], each int | None
HalfScores = dict[str, list[int | None]]


class FootballGame(SQLModel, table=True):
    __tablename__ = "football_games"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    home_team: str
    away_team: str
    home_score: int = Field(default=0, ge=0)
    away_score: int = Field(default=0, ge=0)
    half: Half = Field(default=Half.FIRST)
    # Per-half scores JSON: {"away": [1H, 2H, OT], "home": [1H, 2H, OT]}
    half_scores_json: str = Field(default_factory=_default_half_scores)
    down: int = Field(default=1, ge=1, le=4)
    distance: Distance = Field(default=Distance.MIDFIELD)
    possession: Possession = Field(default=Possession.HOME)
    home_timeouts: int = Field(default=3, ge=0)
    away_timeouts: int = Field(default=3, ge=0)
    # game_clock: half countdown timer (seconds), default 20 min
    game_clock_default: int = Field(default=1200, ge=1)
    game_clock: int = Field(default=1200, ge=0)
    game_clock_running: bool = Field(default=False)
    game_clock_started_at: datetime | None = Field(default=None)
    # play_clock_default: configured duration, used for reset
    play_clock_default: int = Field(default=30, ge=1)
    # play_clock: remaining seconds as of play_clock_started_at (or now, if stopped)
    play_clock: int = Field(default=30, ge=0)
    play_clock_running: bool = Field(default=False)
    play_clock_started_at: datetime | None = Field(default=None)
    no_run_zone: bool = Field(default=False)
    # PAT: point-after-touchdown attempt marker (null = normal down, 1pt/2pt = PAT mode)
    pat: PAT | None = Field(default=None)
    # drive_direction: which way the offense is driving (independent of possession)
    drive_direction: DriveDirection | None = Field(default=None)
    # ot_enabled: OT column/button only shown when explicitly activated
    ot_enabled: bool = Field(default=False)
    status: str = Field(default="active")
    # Naive UTC datetimes — SQLite does not preserve timezone info
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class FootballGameCreate(SQLModel):
    home_team: str = "Home"
    away_team: str = "Away"
    home_timeouts: int = Field(default=3, ge=0)
    away_timeouts: int = Field(default=3, ge=0)
    game_clock: int = Field(default=1200, ge=1)
    play_clock: int = Field(default=30, ge=1)


class FootballGameRead(SQLModel):
    """Response schema — exposes computed clocks, hides started_at fields."""

    id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    half: Half
    half_scores: HalfScores  # computed from half_scores_json
    down: int
    distance: Distance
    possession: Possession
    home_timeouts: int
    away_timeouts: int
    game_clock_default: int
    game_clock: int  # current computed value
    game_clock_running: bool
    play_clock_default: int
    play_clock: int  # current computed value
    play_clock_running: bool
    no_run_zone: bool
    pat: PAT | None
    drive_direction: DriveDirection | None
    ot_enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime
