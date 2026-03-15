# AI Council — Product Document

**Project:** AI Council Orchestrator
**Current Version:** 1.3.0
**Last Stable PyPI Release:** 1.0.0 (December 26, 2024)
**PyPI:** `ai-council-orchestrator`

---

## What Was Built in v1.0.0

### Core Engine

A 5-layer orchestration pipeline that coordinates multiple AI models to produce a validated, synthesized final answer.

- **Analysis Layer** — Determines intent (question, instruction, analysis, creation, etc.), scores complexity, and classifies task types using rule-based keyword matching.
- **Routing Layer** — `ModelRegistry` holds all registered models with capabilities, cost profiles, and performance metrics. `ModelContextProtocol` scores candidates against each subtask's requirements and selects the best fit. Fallback chains are pre-built at routing time.
- **Execution Layer** — Fires subtasks at selected models with per-provider rate limiting, adaptive timeouts, retry with exponential backoff, and circuit breaker isolation per model. Each response includes a `SelfAssessment` (confidence score, assumptions, risk level, token usage, cost).
- **Arbitration Layer** — Detects logical conflicts between responses, compares confidence scores, resolves contradictions, and filters out responses below quality thresholds.
- **Synthesis Layer** — Deduplicates redundant content, combines validated responses, normalizes tone and structure, attaches execution metadata (models used, cost breakdown, execution path, arbitration decisions).

### Execution Modes

- **FAST** — Single best-fit model, no arbitration unless failure
- **BALANCED** — Primary model + optional second for high-risk subtasks
- **BEST_QUALITY** — Multiple models in parallel, arbitration always applied

### Cost Optimization

`CostOptimizer` scores every candidate model on cost, speed, and quality using mode-specific weights. Results are cached with a 24-hour TTL. Performance history is tracked per model and feeds back into future scoring.

### Resilience

Circuit breakers on every pipeline component with independent thresholds. Per-provider rate limiting. Adaptive timeouts. Graceful degradation when more than 50% of subtasks fail.

### Web Application

- React 18 frontend — Chat UI, basic auth flow
- FastAPI backend — REST + WebSocket, runs the core engine directly
- Express + MongoDB auth service — JWT sessions, chat history

### Real Model Adapters

OpenAI, Anthropic, Google (Gemini), xAI (Grok), Groq — all via raw `httpx`. Mock models for development and testing.

### Infrastructure

- YAML-based configuration
- Structured logging via `structlog`
- `AICouncilFactory` for dependency injection
- 95 tests, 45% code coverage

---

## What Changed in v1.1.0 – v1.3.0 (Current)

These are all the features and fixes that have landed on `master` since the v1.0.0 PyPI release but have not yet been published.

### Security
- WebSocket endpoint now requires authentication and has rate limiting
- Authentication bypass vulnerability patched
- CORS configuration hardened
- Hardcoded email credentials removed from source code
- Environment variable validation enforced at startup

### Core Engine
- Full async pipeline rewrite — entire orchestration pipeline is now properly async end-to-end
- Context-aware fallback model selection — fallback now considers the failure type (rate limit, content filter, reasoning failure) when picking the next model
- Distributed locking for circuit breakers via Redis — prevents race conditions in multi-worker deployments
- CostOptimizer in-memory cache persistence fixed
- Request timeout enforced at the `AICouncil` level
- Structured logging standardized across all components
- Hardcoded timeouts refactored to config-driven values

### Infrastructure
- Redis MQ Execution Agent and Worker System — async task queue for model execution
- Web app CI setup with test suite

### Web Application
- Live Orchestration Visualizer — real-time pipeline stage visualization
- Real analytics data wired to frontend with enhanced visualizations
- Chat History page with full API integration
- Complete password reset flow (email-based OTP)
- Full-stack authentication system (register, login, JWT, MongoDB)
- Rate limiting feedback shown in UI
- Dark mode, query history, keyboard shortcuts
- Session handling improvements
- Loading states and error handling
- UI typography improvements (Space Grotesk + Inter)

### Fixes
- Real-time chat API wired correctly with request race guard
- Removed fragile `sys.path.insert` usages in web backend
- `process_request` refactored for correctness
- Backend dependency on core package resolved
- Gemini model versions corrected across config

---

## What Is Still Incomplete Going into v2.0

These are known gaps that exist in the current codebase and need to be addressed.

1. **Analysis engine is rule-based** — Intent detection and complexity scoring use keyword regex matching. Misclassifies ambiguous or nuanced queries. No NLP or embedding-based classification.

2. **No real semantic conflict detection** — The arbitration layer compares confidence scores and detects surface-level contradictions. Two models can give factually different answers that pass current conflict detection if they don't share contradictory keywords.

3. **Plugin system is a placeholder** — The `plugins/` directory exists with a `.gitkeep`. No plugin loading, registration, or execution logic exists.

4. **Streaming is partial** — WebSocket endpoint exists but end-to-end token streaming from model APIs through to the frontend is not fully wired.

5. **Test coverage is low** — 45% coverage. Arbitration layer, synthesis layer, and routing logic have limited test coverage. No full pipeline integration tests.

6. **Performance history is not persisted** — `CostOptimizer` tracks per-model performance history in memory. Lost on every restart. Scoring bonuses for well-performing models never survive a deployment.

---

## Requirements for v2.0

### R1 — Semantic Conflict Detection

Replace surface-level contradiction detection in the arbitration layer with embedding-based semantic similarity. When two model responses are compared, compute their semantic similarity score. If similarity is below a configurable threshold, treat it as a conflict and trigger arbitration.

Confidence should increase when models semantically agree, not just when they don't contain obvious keyword contradictions.

Acceptance: two responses that say the same thing in different words are recognized as agreeing. Two responses that give factually different answers are flagged as conflicting even if they share no contradictory keywords.

---

### R2 — NLP-Based Analysis Engine

Replace the keyword regex analysis engine with an embedding or lightweight NLP classifier for intent classification and complexity scoring.

Options to evaluate: sentence-transformers for embedding-based classification, or a small fine-tuned classifier. Must not add significant latency to the pipeline.

Acceptance: intent classification accuracy improves on a held-out test set of ambiguous queries compared to the current regex baseline.

---

### R3 — Plugin System

Implement the plugin architecture. Plugins should be able to:
- Register custom AI model adapters
- Add custom routing rules
- Hook into the pipeline at defined extension points (pre-execution, post-arbitration, post-synthesis)

Loadable from the `plugins/` directory via a manifest file without modifying core code.

Acceptance: a third-party model can be integrated by dropping a plugin into `plugins/` and adding it to config, with no changes to the core codebase.

---

### R4 — End-to-End Token Streaming

Wire token streaming from model APIs through the WebSocket to the frontend. Users should see partial responses appearing progressively, especially important in BEST_QUALITY mode where wait times are longest.

Acceptance: in BEST_QUALITY mode, the user sees tokens streaming in real time rather than a blank screen followed by a complete answer.

---

### R5 — Persist Performance History

The `CostOptimizer` performance history must survive restarts. Persist to the existing Redis store so the optimizer resumes with historical data after a deployment.

Acceptance: after a restart, model scoring bonuses based on historical performance are preserved.

---

### R6 — Increase Test Coverage to 80%

Priority areas:
- Arbitration layer — conflict detection and resolution logic
- Synthesis layer — redundancy removal and content combination
- Routing layer — model scoring, fallback chain building, context-aware fallback selection
- Full pipeline integration tests — a request going through all 5 layers with mock model responses
- Failure scenario tests — circuit breaker trips, rate limit hits, model timeouts, fallback invocation

---

### R7 — PyPI Release of v1.3.0

Publish the current HEAD as v1.3.0 to PyPI. The gap between the last published version (1.0.0) and the current state of the codebase is significant — security fixes, async rewrite, Redis MQ, auth system, and analytics are all unreleased on PyPI.

Steps: update version in `pyproject.toml` (done — now 1.3.0), tag the release, run the publish script at `scripts/publish_to_pypi.py`.
