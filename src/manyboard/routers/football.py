"""Football game API router."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from manyboard.database import get_session
from manyboard.models.football import (
    Distance,
    Down,
    FootballGame,
    FootballGameCreate,
    FootballGameRead,
    Half,
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


class HalfUpdate(BaseModel):
    half: Half


class TeamNamesUpdate(BaseModel):
    home_team: str | None = None
    away_team: str | None = None


class PlayClockSet(BaseModel):
    """Set clock to a specific value (stops the clock)."""

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


def _computed_clock(game: FootballGame) -> int:
    """Current remaining seconds, accounting for elapsed time if running."""
    if not game.play_clock_running or game.play_clock_started_at is None:
        return game.play_clock
    elapsed = (_now() - game.play_clock_started_at).total_seconds()
    return max(0, game.play_clock - int(elapsed))


def _to_read(game: FootballGame) -> FootballGameRead:
    data = game.model_dump()
    data["play_clock"] = _computed_clock(game)
    return FootballGameRead.model_validate(data)


# --- Endpoints ---


@router.post("", status_code=201)
def create_game(data: FootballGameCreate, session: SessionDep) -> FootballGameRead:
    game = FootballGame(
        home_team=data.home_team,
        away_team=data.away_team,
        home_timeouts=data.home_timeouts,
        away_timeouts=data.away_timeouts,
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
    # Auto-stop in DB if clock expired while running
    if game.play_clock_running and read.play_clock == 0:
        game.play_clock = 0
        game.play_clock_running = False
        game.play_clock_started_at = None
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


@router.patch("/{game_id}/half")
def update_half(
    game_id: str, update: HalfUpdate, session: SessionDep
) -> FootballGameRead:
    game = _get_game(game_id, session)
    game.half = update.half
    return _to_read(_save(game, session))


@router.patch("/{game_id}/play-clock")
def set_play_clock(
    game_id: str, update: PlayClockSet, session: SessionDep
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
        game.play_clock = _computed_clock(game)
        game.play_clock_running = False
        game.play_clock_started_at = None
    return _to_read(_save(game, session))


# Keep unused imports quiet
__all__ = ["router", "Down", "Half"]
