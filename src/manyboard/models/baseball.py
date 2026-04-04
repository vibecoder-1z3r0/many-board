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

    # JSON string: {"away": [3, 0, null, ...], "home": [0, null, ...]}
    # null = not yet played; integer = finalized runs (0 means played, no runs)
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

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class BaseballGameCreate(SQLModel):
    home_team: str = "Home"
    away_team: str = "Away"
    num_innings: int = Field(default=6, ge=1)
    bso_style: BSOStyle = BSOStyle.DOTS


class InningScores(SQLModel):
    away: list[int | None]
    home: list[int | None]


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
    created_at: datetime
    updated_at: datetime
