# Adding a New Sport to Many Board

This guide captures the patterns established by the football and baseball
implementations. Follow it to add a new sport consistently.

---

## Checklist

```
src/manyboard/
  models/{sport}.py          # DB model, Create schema, Read schema
  routers/{sport}.py         # All /api/{sport}/games/* endpoints
  static/{sport}.html        # Full scoreboard UI

tests/
  test_models/test_{sport}.py  # Model unit tests (defaults, enums, IDs)
  test_api/test_{sport}.py     # API integration tests (all endpoints)
```

Wire it up in two files:
- `src/manyboard/main.py` — import router and call `app.include_router`
- `src/manyboard/static/index.html` — add game cards with links to the sport's views

---

## 1. Model (`models/{sport}.py`)

### Required fields (every sport gets these)

```python
import uuid
from datetime import UTC, datetime
from sqlmodel import Field, SQLModel

def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

class MySportGame(SQLModel, table=True):
    __tablename__ = "mysport_games"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    home_team: str = Field(default="Home")
    away_team: str = Field(default="Away")
    status: str = Field(default="active")   # "active" | "final" | any string
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    # ... sport-specific fields below
```

### Enums

Use `StrEnum` (Python 3.11+) for all string-valued enums. Use `int, Enum` for
integer-valued ones (like downs). No `.values()` needed with `StrEnum`.

```python
from enum import StrEnum

class MySportHalf(StrEnum):
    FIRST = "first"
    SECOND = "second"
    FINAL = "final"
```

### Storing complex state as JSON

When a field is a list or dict (e.g. per-period scores, a lineup), store it as
a JSON string column and expose it as a parsed type in the Read schema:

```python
import json

def _default_period_scores() -> str:
    return json.dumps({"away": [None, None], "home": [None, None]})

class MySportGame(SQLModel, table=True):
    ...
    period_scores_json: str = Field(default_factory=_default_period_scores)
```

Parse/serialize in the router helpers, not in the model. Never expose raw
`_json` fields in the Read schema.

### Three schemas

| Schema | Purpose |
|--------|---------|
| `MySportGame` | DB table — raw storage, JSON blobs, `table=True` |
| `MySportGameCreate` | POST body — only fields the caller sets at creation |
| `MySportGameRead` | All responses — replaces JSON blobs with parsed types, adds computed fields |

```python
class MySportGameCreate(SQLModel):
    home_team: str = "Home"
    away_team: str = "Away"
    # only creation-time options

class MySportGameRead(SQLModel):
    id: str
    home_team: str
    away_team: str
    status: str
    # parsed/computed fields instead of *_json raw strings
    created_at: datetime
    updated_at: datetime
```

---

## 2. Router (`routers/{sport}.py`)

### Boilerplate helpers (copy these verbatim, change type names)

```python
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from manyboard.database import get_session
from manyboard.models.mysport import MySportGame, MySportGameCreate, MySportGameRead

router = APIRouter(prefix="/api/mysport/games", tags=["mysport"])
SessionDep = Annotated[Session, Depends(get_session)]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_game(game_id: str, session: Session) -> MySportGame:
    game = session.get(MySportGame, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _save(game: MySportGame, session: Session) -> MySportGame:
    game.updated_at = _now()
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def _to_read(game: MySportGame) -> MySportGameRead:
    # build and return MySportGameRead from game fields
    # parse any JSON blobs here; compute derived fields (totals, elapsed clocks)
    ...
```

### Standard CRUD endpoints (every sport gets all four)

```python
@router.post("", status_code=201)
def create_game(data: MySportGameCreate, session: SessionDep) -> MySportGameRead:
    game = MySportGame(home_team=data.home_team, away_team=data.away_team)
    session.add(game)
    session.commit()
    session.refresh(game)
    return _to_read(game)

@router.get("")
def list_games(session: SessionDep) -> list[MySportGameRead]:
    return [_to_read(g) for g in session.exec(select(MySportGame)).all()]

@router.get("/{game_id}")
def get_game(game_id: str, session: SessionDep) -> MySportGameRead:
    return _to_read(_get_game(game_id, session))

@router.delete("/{game_id}", status_code=204)
def delete_game(game_id: str, session: SessionDep) -> None:
    game = _get_game(game_id, session)
    session.delete(game)
    session.commit()
```

### PATCH endpoints (one per state mutation)

Every PATCH follows the same shape:

```python
class SomeUpdate(BaseModel):
    field: SomeType

@router.patch("/{game_id}/some-action")
def some_action(game_id: str, update: SomeUpdate, session: SessionDep) -> MySportGameRead:
    game = _get_game(game_id, session)
    # mutate game fields
    return _to_read(_save(game, session))
```

Rules:
- One endpoint per logical action, not per field.
- Use `HTTPException(400)` for invalid game-state transitions (e.g. score below zero, no timeouts left).
- Use `HTTPException(422)` for invalid input values (enum not recognized, out-of-range).
- Always return the full Read schema — client replaces its state from the response.

### Every sport should have at minimum

```
PATCH /{id}/score     — add/subtract score for a team
PATCH /{id}/teams     — update home/away team names
PATCH /{id}/status    — set game status string ("active" / "final")
```

### Default-arg pitfall (B008)

Don't call Pydantic models in function default args — ruff B008 will fail CI:

```python
# BAD
def my_endpoint(..., update: MyUpdate = MyUpdate()):

# GOOD — module-level singleton
_DEFAULT_UPDATE = MyUpdate()
def my_endpoint(..., update: MyUpdate = _DEFAULT_UPDATE):
```

---

## 3. Wiring up (`main.py`)

```python
from manyboard.routers import baseball, football, mysport   # add import

app.include_router(mysport.router)                          # add this line
```

The `lifespan` handler calls `SQLModel.metadata.create_all(engine)` which picks
up the new table automatically on first run.

**DB migration**: SQLite does not auto-migrate. If you add columns to an
existing table after first run, delete `manyboard.db` and restart.

---

## 4. Frontend (`static/{sport}.html`)

### File structure

One self-contained HTML file. No build step. Inline `<style>` and `<script>`.
Copy the header/theme/connection boilerplate from an existing sport's file and
update `GAME_URL` and the API prefix.

### Required boilerplate (every sport page)

**Theme** — copy the `:root` + `[data-theme]` blocks verbatim from an existing
page. Don't change the variable names.

**Header** — logo link, score summary, tab nav, theme `<select>`, connection badge:

```html
<header>
  <a href="/" class="brand">MANY BOARD</a>
  <span class="header-score" id="header-score"></span>
  <nav class="view-tabs">
    <button class="tab-btn" id="tab-display" onclick="switchView('display')">Display</button>
    <!-- more tabs -->
  </nav>
  <select id="theme-select" class="theme-select" onchange="applyTheme(this.value)">
    <option value="default">Default</option>
    <option value="stadium">Stadium</option>
    <option value="field">Field</option>
  </select>
  <span id="conn-status" class="conn-status connected">
    <span class="conn-dot"></span>Connected
  </span>
</header>
```

**Core JS scaffold**:

```javascript
const params = new URLSearchParams(window.location.search);
const gameId = params.get('game');
let view  = params.get('view') || 'display';
let state = null;
let failCount = 0;

// Theme
function applyTheme(t) {
  if (t === 'default') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('mbTheme', t);
  const sel = document.getElementById('theme-select');
  if (sel) sel.value = t;
}
(function() { applyTheme(localStorage.getItem('mbTheme') || 'default'); })();

if (!gameId) { window.location.href = '/'; }

// View switching — stores current view in URL param so refresh restores it
function switchView(v) {
  view = v;
  const url = new URL(window.location);
  url.searchParams.set('view', v);
  history.replaceState(null, '', url);
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.getElementById('view-' + v).classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + v).classList.add('active');
  if (state) render();
}

// Connection status
function setConnStatus(ok) {
  const el = document.getElementById('conn-status');
  if (!el) return;
  if (ok) {
    el.className = 'conn-status connected';
    el.innerHTML = '<span class="conn-dot"></span>Connected';
  } else {
    el.className = 'conn-status lost';
    el.innerHTML = '<span class="conn-dot"></span>Signal Lost';
  }
}

// Polling — 200ms; failCount tracks consecutive failures
async function poll() {
  try {
    const resp = await fetch('/api/mysport/games/' + gameId);
    if (!resp.ok) { failCount++; if (failCount >= 3) setConnStatus(false); return; }
    state = await resp.json();
    failCount = 0;
    setConnStatus(true);
    render();
  } catch (e) { failCount++; if (failCount >= 3) setConnStatus(false); }
}

// Render dispatch — call per-view renderers
function render() {
  if (!state) return;
  renderHeader();
  if      (view === 'display') renderDisplay();
  else if (view === 'control') renderControl();
  // ...
}

// PATCH helper — fires request, updates state from response, re-renders
async function api(endpoint, body = null) {
  const opts = { method: 'PATCH' };
  if (body !== null) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(`/api/mysport/games/${gameId}/${endpoint}`, opts);
  if (resp.ok) { state = await resp.json(); render(); }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// Boot
switchView(view);
poll();
setInterval(poll, 200);
```

### View design principles

**Display views** (read-only, shown at the field on a phone/tablet):
- Use `clamp(min, preferred, max)` with `vh`-based preferred values for all
  font sizes and spacing. `vh` scales better than `vw` on portrait phones.
  Example: `font-size: clamp(130px, 30vh, 200px)` for a large score.
- Use `font-family: 'Orbitron', monospace` (loaded from Google Fonts) for
  numeric displays — clocks, scores.
- No interactive controls.

**Operator views** (Control, Ref, Ump — used by the people running the game):
- Standard font sizes; no clamping needed.
- Scrollable (`overflow-y: auto`).
- Keep actions grouped by concern with `.ctrl-section` / `.ctrl-header`.

**View split per sport** (establish this for any new sport):

| Tab | Type | Audience |
|-----|------|---------|
| Display | display | Spectators / field screen |
| Box Score | display | Spectators / field screen |
| Control | operator | Scorekeeper (admin, score correction, settings) |
| Ref / Ump | operator | On-field official (fast actions only) |

The Ref/Ump view should show **only what an on-field official needs in the
moment** — not score correction, team names, or settings. Those go in Control.

### CSS custom properties (do not rename these)

```css
:root {
  --bg, --panel, --border, --border-mid, --border-dark,
  --input-bg, --accent, --accent-dark,
  --text, --text-dim, --text-dimmer, --text-bright,
  --highlight
}
```

Override for `[data-theme="stadium"]` and `[data-theme="field"]`. Copy the
blocks from an existing page; only adjust values, not property names.

Sport-semantic colors are **hardcoded** (not themed):
- Ball/pitch: `#3498db`
- Strike/foul: `#f39c12`
- Out/penalty: `var(--accent)` (already themed)
- Connected: `#2ecc71`

---

## 5. Index page (`static/index.html`)

Add a card section for the new sport. Each card shows active games and a
"New Game" button. Links should point to `/{sport}.html?game={id}&view=display`
(or whatever the primary display view is called). Include links to all relevant
operator views (Control, Ref/Ump) on each card.

---

## 6. Tests

### Model tests (`tests/test_models/test_{sport}.py`)

```python
def test_{sport}_game_defaults() -> None:
    game = MySportGame(home_team="A", away_team="B")
    assert game.home_team == "A"
    assert game.status == "active"
    # check every field default

def test_{sport}_game_has_id() -> None:
    game = MySportGame(home_team="A", away_team="B")
    assert game.id is not None and len(game.id) > 0

def test_two_games_have_different_ids() -> None:
    assert MySportGame(home_team="A", away_team="B").id != \
           MySportGame(home_team="C", away_team="D").id

def test_enum_values() -> None:
    assert MySportHalf.FIRST == "first"
    # one test per enum
```

### API tests (`tests/test_api/test_{sport}.py`)

Use the shared `client` fixture from `tests/conftest.py` (in-memory SQLite,
automatically wired to the app).

```python
def _new_game(client: TestClient, **kwargs: object) -> str:
    payload: dict[str, object] = {"home_team": "Eagles", "away_team": "Ravens", **kwargs}
    return client.post("/api/mysport/games", json=payload).json()["id"]
```

Required test coverage:
- `POST /` — defaults, custom fields, 201 status, no raw `_json` fields in response
- `GET /{id}` — 200 with correct id, 404 for unknown id
- `GET /` — returns list with at least the created games
- `DELETE /{id}` — 204, subsequent GET is 404; 404 for unknown id
- Every PATCH endpoint:
  - Happy path: correct state change reflected in response
  - Error cases: invalid input → 422, invalid game state → 400
  - Floor/ceiling enforcement (scores can't go below zero, etc.)
- Status: default is `"active"`, can be set to `"final"`

---

## 7. Clock endpoints (if the sport has a timer)

Follow the football pattern exactly:

- Store `{clock}_default`, `{clock}` (remaining seconds), `{clock}_running` (bool),
  and `{clock}_started_at` (nullable datetime) in the DB model.
- Compute remaining seconds server-side on every GET using
  `max(0, stored - int(elapsed))`. Never rely on client-side timers.
- Expose `{clock}_running` and the computed `{clock}` in the Read schema;
  never expose `{clock}_started_at`.
- Endpoints: `/start`, `/stop`, `/reset`, and optionally `/set` (seconds) and
  `/default` (change reset duration).
- Reject `/start` when clock is at zero (400).

See `routers/football.py` → `_computed_game_clock` / `_computed_play_clock`
for the reference implementation.
