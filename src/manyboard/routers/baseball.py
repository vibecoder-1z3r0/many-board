"""Baseball / wiffleball game API router."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from manyboard.database import get_session
from manyboard.models.baseball import (
    BaseballGame,
    BaseballGameCreate,
    BaseballGameRead,
    BSOStyle,
    InningCell,
    InningHalf,
    InningScores,
)

router = APIRouter(prefix="/api/baseball/games", tags=["baseball"])

SessionDep = Annotated[Session, Depends(get_session)]


# --- Request schemas ---


class TeamNamesUpdate(BaseModel):
    home_team: str | None = None
    away_team: str | None = None


class BasesUpdate(BaseModel):
    first: bool | None = None
    second: bool | None = None
    third: bool | None = None


class BSOStyleUpdate(BaseModel):
    style: BSOStyle


class InningNavUpdate(BaseModel):
    inning: Annotated[int, Field(ge=1)]
    half: InningHalf


class InningScoreUpdate(BaseModel):
    inning: Annotated[int, Field(ge=1)]
    half: InningHalf
    # int = runs scored; None = set dash ("-"); negative allowed for correction
    runs: int | None


class StatusUpdate(BaseModel):
    status: str


# --- Helpers ---


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_game(game_id: str, session: Session) -> BaseballGame:
    game = session.get(BaseballGame, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _save(game: BaseballGame, session: Session) -> BaseballGame:
    game.updated_at = _now()
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def _get_scores(game: BaseballGame) -> dict[str, list[InningCell]]:
    return json.loads(game.scores_json)  # type: ignore[no-any-return]


def _set_scores(game: BaseballGame, scores: dict[str, list[InningCell]]) -> None:
    game.scores_json = json.dumps(scores)


def _cell_runs(cell: InningCell) -> int:
    """Numeric value of a cell for totals: int as-is, dash/None = 0."""
    return cell if isinstance(cell, int) else 0


def _current_team(game: BaseballGame) -> str:
    return "away" if game.half == InningHalf.TOP else "home"


def _inning_idx(game: BaseballGame) -> int:
    return game.current_inning - 1


def _end_half_inning(game: BaseballGame) -> None:
    """Finalize current half-inning score and advance to next half."""
    scores = _get_scores(game)
    team = _current_team(game)
    idx = _inning_idx(game)

    # Finalize: null → 0 (half was played, no runs scored)
    if 0 <= idx < len(scores[team]) and scores[team][idx] is None:
        scores[team][idx] = 0
    _set_scores(game, scores)

    # Reset count and bases
    game.balls = 0
    game.strikes = 0
    game.outs = 0
    game.base_first = False
    game.base_second = False
    game.base_third = False

    # Advance
    if game.half == InningHalf.TOP:
        game.half = InningHalf.BOTTOM
    else:
        game.half = InningHalf.TOP
        game.current_inning += 1


def _to_read(game: BaseballGame) -> BaseballGameRead:
    scores = _get_scores(game)
    away = scores.get("away", [])
    home = scores.get("home", [])
    return BaseballGameRead(
        id=game.id,
        home_team=game.home_team,
        away_team=game.away_team,
        num_innings=game.num_innings,
        scores=InningScores(away=away, home=home),
        current_inning=game.current_inning,
        half=game.half,
        balls=game.balls,
        strikes=game.strikes,
        outs=game.outs,
        base_first=game.base_first,
        base_second=game.base_second,
        base_third=game.base_third,
        bso_style=game.bso_style,
        away_total=sum(_cell_runs(s) for s in away),
        home_total=sum(_cell_runs(s) for s in home),
        status=game.status,
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


# --- Endpoints ---


@router.post("", status_code=201)
def create_game(data: BaseballGameCreate, session: SessionDep) -> BaseballGameRead:
    scores = {"away": [None] * data.num_innings, "home": [None] * data.num_innings}
    game = BaseballGame(
        home_team=data.home_team,
        away_team=data.away_team,
        num_innings=data.num_innings,
        scores_json=json.dumps(scores),
        bso_style=data.bso_style,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return _to_read(game)


@router.get("")
def list_games(session: SessionDep) -> list[BaseballGameRead]:
    return [_to_read(g) for g in session.exec(select(BaseballGame)).all()]


@router.get("/{game_id}")
def get_game(game_id: str, session: SessionDep) -> BaseballGameRead:
    return _to_read(_get_game(game_id, session))


@router.delete("/{game_id}", status_code=204)
def delete_game(game_id: str, session: SessionDep) -> None:
    game = _get_game(game_id, session)
    session.delete(game)
    session.commit()


@router.patch("/{game_id}/teams")
def update_teams(
    game_id: str, update: TeamNamesUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if update.home_team is not None:
        game.home_team = update.home_team
    if update.away_team is not None:
        game.away_team = update.away_team
    return _to_read(_save(game, session))


@router.patch("/{game_id}/ball")
def record_ball(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if game.balls < 3:
        game.balls += 1
    else:
        # Walk — reset count; ump manages base runners manually
        game.balls = 0
        game.strikes = 0
    return _to_read(_save(game, session))


@router.patch("/{game_id}/strike")
def record_strike(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if game.strikes < 2:
        game.strikes += 1
    else:
        # Strikeout — reset count, add out
        game.balls = 0
        game.strikes = 0
        game.outs += 1
        if game.outs >= 3:
            _end_half_inning(game)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/foul")
def record_foul(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if game.strikes < 2:
        game.strikes += 1
    # At 2 strikes foul is no change
    return _to_read(_save(game, session))


@router.patch("/{game_id}/out")
def record_out(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    game.balls = 0
    game.strikes = 0
    game.outs += 1
    if game.outs >= 3:
        _end_half_inning(game)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/change-sides")
def change_sides(game_id: str, session: SessionDep) -> BaseballGameRead:
    """End the current half-inning immediately (like a 3rd out)."""
    game = _get_game(game_id, session)
    _end_half_inning(game)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/count/reset")
def reset_count(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    game.balls = 0
    game.strikes = 0
    return _to_read(_save(game, session))


@router.patch("/{game_id}/run")
def record_run(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    scores = _get_scores(game)
    team = _current_team(game)
    idx = _inning_idx(game)
    if 0 <= idx < len(scores[team]):
        scores[team][idx] = _cell_runs(scores[team][idx]) + 1
    _set_scores(game, scores)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/inning-score")
def set_inning_score(
    game_id: str, update: InningScoreUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    scores = _get_scores(game)
    team = "away" if update.half == InningHalf.TOP else "home"
    idx = update.inning - 1
    if idx < 0 or idx >= len(scores[team]):
        raise HTTPException(status_code=400, detail="Inning out of range")
    # None → dash; int stored as-is (negative allowed for score correction)
    scores[team][idx] = "-" if update.runs is None else update.runs
    _set_scores(game, scores)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/bases")
def update_bases(
    game_id: str, update: BasesUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if update.first is not None:
        game.base_first = update.first
    if update.second is not None:
        game.base_second = update.second
    if update.third is not None:
        game.base_third = update.third
    return _to_read(_save(game, session))


@router.patch("/{game_id}/inning/add")
def add_inning(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    scores = _get_scores(game)
    scores["away"].append(None)
    scores["home"].append(None)
    game.num_innings += 1
    _set_scores(game, scores)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/inning/remove")
def remove_inning(game_id: str, session: SessionDep) -> BaseballGameRead:
    game = _get_game(game_id, session)
    if game.num_innings <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last inning")
    scores = _get_scores(game)
    if scores["away"][-1] is not None or scores["home"][-1] is not None:
        raise HTTPException(status_code=400, detail="Cannot remove a played inning")
    scores["away"].pop()
    scores["home"].pop()
    game.num_innings -= 1
    _set_scores(game, scores)
    return _to_read(_save(game, session))


@router.patch("/{game_id}/inning")
def set_inning(
    game_id: str, update: InningNavUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    game.current_inning = update.inning
    game.half = update.half
    return _to_read(_save(game, session))


@router.patch("/{game_id}/bso-style")
def set_bso_style(
    game_id: str, update: BSOStyleUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    game.bso_style = update.style
    return _to_read(_save(game, session))


@router.patch("/{game_id}/status")
def set_status(
    game_id: str, update: StatusUpdate, session: SessionDep
) -> BaseballGameRead:
    game = _get_game(game_id, session)
    game.status = update.status
    return _to_read(_save(game, session))
