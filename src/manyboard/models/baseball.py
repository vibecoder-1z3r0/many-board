"""Baseball / wiffleball game state models."""

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Naive UTC timestamp for SQLite compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)


class InningHalf(StrEnum):
    TOP = "top"  # away team bats
    BOTTOM = "bottom"  # home team bats


class BSOStyle(StrEnum):
    DOTS = "dots"
    NUMBERS = "numbers"
    BOTH = "both"


def _default_scores_json() -> str:
    return json.dumps({"away": [None] * 6, "home": [None] * 6})


class BaseballGame(SQLModel, table=True):
    __tablename__ = "baseball_games"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    home_team: str = Field(default="Home")
    away_team: str = Field(default="Away")
    num_innings: int = Field(default=6, ge=1)

    # JSON string: {"away": [3, 0, null, "-", ...], "home": [0, null, ...]}
    # null = not yet played; int = finalized runs; "-" = dash (e.g. home wins early)
    scores_json: str = Field(default_factory=_default_scores_json)

    current_inning: int = Field(default=1, ge=1)
    half: InningHalf = Field(default=InningHalf.TOP)

    # Ball-strike-out count
    balls: int = Field(default=0, ge=0)
    strikes: int = Field(default=0, ge=0)
    outs: int = Field(default=0, ge=0)

    # Base runners
    base_first: bool = Field(default=False)
    base_second: bool = Field(default=False)
    base_third: bool = Field(default=False)

    bso_style: BSOStyle = Field(default=BSOStyle.DOTS)
    status: str = Field(default="active")

    # Per-team stats
    home_strikeouts: int = Field(default=0, ge=0)
    away_strikeouts: int = Field(default=0, ge=0)
    home_lob: int = Field(default=0, ge=0)
    away_lob: int = Field(default=0, ge=0)
    home_errors: int = Field(default=0, ge=0)
    away_errors: int = Field(default=0, ge=0)
    home_singles: int = Field(default=0, ge=0)
    away_singles: int = Field(default=0, ge=0)
    home_doubles: int = Field(default=0, ge=0)
    away_doubles: int = Field(default=0, ge=0)
    home_triples: int = Field(default=0, ge=0)
    away_triples: int = Field(default=0, ge=0)
    home_hrs: int = Field(default=0, ge=0)
    away_hrs: int = Field(default=0, ge=0)

    # Batting order display
    at_bat: str = Field(default="")
    next_up: str = Field(default="")
    at_bat_visible: bool = Field(default=True)
    next_up_visible: bool = Field(default=True)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class BaseballGameCreate(SQLModel):
    home_team: str = "Home"
    away_team: str = "Away"
    num_innings: int = Field(default=6, ge=1)
    bso_style: BSOStyle = BSOStyle.DOTS


# Each cell: int (runs scored), None (not played), or "-" (dash — played but no batting)
InningCell = int | str | None


class InningScores(SQLModel):
    away: list[InningCell]
    home: list[InningCell]


class BaseballGameRead(SQLModel):
    """Response schema — replaces scores_json with parsed InningScores + totals."""

    id: str
    home_team: str
    away_team: str
    num_innings: int
    scores: InningScores
    current_inning: int
    half: InningHalf
    balls: int
    strikes: int
    outs: int
    base_first: bool
    base_second: bool
    base_third: bool
    bso_style: BSOStyle
    away_total: int
    home_total: int
    status: str

    # Stats
    home_strikeouts: int
    away_strikeouts: int
    home_lob: int
    away_lob: int
    home_errors: int
    away_errors: int
    home_singles: int
    away_singles: int
    home_doubles: int
    away_doubles: int
    home_triples: int
    away_triples: int
    home_hrs: int
    away_hrs: int
    home_hits: int  # computed: singles + doubles + triples + hrs
    away_hits: int

    # Batting display
    at_bat: str
    next_up: str
    at_bat_visible: bool
    next_up_visible: bool

    created_at: datetime
    updated_at: datetime
