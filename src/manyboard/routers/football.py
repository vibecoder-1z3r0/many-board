"""Football game API router."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from manyboard.database import get_session
from manyboard.models.football import (
    PAT,
    Distance,
    Down,
    FootballGame,
    FootballGameCreate,
    FootballGameRead,
    Half,
    HalfScores,
    Possession,
)

router = APIRouter(prefix="/api/football/games", tags=["football"])

SessionDep = Annotated[Session, Depends(get_session)]


# --- Request schemas ---


class ScoreUpdate(BaseModel):
    team: str
    delta: int


class DownUpdate(BaseModel):
    down: Annotated[int, Field(ge=1, le=4)]
    distance: Distance


class PossessionUpdate(BaseModel):
    possession: Possession


class TeamUpdate(BaseModel):
    team: str


class NoRunZoneUpdate(BaseModel):
    enabled: bool


class PATUpdate(BaseModel):
    pat: PAT | None  # None clears PAT mode


class OTEnabledUpdate(BaseModel):
    enabled: bool


class HalfUpdate(BaseModel):
    half: Half


class HalfScoreUpdate(BaseModel):
    half: Half  # first | second | ot
    team: str   # "home" or "away"
    points: int


class TeamNamesUpdate(BaseModel):
    home_team: str | None = None
    away_team: str | None = None


class ClockSet(BaseModel):
    """Set a clock to a specific value (stops it)."""

    seconds: Annotated[int, Field(ge=0)]


# --- Helpers ---


def _get_game(game_id: str, session: Session) -> FootballGame:
    game = session.get(FootballGame, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _now() -> datetime:
    """Naive UTC timestamp — SQLite does not preserve timezone info."""
    return datetime.now(UTC).replace(tzinfo=None)


def _save(game: FootballGame, session: Session) -> FootballGame:
    game.updated_at = _now()
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


_HALF_IDX: dict[str, int] = {"first": 0, "second": 1, "ot": 2}


def _get_half_scores(game: FootballGame) -> HalfScores:
    return json.loads(game.half_scores_json)  # type: ignore[no-any-return]


def _set_half_scores(game: FootballGame, scores: HalfScores) -> None:
    game.half_scores_json = json.dumps(scores)


def _snapshot_half(game: FootballGame, half_key: str) -> None:
    """Record points scored IN the given half based on running totals."""
    idx = _HALF_IDX.get(half_key)
    if idx is None:
        return
    scores = _get_half_scores(game)
    # Points in this half = total minus sum of previous halves
    prev_away = sum(v for v in scores["away"][:idx] if v is not None)
    prev_home = sum(v for v in scores["home"][:idx] if v is not None)
    scores["away"][idx] = game.away_score - prev_away
    scores["home"][idx] = game.home_score - prev_home
    _set_half_scores(game, scores)


def _computed_game_clock(game: FootballGame) -> int:
    """Current remaining game clock seconds, accounting for elapsed time if running."""
    if not game.game_clock_running or game.game_clock_started_at is None:
        return game.game_clock
    elapsed = (_now() - game.game_clock_started_at).total_seconds()
    return max(0, game.game_clock - int(elapsed))


def _computed_play_clock(game: FootballGame) -> int:
    """Current remaining play clock seconds, accounting for elapsed time if running."""
    if not game.play_clock_running or game.play_clock_started_at is None:
        return game.play_clock
    elapsed = (_now() - game.play_clock_started_at).total_seconds()
    return max(0, game.play_clock - int(elapsed))


def _to_read(game: FootballGame) -> FootballGameRead:
    data = game.model_dump()
    data["game_clock"] = _computed_game_clock(game)
    data["play_clock"] = _computed_play_clock(game)
    data["half_scores"] = _get_half_scores(game)
    return FootballGameRead.model_validate(data)


# --- Endpoints ---


@router.post("", status_code=201)
def create_game(data: FootballGameCreate, session: SessionDep) -> FootballGameRead:
    game = FootballGame(
        home_team=data.home_team,
        away_team=data.away_team,
        home_timeouts=data.home_timeouts,
        away_timeouts=data.away_timeouts,
        game_clock_default=data.game_clock,
        game_clock=data.game_clock,
        play_clock_default=data.play_clock,
        play_clock=data.play_clock,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return _to_read(game)


@router.get("")
def list_games(session: SessionDep) -> list[FootballGameRead]:
    return [_to_read(g) for g in session.exec(select(FootballGame)).all()]


@router.get("/{game_id}")
def get_game(game_id: str, session: SessionDep) -> FootballGameRead:
    game = _get_game(game_id, session)
    read = _to_read(game)
    dirty = False
    # Auto-stop game clock in DB if it expired while running
    if game.game_clock_running and read.game_clock == 0:
        game.game_clock = 0
        game.game_clock_running = False
        game.game_clock_started_at = None
        dirty = True
    # Auto-stop play clock in DB if it expired while running
    if game.play_clock_running and read.play_clock == 0:
        game.play_clock = 0
        game.play_clock_running = False
        game.play_clock_started_at = None
        dirty = True
    if dirty:
        _save(game, session)
    return read


@router.delete("/{game_id}", status_code=204)
def delete_game(game_id: str, session: SessionDep) -> None:
    game = _get_game(game_id, session)
    session.delete(game)
    session.commit()


@router.patch("/{game_id}/teams")
def update_teams(
    game_id: str, update: TeamNamesUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    if update.home_team is not None:
        game.home_team = update.home_team
    if update.away_team is not None:
        game.away_team = update.away_team
    return _to_read(_save(game, session))


@router.patch("/{game_id}/score")
def update_score(
    game_id: str, update: ScoreUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    if update.team == "home":
        new_score = game.home_score + update.delta
        if new_score < 0:
            raise HTTPException(status_code=400, detail="Score cannot go below zero")
        game.home_score = new_score
    elif update.team == "away":
        new_score = game.away_score + update.delta
        if new_score < 0:
            raise HTTPException(status_code=400, detail="Score cannot go below zero")
        game.away_score = new_score
    else:
        raise HTTPException(status_code=422, detail="team must be 'home' or 'away'")
    return _to_read(_save(game, session))


@router.patch("/{game_id}/down")
def update_down(
    game_id: str, update: DownUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    game.down = update.down
    game.distance = update.distance
    return _to_read(_save(game, session))


@router.patch("/{game_id}/possession")
def update_possession(
    game_id: str, update: PossessionUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    game.possession = update.possession
    return _to_read(_save(game, session))


@router.patch("/{game_id}/timeout")
def use_timeout(
    game_id: str, update: TeamUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    if update.team == "home":
        if game.home_timeouts <= 0:
            raise HTTPException(
                status_code=400, detail="No timeouts remaining for home team"
            )
        game.home_timeouts -= 1
    elif update.team == "away":
        if game.away_timeouts <= 0:
            raise HTTPException(
                status_code=400, detail="No timeouts remaining for away team"
            )
        game.away_timeouts -= 1
    else:
        raise HTTPException(status_code=422, detail="team must be 'home' or 'away'")
    return _to_read(_save(game, session))


@router.patch("/{game_id}/timeout/restore")
def restore_timeout(
    game_id: str, update: TeamUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    if update.team == "home":
        game.home_timeouts += 1
    elif update.team == "away":
        game.away_timeouts += 1
    else:
        raise HTTPException(status_code=422, detail="team must be 'home' or 'away'")
    return _to_read(_save(game, session))


@router.patch("/{game_id}/no-run-zone")
def update_no_run_zone(
    game_id: str, update: NoRunZoneUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    game.no_run_zone = update.enabled
    return _to_read(_save(game, session))


@router.patch("/{game_id}/pat")
def update_pat(
    game_id: str, update: PATUpdate, session: SessionDep
) -> FootballGameRead:
    """Set PAT mode (1pt/2pt attempt) or clear it (null)."""
    game = _get_game(game_id, session)
    game.pat = update.pat
    return _to_read(_save(game, session))


@router.patch("/{game_id}/ot")
def update_ot_enabled(
    game_id: str, update: OTEnabledUpdate, session: SessionDep
) -> FootballGameRead:
    """Enable or disable the OT period for this game."""
    game = _get_game(game_id, session)
    game.ot_enabled = update.enabled
    return _to_read(_save(game, session))


@router.patch("/{game_id}/half")
def update_half(
    game_id: str, update: HalfUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    prev = game.half
    game.half = update.half
    # Snapshot points scored when a scoring half ends
    if prev == Half.FIRST and update.half == Half.HALFTIME:
        _snapshot_half(game, "first")
    elif prev == Half.SECOND and update.half in (Half.FINAL, Half.OT):
        _snapshot_half(game, "second")
    elif prev == Half.OT and update.half == Half.FINAL:
        _snapshot_half(game, "ot")
    return _to_read(_save(game, session))


@router.patch("/{game_id}/half-score")
def set_half_score(
    game_id: str, update: HalfScoreUpdate, session: SessionDep
) -> FootballGameRead:
    """Manually correct a half's score (e.g. after the fact)."""
    if update.half not in (Half.FIRST, Half.SECOND, Half.OT):
        raise HTTPException(status_code=422, detail="half must be first, second, or ot")
    if update.team not in ("home", "away"):
        raise HTTPException(status_code=422, detail="team must be 'home' or 'away'")
    game = _get_game(game_id, session)
    scores = _get_half_scores(game)
    scores[update.team][_HALF_IDX[update.half]] = update.points
    _set_half_scores(game, scores)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/game-clock")
def set_game_clock(
    game_id: str, update: ClockSet, session: SessionDep
) -> FootballGameRead:
    """Set game clock to a specific value and stop it."""
    game = _get_game(game_id, session)
    game.game_clock = update.seconds
    game.game_clock_running = False
    game.game_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/game-clock/reset")
def reset_game_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Reset game clock to configured default and stop it."""
    game = _get_game(game_id, session)
    game.game_clock = game.game_clock_default
    game.game_clock_running = False
    game.game_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/game-clock/start")
def start_game_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Start the game clock countdown from current remaining seconds."""
    game = _get_game(game_id, session)
    if game.game_clock <= 0:
        raise HTTPException(status_code=400, detail="Game clock is already at zero")
    if not game.game_clock_running:
        game.game_clock_running = True
        game.game_clock_started_at = _now()
    return _to_read(_save(game, session))


@router.patch("/{game_id}/game-clock/stop")
def stop_game_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Stop the game clock and persist current remaining seconds."""
    game = _get_game(game_id, session)
    if game.game_clock_running:
        game.game_clock = _computed_game_clock(game)
        game.game_clock_running = False
        game.game_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock")
def set_play_clock(
    game_id: str, update: ClockSet, session: SessionDep
) -> FootballGameRead:
    """Set clock to a specific value and stop it."""
    game = _get_game(game_id, session)
    game.play_clock = update.seconds
    game.play_clock_running = False
    game.play_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock/reset")
def reset_play_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Reset clock to configured default and stop it."""
    game = _get_game(game_id, session)
    game.play_clock = game.play_clock_default
    game.play_clock_running = False
    game.play_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock/start")
def start_play_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Start the clock countdown from current remaining seconds."""
    game = _get_game(game_id, session)
    if game.play_clock <= 0:
        raise HTTPException(status_code=400, detail="Clock is already at zero")
    if not game.play_clock_running:
        game.play_clock_running = True
        game.play_clock_started_at = _now()
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock/stop")
def stop_play_clock(game_id: str, session: SessionDep) -> FootballGameRead:
    """Stop the clock and persist current remaining seconds."""
    game = _get_game(game_id, session)
    if game.play_clock_running:
        game.play_clock = _computed_play_clock(game)
        game.play_clock_running = False
        game.play_clock_started_at = None
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock/default")
def set_play_clock_default(
    game_id: str, update: ClockSet, session: SessionDep
) -> FootballGameRead:
    """Change the reset duration. Also resets the current clock if it is stopped."""
    game = _get_game(game_id, session)
    if update.seconds < 1:
        raise HTTPException(status_code=422, detail="Default must be >= 1 second")
    game.play_clock_default = update.seconds
    if not game.play_clock_running:
        game.play_clock = update.seconds
        game.play_clock_started_at = None
    return _to_read(_save(game, session))


# Keep unused imports quiet
__all__ = ["router", "Down", "Half"]
