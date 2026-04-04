"""Unit tests for baseball game models — written before implementation (TDD)."""

from manyboard.models.baseball import (
    BaseballGame,
    BaseballGameCreate,
    BSOStyle,
    InningHalf,
)


def test_baseball_game_defaults() -> None:
    game = BaseballGame()
    assert game.home_team == "Home"
    assert game.away_team == "Away"
    assert game.num_innings == 6
    assert game.current_inning == 1
    assert game.half == InningHalf.TOP
    assert game.balls == 0
    assert game.strikes == 0
    assert game.outs == 0
    assert game.base_first is False
    assert game.base_second is False
    assert game.base_third is False
    assert game.bso_style == BSOStyle.DOTS
    assert game.status == "active"


def test_baseball_game_create_schema_defaults() -> None:
    create = BaseballGameCreate()
    assert create.home_team == "Home"
    assert create.away_team == "Away"
    assert create.num_innings == 6


def test_baseball_game_create_schema_custom() -> None:
    create = BaseballGameCreate(
        home_team="Eagles",
        away_team="Ravens",
        num_innings=9,
    )
    assert create.home_team == "Eagles"
    assert create.away_team == "Ravens"
    assert create.num_innings == 9


def test_inning_half_enum_values() -> None:
    assert InningHalf.TOP == "top"
    assert InningHalf.BOTTOM == "bottom"


def test_bso_style_enum_values() -> None:
    assert BSOStyle.DOTS == "dots"
    assert BSOStyle.NUMBERS == "numbers"
    assert BSOStyle.BOTH == "both"


def test_baseball_game_has_id() -> None:
    game = BaseballGame()
    assert game.id is not None
    assert len(game.id) > 0


def test_two_games_have_different_ids() -> None:
    g1 = BaseballGame()
    g2 = BaseballGame()
    assert g1.id != g2.id
