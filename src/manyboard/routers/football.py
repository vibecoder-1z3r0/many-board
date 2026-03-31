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


class PlayClockUpdate(BaseModel):
    seconds: Annotated[int, Field(ge=0)] | None = None
    running: bool | None = None


# --- Helpers ---


def _get_game(game_id: str, session: Session) -> FootballGame:
    game = session.get(FootballGame, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _save(game: FootballGame, session: Session) -> FootballGame:
    game.updated_at = datetime.now(UTC)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


# --- Endpoints ---


@router.post("", status_code=201)
def create_game(data: FootballGameCreate, session: SessionDep) -> FootballGame:
    game = FootballGame(
        home_team=data.home_team,
        away_team=data.away_team,
        home_timeouts=data.home_timeouts,
        away_timeouts=data.away_timeouts,
        play_clock=data.play_clock,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@router.get("")
def list_games(session: SessionDep) -> list[FootballGame]:
    return list(session.exec(select(FootballGame)).all())


@router.get("/{game_id}")
def get_game(game_id: str, session: SessionDep) -> FootballGame:
    return _get_game(game_id, session)


@router.patch("/{game_id}/score")
def update_score(
    game_id: str, update: ScoreUpdate, session: SessionDep
) -> FootballGame:
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
    return _save(game, session)


@router.patch("/{game_id}/down")
def update_down(game_id: str, update: DownUpdate, session: SessionDep) -> FootballGame:
    game = _get_game(game_id, session)
    game.down = update.down
    game.distance = update.distance
    return _save(game, session)


@router.patch("/{game_id}/possession")
def update_possession(
    game_id: str, update: PossessionUpdate, session: SessionDep
) -> FootballGame:
    game = _get_game(game_id, session)
    game.possession = update.possession
    return _save(game, session)


@router.patch("/{game_id}/timeout")
def use_timeout(game_id: str, update: TeamUpdate, session: SessionDep) -> FootballGame:
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
    return _save(game, session)


@router.patch("/{game_id}/timeout/restore")
def restore_timeout(
    game_id: str, update: TeamUpdate, session: SessionDep
) -> FootballGame:
    game = _get_game(game_id, session)
    if update.team == "home":
        game.home_timeouts += 1
    elif update.team == "away":
        game.away_timeouts += 1
    else:
        raise HTTPException(status_code=422, detail="team must be 'home' or 'away'")
    return _save(game, session)


@router.patch("/{game_id}/no-run-zone")
def update_no_run_zone(
    game_id: str, update: NoRunZoneUpdate, session: SessionDep
) -> FootballGame:
    game = _get_game(game_id, session)
    game.no_run_zone = update.enabled
    return _save(game, session)


@router.patch("/{game_id}/half")
def update_half(game_id: str, update: HalfUpdate, session: SessionDep) -> FootballGame:
    game = _get_game(game_id, session)
    game.half = update.half
    return _save(game, session)


@router.patch("/{game_id}/play-clock")
def update_play_clock(
    game_id: str, update: PlayClockUpdate, session: SessionDep
) -> FootballGame:
    game = _get_game(game_id, session)
    if update.seconds is not None:
        game.play_clock = update.seconds
    if update.running is not None:
        game.play_clock_running = update.running
    return _save(game, session)


# Keep unused imports from triggering linter — Down/Half used indirectly via enums
__all__ = ["router", "Down", "Half"]
