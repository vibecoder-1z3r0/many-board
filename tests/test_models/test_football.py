"""Unit tests for football game models — written before implementation (TDD)."""

from manyboard.models.football import (
    Distance,
    Down,
    FootballGame,
    FootballGameCreate,
    Half,
    Possession,
)


def test_football_game_defaults() -> None:
    game = FootballGame(home_team="Eagles", away_team="Ravens")
    assert game.home_score == 0
    assert game.away_score == 0
    assert game.half == Half.FIRST
    assert game.down == Down.FIRST
    assert game.distance == Distance.MIDFIELD
    assert game.possession == Possession.HOME
    assert game.home_timeouts == 3
    assert game.away_timeouts == 3
    assert game.play_clock == 30
    assert game.play_clock_running is False
    assert game.no_run_zone is False


def test_football_game_create_schema() -> None:
    create = FootballGameCreate(home_team="Eagles", away_team="Ravens")
    assert create.home_team == "Eagles"
    assert create.away_team == "Ravens"
    assert create.home_timeouts == 3
    assert create.away_timeouts == 3
    assert create.play_clock == 30


def test_football_game_create_custom_timeouts() -> None:
    create = FootballGameCreate(
        home_team="Eagles",
        away_team="Ravens",
        home_timeouts=2,
        away_timeouts=2,
        play_clock=25,
    )
    assert create.home_timeouts == 2
    assert create.away_timeouts == 2
    assert create.play_clock == 25


def test_half_enum_values() -> None:
    assert Half.FIRST == "first"
    assert Half.HALFTIME == "halftime"
    assert Half.SECOND == "second"
    assert Half.FINAL == "final"


def test_down_enum_values() -> None:
    assert Down.FIRST == 1
    assert Down.SECOND == 2
    assert Down.THIRD == 3
    assert Down.FOURTH == 4


def test_distance_enum_values() -> None:
    assert Distance.MIDFIELD == "midfield"
    assert Distance.GOAL == "goal"


def test_possession_enum_values() -> None:
    assert Possession.HOME == "home"
    assert Possession.AWAY == "away"


def test_football_game_has_id() -> None:
    game = FootballGame(home_team="Eagles", away_team="Ravens")
    assert game.id is not None
    assert len(game.id) > 0


def test_two_games_have_different_ids() -> None:
    g1 = FootballGame(home_team="Eagles", away_team="Ravens")
    g2 = FootballGame(home_team="Chiefs", away_team="49ers")
    assert g1.id != g2.id
