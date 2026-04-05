"""API tests for the baseball game endpoints — written before implementation (TDD)."""

from fastapi.testclient import TestClient

# ── Creation & retrieval ─────────────────────────────────────────────────────


def test_create_baseball_game_defaults(client: TestClient) -> None:
    resp = client.post("/api/baseball/games", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["home_team"] == "Home"
    assert data["away_team"] == "Away"
    assert data["num_innings"] == 6
    assert data["current_inning"] == 1
    assert data["half"] == "top"
    assert data["balls"] == 0
    assert data["strikes"] == 0
    assert data["outs"] == 0
    assert data["base_first"] is False
    assert data["base_second"] is False
    assert data["base_third"] is False
    assert data["bso_style"] == "dots"
    assert data["away_total"] == 0
    assert data["home_total"] == 0
    assert data["status"] == "active"
    assert len(data["scores"]["away"]) == 6
    assert len(data["scores"]["home"]) == 6
    assert all(s is None for s in data["scores"]["away"])
    assert "id" in data
    assert "scores_json" not in data


def test_create_baseball_game_custom(client: TestClient) -> None:
    resp = client.post(
        "/api/baseball/games",
        json={"home_team": "Eagles", "away_team": "Ravens", "num_innings": 9},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["home_team"] == "Eagles"
    assert data["away_team"] == "Ravens"
    assert data["num_innings"] == 9
    assert len(data["scores"]["away"]) == 9


def test_get_baseball_game(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.get(f"/api/baseball/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == game_id


def test_get_baseball_game_not_found(client: TestClient) -> None:
    resp = client.get("/api/baseball/games/nonexistent")
    assert resp.status_code == 404


def test_list_baseball_games(client: TestClient) -> None:
    _new_game(client)
    _new_game(client)
    resp = client.get("/api/baseball/games")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ── Team names ───────────────────────────────────────────────────────────────


def test_update_team_names(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/teams",
        json={"home_team": "Tigers", "away_team": "Bears"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["home_team"] == "Tigers"
    assert data["away_team"] == "Bears"


def test_update_only_home_team(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/teams", json={"home_team": "Tigers"}
    )
    assert resp.status_code == 200
    assert resp.json()["home_team"] == "Tigers"
    assert resp.json()["away_team"] == "Away"


# ── BSO count ────────────────────────────────────────────────────────────────


def test_record_ball(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/ball")
    assert resp.status_code == 200
    assert resp.json()["balls"] == 1


def test_ball_resets_on_walk(client: TestClient) -> None:
    game_id = _new_game(client)
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/ball")
    resp = client.patch(f"/api/baseball/games/{game_id}/ball")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balls"] == 0
    assert data["strikes"] == 0


def test_record_strike(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/strike")
    assert resp.status_code == 200
    assert resp.json()["strikes"] == 1


def test_strikeout_adds_out_and_resets_count(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/strike")
    client.patch(f"/api/baseball/games/{game_id}/strike")
    resp = client.patch(f"/api/baseball/games/{game_id}/strike")
    assert resp.status_code == 200
    data = resp.json()
    assert data["strikes"] == 0
    assert data["balls"] == 0
    assert data["outs"] == 1


def test_foul_adds_strike_when_less_than_two(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/foul")
    assert resp.status_code == 200
    assert resp.json()["strikes"] == 1


def test_foul_does_not_add_strike_at_two(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/strike")
    client.patch(f"/api/baseball/games/{game_id}/strike")
    resp = client.patch(f"/api/baseball/games/{game_id}/foul")
    assert resp.status_code == 200
    assert resp.json()["strikes"] == 2  # unchanged


def test_record_out(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/out")
    assert resp.status_code == 200
    assert resp.json()["outs"] == 1


def test_reset_count(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/ball")
    client.patch(f"/api/baseball/games/{game_id}/ball")
    client.patch(f"/api/baseball/games/{game_id}/strike")
    resp = client.patch(f"/api/baseball/games/{game_id}/count/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balls"] == 0
    assert data["strikes"] == 0


# ── End of half-inning (3 outs) ──────────────────────────────────────────────


def test_three_outs_end_top_half(client: TestClient) -> None:
    game_id = _new_game(client)
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    resp = client.get(f"/api/baseball/games/{game_id}")
    data = resp.json()
    assert data["outs"] == 0
    assert data["half"] == "bottom"
    assert data["current_inning"] == 1


def test_three_outs_end_bottom_half_advances_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    # End top of 1st
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    # End bottom of 1st
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    resp = client.get(f"/api/baseball/games/{game_id}")
    data = resp.json()
    assert data["outs"] == 0
    assert data["half"] == "top"
    assert data["current_inning"] == 2


def test_three_outs_finalizes_inning_score_as_zero(client: TestClient) -> None:
    game_id = _new_game(client)
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    data = client.get(f"/api/baseball/games/{game_id}").json()
    # Top of 1st (away team) scored 0 — should be 0, not None
    assert data["scores"]["away"][0] == 0


def test_three_outs_resets_bases(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/bases", json={"first": True})
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    data = client.get(f"/api/baseball/games/{game_id}").json()
    assert data["base_first"] is False


# ── Scoring runs ─────────────────────────────────────────────────────────────


def test_record_run_in_top_half(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scores"]["away"][0] == 1
    assert data["away_total"] == 1


def test_record_multiple_runs(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/run")
    client.patch(f"/api/baseball/games/{game_id}/run")
    resp = client.patch(f"/api/baseball/games/{game_id}/run")
    data = resp.json()
    assert data["scores"]["away"][0] == 3
    assert data["away_total"] == 3


def test_record_run_in_bottom_half(client: TestClient) -> None:
    game_id = _new_game(client)
    # End top of 1st
    for _ in range(3):
        client.patch(f"/api/baseball/games/{game_id}/out")
    resp = client.patch(f"/api/baseball/games/{game_id}/run")
    data = resp.json()
    assert data["scores"]["home"][0] == 1
    assert data["home_total"] == 1


# ── Inning score correction ───────────────────────────────────────────────────


def test_set_inning_score_directly(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/inning-score",
        json={"inning": 1, "half": "top", "runs": 4},
    )
    assert resp.status_code == 200
    assert resp.json()["scores"]["away"][0] == 4
    assert resp.json()["away_total"] == 4


# ── Bases ────────────────────────────────────────────────────────────────────


def test_set_bases(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/bases",
        json={"first": True, "second": False, "third": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_first"] is True
    assert data["base_second"] is False
    assert data["base_third"] is True


# ── Innings management ───────────────────────────────────────────────────────


def test_add_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/inning/add")
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_innings"] == 7
    assert len(data["scores"]["away"]) == 7
    assert data["scores"]["away"][6] is None


def test_remove_last_unplayed_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/inning/remove")
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_innings"] == 5
    assert len(data["scores"]["away"]) == 5


def test_cannot_remove_played_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    # Play through all 6 innings
    for _ in range(6):
        for _ in range(3):
            client.patch(f"/api/baseball/games/{game_id}/out")
        for _ in range(3):
            client.patch(f"/api/baseball/games/{game_id}/out")
    resp = client.patch(f"/api/baseball/games/{game_id}/inning/remove")
    assert resp.status_code == 400


def test_cannot_remove_below_one_inning(client: TestClient) -> None:
    game_id = _new_game(client, num_innings=1)
    resp = client.patch(f"/api/baseball/games/{game_id}/inning/remove")
    assert resp.status_code == 400


# ── BSO style ────────────────────────────────────────────────────────────────


def test_set_bso_style(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/bso-style", json={"style": "numbers"}
    )
    assert resp.status_code == 200
    assert resp.json()["bso_style"] == "numbers"


# ── Current inning navigation ─────────────────────────────────────────────────


def test_set_current_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/inning", json={"inning": 3, "half": "bottom"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_inning"] == 3
    assert data["half"] == "bottom"


# ── Score correction (negative runs) ─────────────────────────────────────────


def test_inning_score_negative_correction(client: TestClient) -> None:
    game_id = _new_game(client)
    # Set inning 1 top to 3, then correct down to 1
    client.patch(
        f"/api/baseball/games/{game_id}/inning-score",
        json={"inning": 1, "half": "top", "runs": 3},
    )
    resp = client.patch(
        f"/api/baseball/games/{game_id}/inning-score",
        json={"inning": 1, "half": "top", "runs": -1},
    )
    assert resp.status_code == 200
    assert resp.json()["scores"]["away"][0] == -1


# ── Change sides ──────────────────────────────────────────────────────────────


def test_change_sides_top_to_bottom(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(f"/api/baseball/games/{game_id}/change-sides")
    assert resp.status_code == 200
    data = resp.json()
    assert data["half"] == "bottom"
    assert data["current_inning"] == 1
    assert data["outs"] == 0
    assert data["balls"] == 0
    assert data["strikes"] == 0


def test_change_sides_bottom_to_top_advances_inning(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(f"/api/baseball/games/{game_id}/change-sides")  # top → bottom
    resp = client.patch(f"/api/baseball/games/{game_id}/change-sides")  # bottom → top 2
    assert resp.status_code == 200
    data = resp.json()
    assert data["half"] == "top"
    assert data["current_inning"] == 2


def test_change_sides_clears_bases(client: TestClient) -> None:
    game_id = _new_game(client)
    client.patch(
        f"/api/baseball/games/{game_id}/bases",
        json={"first": True, "second": True},
    )
    resp = client.patch(f"/api/baseball/games/{game_id}/change-sides")
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_first"] is False
    assert data["base_second"] is False


# ── Status ───────────────────────────────────────────────────────────────────


def test_set_game_final(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.patch(
        f"/api/baseball/games/{game_id}/status", json={"status": "final"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "final"


# ── Delete ───────────────────────────────────────────────────────────────────


def test_delete_baseball_game(client: TestClient) -> None:
    game_id = _new_game(client)
    resp = client.delete(f"/api/baseball/games/{game_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/baseball/games/{game_id}").status_code == 404


def test_delete_baseball_game_not_found(client: TestClient) -> None:
    resp = client.delete("/api/baseball/games/nonexistent")
    assert resp.status_code == 404


# ── helpers ───────────────────────────────────────────────────────────────────


def _new_game(client: TestClient, **kwargs: object) -> str:
    payload: dict[str, object] = {**kwargs}
    return client.post("/api/baseball/games", json=payload).json()["id"]
