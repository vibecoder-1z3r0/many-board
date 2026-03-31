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
    assert data["play_clock_running"] is False
    assert data["no_run_zone"] is False
    assert "id" in data


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


def test_update_play_clock_seconds(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"seconds": 25}
    )
    assert resp.status_code == 200
    assert resp.json()["play_clock"] == 25


def test_update_play_clock_running(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"running": True}
    )
    assert resp.status_code == 200
    assert resp.json()["play_clock_running"] is True


def test_play_clock_seconds_cannot_be_negative(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/football/games/{game_id}/play-clock", json={"seconds": -1}
    )
    assert resp.status_code == 422


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


# --- helpers ---


def _new_game(client: TestClient, **kwargs: int) -> str:
    payload: dict[str, object] = {
        "home_team": "Eagles",
        "away_team": "Ravens",
        **kwargs,
    }
    return client.post("/api/football/games", json=payload).json()["id"]
