"""API tests for the football game endpoints — written before implementation (TDD)."""

from fastapi.testclient import TestClient


def test_create_football_game(client: TestClient) -> None:
    resp = client.post(
        "/api/football/games",
        json={"home_team": "Eagles", "away_team": "Ravens"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["home_team"] == "Eagles"
    assert data["away_team"] == "Ravens"
    assert data["home_score"] == 0
    assert data["away_score"] == 0
    assert data["half"] == "first"
    assert data["down"] == 1
    assert data["distance"] == "midfield"
    assert data["possession"] == "home"
    assert data["home_timeouts"] == 3
    assert data["away_timeouts"] == 3
    assert data["play_clock"] == 40
    assert data["play_clock_default"] == 40
    assert data["play_clock_running"] is False
    assert data["no_run_zone"] is False
    assert "id" in data
    assert "play_clock_started_at" not in data


def test_create_football_game_custom(client: TestClient) -> None:
    resp = client.post(
        "/api/football/games",
        json={
            "home_team": "Eagles",
            "away_team": "Ravens",
            "home_timeouts": 2,
            "away_timeouts": 2,
            "play_clock": 25,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["home_timeouts"] == 2
    assert data["away_timeouts"] == 2
    assert data["play_clock"] == 25


def test_get_football_game(client: TestClient) -> None:
    create_resp = client.post(
        "/api/football/games",
        json={"home_team": "Eagles", "away_team": "Ravens"},
    )
    game_id = create_resp.json()["id"]

    resp = client.get(f"/api/football/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == game_id


def test_get_football_game_not_found(client: TestClient) -> None:
    resp = client.get("/api/football/games/nonexistent-id")
    assert resp.status_code == 404


def test_list_football_games(client: TestClient) -> None:
    client.post(
        "/api/football/games", json={"home_team": "Eagles", "away_team": "Ravens"}
    )
    client.post(
        "/api/football/games", json={"home_team": "Chiefs", "away_team": "49ers"}
    )
    resp = client.get("/api/football/games")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_add_score_home_touchdown(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 6}
    )
    assert resp.status_code == 200
    assert resp.json()["home_score"] == 6


def test_add_score_away(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "away", "delta": 7}
    )
    assert resp.status_code == 200
    assert resp.json()["away_score"] == 7


def test_score_accumulates(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 6}
    )
    client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 1}
    )
    resp = client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 3}
    )
    assert resp.json()["home_score"] == 10


def test_score_correction_negative_delta(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 6}
    )
    resp = client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": -1}
    )
    assert resp.status_code == 200
    assert resp.json()["home_score"] == 5


def test_score_cannot_go_negative(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": -1}
    )
    assert resp.status_code == 400


def test_update_down_and_distance(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/down", json={"down": 3, "distance": "goal"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["down"] == 3
    assert data["distance"] == "goal"


def test_update_possession(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/possession", json={"possession": "away"}
    )
    assert resp.status_code == 200
    assert resp.json()["possession"] == "away"


def test_use_home_timeout(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/football/games/{game_id}/timeout", json={"team": "home"})
    assert resp.status_code == 200
    assert resp.json()["home_timeouts"] == 2


def test_use_away_timeout(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/football/games/{game_id}/timeout", json={"team": "away"})
    assert resp.status_code == 200
    assert resp.json()["away_timeouts"] == 2


def test_timeout_cannot_go_below_zero(client: TestClient) -> None:
    game_id = _new_game(client, home_timeouts=0)
    resp = client.patch(f"/api/football/games/{game_id}/timeout", json={"team": "home"})
    assert resp.status_code == 400


def test_restore_timeout(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/timeout", json={"team": "home"})
    resp = client.patch(
        f"/api/football/games/{game_id}/timeout/restore", json={"team": "home"}
    )
    assert resp.status_code == 200
    assert resp.json()["home_timeouts"] == 3


def test_toggle_no_run_zone_on(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/no-run-zone", json={"enabled": True}
    )
    assert resp.status_code == 200
    assert resp.json()["no_run_zone"] is True


def test_toggle_no_run_zone_off(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/no-run-zone", json={"enabled": True})
    resp = client.patch(
        f"/api/football/games/{game_id}/no-run-zone", json={"enabled": False}
    )
    assert resp.status_code == 200
    assert resp.json()["no_run_zone"] is False


def test_set_half(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/half", json={"half": "halftime"}
    )
    assert resp.status_code == 200
    assert resp.json()["half"] == "halftime"


def test_set_play_clock_seconds(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"seconds": 25}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["play_clock"] == 25
    assert data["play_clock_running"] is False


def test_set_play_clock_stops_running_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/play-clock/start")
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"seconds": 20}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["play_clock"] == 20
    assert data["play_clock_running"] is False


def test_play_clock_seconds_cannot_be_negative(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"seconds": -1}
    )
    assert resp.status_code == 422


def test_start_play_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/football/games/{game_id}/play-clock/start")
    assert resp.status_code == 200
    assert resp.json()["play_clock_running"] is True


def test_stop_play_clock(client: TestClient) -> None:
    import time

    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/play-clock/start")
    time.sleep(1.1)
    resp = client.patch(f"/api/football/games/{game_id}/play-clock/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["play_clock_running"] is False
    assert data["play_clock"] <= 39  # at least 1 second elapsed


def test_start_clock_at_zero_is_rejected(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/play-clock", json={"seconds": 0})
    resp = client.patch(f"/api/football/games/{game_id}/play-clock/start")
    assert resp.status_code == 400


def test_reset_play_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/play-clock", json={"seconds": 15})
    resp = client.patch(f"/api/football/games/{game_id}/play-clock/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["play_clock"] == 40  # back to default
    assert data["play_clock_running"] is False


def test_get_returns_computed_clock_while_running(client: TestClient) -> None:
    import time

    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/play-clock/start")
    time.sleep(1.1)
    resp = client.get(f"/api/football/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["play_clock"] <= 39  # computed, not raw stored value


def test_create_game_default_team_names(client: TestClient) -> None:
    resp = client.post("/api/football/games", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["home_team"] == "Home"
    assert data["away_team"] == "Away"


def test_update_team_names(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/teams",
        json={"home_team": "Chiefs", "away_team": "49ers"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["home_team"] == "Chiefs"
    assert data["away_team"] == "49ers"


def test_update_only_home_team(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/teams", json={"home_team": "Chiefs"}
    )
    assert resp.status_code == 200
    assert resp.json()["home_team"] == "Chiefs"
    assert resp.json()["away_team"] == "Ravens"


def test_updated_at_changes_on_update(client: TestClient) -> None:
    game_id = _new_game(client)
    before = client.get(f"/api/football/games/{game_id}").json()["updated_at"]
    import time

    time.sleep(0.01)
    client.patch(
        f"/api/football/games/{game_id}/score", json={"team": "home", "delta": 6}
    )
    after = client.get(f"/api/football/games/{game_id}").json()["updated_at"]
    assert after >= before


# ── Delete ───────────────────────────────────────────────────────────────────


# ── Game Clock ───────────────────────────────────────────────────────────────


def test_game_created_with_default_game_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    data = client.get(f"/api/football/games/{game_id}").json()
    assert data["game_clock"] == 1200
    assert data["game_clock_default"] == 1200
    assert data["game_clock_running"] is False


def test_game_created_with_custom_game_clock(client: TestClient) -> None:
    resp = client.post(
        "/api/football/games",
        json={"home_team": "A", "away_team": "B", "game_clock": 600},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["game_clock"] == 600
    assert data["game_clock_default"] == 600


def test_start_game_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/football/games/{game_id}/game-clock/start")
    assert resp.status_code == 200
    assert resp.json()["game_clock_running"] is True


def test_stop_game_clock(client: TestClient) -> None:
    import time

    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/game-clock/start")
    time.sleep(1.1)
    resp = client.patch(f"/api/football/games/{game_id}/game-clock/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["game_clock_running"] is False
    assert data["game_clock"] <= 1199


def test_reset_game_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/game-clock", json={"seconds": 100})
    resp = client.patch(f"/api/football/games/{game_id}/game-clock/reset")
    assert resp.status_code == 200
    assert resp.json()["game_clock"] == 1200
    assert resp.json()["game_clock_running"] is False


def test_set_game_clock(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/game-clock", json={"seconds": 300}
    )
    assert resp.status_code == 200
    assert resp.json()["game_clock"] == 300
    assert resp.json()["game_clock_running"] is False


def test_start_game_clock_at_zero_rejected(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/game-clock", json={"seconds": 0})
    resp = client.patch(f"/api/football/games/{game_id}/game-clock/start")
    assert resp.status_code == 400


def test_get_computes_game_clock_while_running(client: TestClient) -> None:
    import time

    game_id = _new_game(client)
    client.patch(f"/api/football/games/{game_id}/game-clock/start")
    time.sleep(1.1)
    resp = client.get(f"/api/football/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["game_clock"] <= 1199


# ── Delete ───────────────────────────────────────────────────────────────────


def test_delete_football_game(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.delete(f"/api/football/games/{game_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/football/games/{game_id}").status_code == 404


def test_delete_football_game_not_found(client: TestClient) -> None:
    resp = client.delete("/api/football/games/nonexistent")
    assert resp.status_code == 404


# --- helpers ---


def _new_game(client: TestClient, **kwargs: int) -> str:
    payload: dict[str, object] = {
        "home_team": "Eagles",
        "away_team": "Ravens",
        **kwargs,
    }
    return client.post("/api/football/games", json=payload).json()["id"]
