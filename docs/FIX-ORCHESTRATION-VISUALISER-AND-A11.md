# Fix: Orchestration Visualizer Real Data + A11y + Backend Startup

## Summary
This change set addresses three practical issues encountered while implementing the “OrchestrationVisualizer should use real backend data” feature:

- The UI previously didn’t reliably surface orchestration metadata to the user.
- An accessibility audit reported: **“Buttons must have discernible text”** for icon-only buttons.
- Running the backend via `web_app/backend/main.py` failed with `ModuleNotFoundError: No module named 'structlog'`.

## Problem 1: Orchestration visualizer showed mock/empty data

### Root cause
The backend orchestration metadata (execution pipeline explainability fields) existed in the core models (`ExecutionMetadata`), but the web UI didn’t consistently bind that backend response data into a dedicated orchestration view.

### Fix
- **Backend**: ensured `/api/process` returns orchestration fields so the UI can render them.
- **Frontend**: added a dedicated `orchestrationData` state and a normalization function `parseOrchestrationData()` that maps:
  - `execution_path` → `executionPath`
  - `arbitration_decisions` → `arbitrationDecisions`
  - `synthesis_notes` → `synthesisNotes`

Why normalization is used:
- It keeps the template simple.
- It provides one stable place to adapt if the backend response changes.

### Files changed
- `web_app/backend/main.py`
- `web_app/frontend/index.html`

## Problem 2: Accessibility audit error (Buttons must have discernible text)

### Root cause
Some buttons contained only an icon (`<i class="...">`) and had no accessible name.
Many audit tools treat this as a failure unless the button has:
- visible text, or
- `aria-label`, or
- `title` (often not sufficient alone, but still useful).

### Fix
Added `aria-label` + `title` to icon-only buttons, including:
- Send message
- Close trade-off analysis modal
- Close keyboard shortcuts modal

### File changed
- `web_app/frontend/index.html`

## Problem 3: Backend startup error (structlog missing)

### Root cause
The core package declares `structlog` as a dependency in `pyproject.toml`, but `web_app/backend/requirements.txt` did not include it.
When running the backend directly (`python main.py`), the environment relied on `web_app/backend/requirements.txt`, so `structlog` was not installed.

### Fix
Added `structlog>=23.0.0` to:
- `web_app/backend/requirements.txt`

## How to test

### 1) Install backend dependencies
From `web_app/backend` with your venv activated:

```bash
pip install -r requirements.txt
```

### 2) Run backend
```bash
python main.py
```

Expected:
- Server starts and listens on `http://localhost:8000`

### 3) Confirm orchestration data is returned
Open a browser and call:

- `http://localhost:8000/api/status`

Then from the UI (open `web_app/frontend/index.html`), send a query.
In DevTools → Network, inspect the `/api/process` response and verify it includes:

- `execution_path` (array)
- `arbitration_decisions` (array)
- `synthesis_notes` (array)

### 4) Confirm UI renders orchestration
After a successful response, the Orchestration panel should show:
- Execution Path steps
- Arbitration decisions (if present)
- Synthesis notes (if present)

### 5) Confirm A11y fix
Re-run your accessibility audit (Lighthouse/axe). The icon-only button errors should be resolved.
