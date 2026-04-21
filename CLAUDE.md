# Many Board — Project Context

Backyard sports scoreboard. FastAPI + SQLite backend, vanilla HTML/JS frontend.
Designed to run on a local network (Raspberry Pi or similar) and be viewed on
phones/tablets at the field.

See **[ADDING_A_SPORT.md](./ADDING_A_SPORT.md)** for the step-by-step guide to
implementing a new sport.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.13+, FastAPI, SQLModel (SQLite), Pydantic v2 |
| Package mgr | uv |
| Lint / format | ruff |
| Type check | mypy |
| Tests | pytest |
| Frontend | Vanilla HTML + CSS + JS (no build step, no frameworks) |

---

## Dev Setup

```bash
# Install dependencies
uv sync

# Run dev server (hot-reload, timestamps in access log)
uv run uvicorn manyboard.main:app --reload --log-config log_config.json

# Run tests
uv run pytest

# Lint + format
uv run ruff check --fix
uv run ruff format

# Type check
uv run mypy src/
```

The SQLite database file (`manyboard.db`) is created automatically on first run.
**If you add columns to a model, delete the db file and restart** — SQLite does
not auto-migrate.

---

## Project Structure

```
src/manyboard/
  main.py                   # FastAPI app, router registration
  database.py               # SQLite engine + get_session() dependency
  models/
    football.py             # FootballGame, FootballGameCreate, FootballGameRead
    baseball.py             # BaseballGame, BaseballGameCreate, BaseballGameRead
  routers/
    football.py             # All /api/football/games/* endpoints
    baseball.py             # All /api/baseball/games/* endpoints
  static/
    index.html              # Game list / lobby (polls every 1s)
    football.html           # Live football scoreboard (polls every 200ms)
    baseball.html           # Live baseball scoreboard (polls every 200ms)
    favicon.svg             # SVG favicon (served as /favicon.svg)

tests/
  test_api/
    test_football.py
    test_baseball.py
```

---

## Architecture Decisions

### Server is the clock source of truth
Game clocks and play clocks are stored server-side as remaining seconds
(`game_clock`, `play_clock`) plus a `*_started_at` UTC timestamp. On every GET
request the server computes elapsed time and returns the current remaining
seconds. Clients do **not** interpolate between polls — they display exactly
what the server returns. At 200ms polling, max visual lag is imperceptible.

No client-side local clock variables. No competing timers. The pattern that was
removed: `localGameClock` / `localPlayClock` decremented every 1s by a separate
`setInterval`. Do not re-introduce this.

### REST polling, not WebSockets
200ms polling on game views, 1s on the index page. Simple to reason about,
trivially restartable, no connection state to manage.

### Connection status
`failCount` tracks consecutive poll failures. After 3 failures (~600ms) the
header shows a red "Signal Lost" badge. On next success it returns to green
"Connected". Both `football.html` and `baseball.html` implement this.

### Scores stored as JSON strings
Football: `half_scores_json` — `{"away": [null, null, null], "home": [null, null, null]}`
for [1H, 2H, OT]. Columns are nullable; null = not yet played.

Baseball: `scores_json` — `{"away": [...], "home": [...]}` where each cell is
`int` (runs), `null` (inning not yet played), or `"-"` (dash — e.g. home team
wins in top of 9th, bottom never played). The `_cell_runs()` helper handles
all three.

### OT is opt-in
Football OT is hidden by default. The "Enable OT" button in the Control view
sets `ot_enabled = True`. The OT column in the box score and the OT half button
only appear when `ot_enabled` is true OR when OT scores already exist.

### Inning auto-advance
Baseball: recording a 3rd out calls `_end_half_inning()` which finalizes the
current half (null → 0), resets BSO + bases, and advances to the next half or
next inning.

---

## Model Conventions

- All DB models extend `SQLModel` with `table=True`.
- `*Create` schemas are used for POST request bodies.
- `*Read` schemas are returned by all endpoints — they replace raw JSON fields
  with parsed/computed values (e.g. `scores_json` → `InningScores`, clock
  `started_at` timestamps → computed remaining seconds).
- `_to_read(game)` converts a DB model to a Read schema.
- `_save(game, session)` sets `updated_at`, commits, refreshes, and returns.
- `_get_game(game_id, session)` fetches by PK or raises 404.
- `StrEnum` is used for all enum fields (Python 3.11+, no `values()` needed).
- IDs are UUIDs stored as strings.

---

## API Overview

### Football — `/api/football/games`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create game |
| GET | `/` | List games |
| GET | `/{id}` | Get game |
| DELETE | `/{id}` | Delete game |
| PATCH | `/{id}/score` | Add/subtract score |
| PATCH | `/{id}/down` | Set down + distance |
| PATCH | `/{id}/possession` | Set possession |
| PATCH | `/{id}/timeout` | Use timeout |
| PATCH | `/{id}/timeout/restore` | Restore timeout |
| PATCH | `/{id}/half` | Set half (first/halftime/second/ot/final) |
| PATCH | `/{id}/no-run-zone` | Toggle NRZ |
| PATCH | `/{id}/game-clock` | Set game clock (seconds) |
| PATCH | `/{id}/game-clock/start` | Start game clock |
| PATCH | `/{id}/game-clock/stop` | Stop game clock |
| PATCH | `/{id}/game-clock/reset` | Reset game clock to default |
| PATCH | `/{id}/play-clock` | Set play clock (seconds) |
| PATCH | `/{id}/play-clock/start` | Start play clock |
| PATCH | `/{id}/play-clock/stop` | Stop play clock |
| PATCH | `/{id}/play-clock/reset` | Reset play clock to default |
| PATCH | `/{id}/play-clock/default` | Change play clock reset duration |
| PATCH | `/{id}/half-score` | Manually correct a half score |
| PATCH | `/{id}/pat` | Set PAT marker (1pt / 2pt / clear) |
| PATCH | `/{id}/ot` | Enable/disable OT |
| PATCH | `/{id}/teams` | Update team names |
| PATCH | `/{id}/status` | Set game status string (default `"active"`) |

Half transition logic: FIRST→HALFTIME snapshots 1H score; SECOND→FINAL or
SECOND→OT snapshots 2H score; OT→FINAL snapshots OT score.

### Baseball — `/api/baseball/games`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create game |
| GET | `/` | List games |
| GET | `/{id}` | Get game |
| DELETE | `/{id}` | Delete game |
| PATCH | `/{id}/ball` | Record ball (4th = walk, resets count) |
| PATCH | `/{id}/strike` | Record strike (3rd = strikeout, adds out) |
| PATCH | `/{id}/foul` | Record foul (no-op at 2 strikes) |
| PATCH | `/{id}/out` | Record out (resets count; 3rd ends half) |
| PATCH | `/{id}/change-sides` | End current half immediately |
| PATCH | `/{id}/run` | Add/subtract run (`delta` body field, default +1) |
| PATCH | `/{id}/inning-score` | Manually set inning score (int or null→"-") |
| PATCH | `/{id}/bases` | Update base runners |
| PATCH | `/{id}/inning/add` | Add an extra inning |
| PATCH | `/{id}/inning/remove` | Remove last (unplayed) inning |
| PATCH | `/{id}/inning` | Jump to inning + half |
| PATCH | `/{id}/count/reset` | Reset B/S count |
| PATCH | `/{id}/teams` | Update team names |
| PATCH | `/{id}/bso-style` | Set BSO display style (dots/numbers/both) |
| PATCH | `/{id}/status` | Set game status string |
| PATCH | `/{id}/stat` | Increment/decrement a stat (`team`, `stat`, `delta`) |
| PATCH | `/{id}/batting` | Set at-bat / next-up text and visibility |

Stats (`stat` field values): `singles`, `doubles`, `triples`, `hrs`, `strikeouts`, `lob`, `errors`.
`team` is `"home"` or `"away"`. `errors` and `strikeouts` should be posted to the **fielding** team.
`home_hits` / `away_hits` are computed in `_to_read` (sum of 1B+2B+3B+HR) and returned read-only.
`home_errors` / `away_errors` are stored directly and also returned in Read.

`batting` fields: `at_bat` (str), `next_up` (str), `at_bat_visible` (bool), `next_up_visible` (bool).
All optional — only supplied fields are updated. Modern view renders banners when visible and non-empty.

### Status field (both sports)
Both `FootballGame` and `BaseballGame` have a `status: str` field (default `"active"`).
The UI currently uses `"active"` and `"final"`. The field is a free string — any value is
accepted. The frontend reads it to show `FINAL` labels or style the display accordingly.

---

## Frontend Conventions

- Each game view polls `/api/{sport}/games/{id}` every 200ms.
- `state` is the raw parsed JSON from the last successful poll.
- `render()` is called on every successful poll and after every PATCH action.
- `poll()` tracks `failCount`; `setConnStatus(bool)` updates the header badge.
- `switchView(v)` updates the URL search param `?view=v` so refreshes restore
  the current tab.
- Theme is stored in `localStorage` under key `mbTheme`; a `<select>` in every
  header calls `applyTheme(t)` which sets `data-theme` on `<html>` and syncs
  the select. Three themes: `default` (navy/crimson), `stadium` (black/cyan),
  `field` (dark green/orange).
- Colors use CSS custom properties (`--bg`, `--panel`, `--accent`, etc.) defined
  in `:root` with overrides for `[data-theme="stadium"]` and
  `[data-theme="field"]`.
- Orbitron (Google Fonts) is used for clock and score numbers.
- Sport-semantic colors are hardcoded (not themed): ball blue `#3498db`, strike
  orange `#f39c12`, foul `#e67e22`, connected green `#2ecc71`.
- Display views use `clamp(min, preferred, max)` for font sizes and spacing so
  they scale naturally from phones to tablets without media queries.

### Theme-specific view overrides

Views that have a sport-specific aesthetic (e.g. the baseball Scoreboard tab
which mimics a Fenway-style manual scoreboard) should use CSS vars by default
so they inherit the current theme, and add `[data-theme="field"]`-scoped
overrides for the cases where the theme naturally matches the sport aesthetic:

```css
/* Default: use app theme vars */
.fw-board { background: var(--panel); color: var(--text); }

/* Field theme: override to Fenway green palette */
[data-theme="field"] .fw-board { background: #2d5a1b; color: #f5e6c8; }
```

This keeps the view usable in all themes while looking purpose-built in the
most thematically appropriate one.

### View conventions per sport

Each sport has **display views** (read-only, meant to be shown on a screen at
the field) and **operator views** (interactive, used by people running the
game).

**Football (`football.html`)**
| Tab | Purpose |
|-----|---------|
| Display | Big-score TV scoreboard with clocks, possession, NRZ, PAT |
| Box Score | Half-by-half table with live active-half score, clocks |
| Game Clock | Fullscreen Orbitron game clock |
| Play Clock | Fullscreen Orbitron play clock |
| Control | Scorekeeper: scoring, PAT, down/distance, timeouts, half, clocks with set/reset, half-score correction, OT, team names |
| Ref | Field referee: dual clock cards (start/stop), downs, possession, PAT |

**Baseball (`baseball.html`)**
| Tab | Purpose |
|-----|---------|
| Scoreboard | Manual Fenway-style inning-by-inning scoreboard (display, field-appropriate) |
| Modern | Digital inning-by-inning table with R/H/E columns, BSO indicators, base diamond |
| Ump | Field ump: pitch calls (B/S/Out), score +1/−1, bases, change sides, hit/stat buttons |
| Control | Scorekeeper: score correction, inning nav (add/remove/jump), BSO display style (Modern View), team names, game status |

Baseball index cards link to both `?view=scoreboard` and `?view=modern` plus Ump and Control.

---

## Git Conventions

- **Never include Claude session URLs in commit messages.** Not in the body,
  not as a footer, never. This is a hard rule.
- Commit messages: imperative mood, present tense, concise subject line.
- Branch for this Claude agent: `claude/remove-claude-links-VEdyO`
- Always push to that branch: `git push -u origin claude/remove-claude-links-VEdyO`
