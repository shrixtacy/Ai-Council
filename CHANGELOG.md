# Changelog

All notable changes to AI Council Orchestrator are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - Unreleased (Current HEAD)

### Added
- Context-aware fallback model selection — fallback now considers failure type (rate limit, content filter, reasoning failure) when picking the next model (#144)
- Distributed locking for circuit breakers using Redis — prevents race conditions in multi-worker deployments (#136)
- Chat History page with full API integration (#135)
- Real analytics data wired to frontend with enhanced visualizations (#140)

### Fixed
- WebSocket endpoint now has authentication and rate limiting (#137)
- CostOptimizer in-memory cache now persists correctly across calls (#134)
- Session handling edge cases resolved (#120)

---

## [1.2.0] - February 2025

### Added
- Redis MQ Execution Agent and Worker System — async task queue for model execution (#118)
- Live Orchestration Visualizer — real-time pipeline stage visualization in the frontend (#87)
- Full async pipeline rewrite — entire orchestration pipeline is now fully async (#111)
- Rate limiting feedback — users now see rate limit status and wait times in the UI (#112)
- Web app testing suite and CI setup (#101)
- Complete password reset flow (email-based OTP) (#102)

### Fixed
- Authentication bypass vulnerability patched (#113)
- Real-time chat API wired correctly with request race guard (#116)
- Hardcoded timeouts refactored to config-driven values (#115)
- Removed fragile `sys.path.insert` usages in web backend (#110)
- Hardcoded email credentials removed from source code (#98)
- `process_request` refactored for correctness and clarity (#107)
- Request timeout enforced at the `AICouncil` level (#100)
- Structured logging standardized across all components (#119)

### Security
- CORS configuration hardened (#57)
- Environment variable validation enforced at startup (#63)
- WebSocket authentication added (#137)

---

## [1.1.0] - January 2025

### Added
- Full-stack authentication system — register, login, JWT sessions, MongoDB user storage (#65, #77)
- Dark mode, query history, and keyboard shortcuts in the web UI (#36)
- Mode comparison example (#35)
- Enhanced error handling in `process_request` (#88)
- Loading states and error handling in the frontend (#99)
- CLI refactored into `CLIHandler` class (#84)
- Space Grotesk and Inter fonts added to UI (#103)
- Contributors section added to README (#109)

### Fixed
- Backend dependency on core package resolved (#59)
- Model timeouts and capabilities aligned in example config (#58)
- Frontend served correctly via `http.server` on startup (#56)
- Gemini model versions corrected (2.5 → 1.5) across config (#55)
- Broken emoji and markdown typos in docs (#45)

### Infrastructure
- GitHub Actions workflows for issue assignment and PR-issue linking (#64, #47)
- CI badges added to README (#27)
- Cross-platform publish script with Windows fixes (#79)

---

## [1.0.0] - December 26, 2024

Initial release on PyPI as `ai-council-orchestrator`.

### Core Engine
- 5-layer orchestration pipeline: Analysis → Routing → Execution → Arbitration → Synthesis
- Three execution modes: FAST, BALANCED, BEST_QUALITY
- `AICouncilFactory` for dependency injection
- YAML-based configuration system

### Analysis Layer
- Rule-based intent classification (question, instruction, analysis, creation, modification, verification)
- Complexity scoring (trivial → very complex)
- Task type classification (reasoning, code generation, research, fact-checking, etc.)

### Routing Layer
- `ModelRegistry` with capability, cost, and performance profiles per model
- `ModelContextProtocol` for scored model selection
- Fallback chain pre-building at routing time
- Routing decision cache

### Execution Layer
- `BaseExecutionAgent` with retry and exponential backoff
- Per-provider rate limiting (OpenAI, Anthropic, default)
- Adaptive timeout management
- Circuit breakers per model
- `SelfAssessment` generation per response (confidence, assumptions, risk, cost, tokens)

### Arbitration Layer
- Conflict detection between multiple model responses
- Confidence-based resolution
- Quality threshold filtering

### Synthesis Layer
- Redundancy removal across validated responses
- Content combination and normalization
- Execution metadata attachment (models used, cost breakdown, execution path)

### Cost Optimizer
- Mode-based weighting (cost / speed / quality / reliability)
- Per-model performance history tracking
- Cost estimation with task-type multipliers
- Disk-cached optimization results (24h TTL)

### Resilience
- Circuit breakers on every pipeline component with independent thresholds
- Graceful degradation on partial failures (>50% subtask failure threshold)
- Failure isolation for repeatedly failing models

### Web Application
- React 18 frontend with Tailwind CSS, Zustand, Recharts, Framer Motion
- FastAPI backend with REST + WebSocket
- Express + MongoDB auth service with JWT and email-based password reset

### Real Model Adapters
- OpenAI, Anthropic, Google (Gemini), xAI (Grok), Groq — via raw `httpx`
- Mock models for development and testing

### Infrastructure
- Structured logging via `structlog`
- 95 tests, 45% code coverage
- Full type hints throughout
- Both sync and async APIs

---

## Tags Reference

| Tag | Date | Description |
|-----|------|-------------|
| `v1.0.0` | Dec 26, 2024 | Official PyPI release |
| `v1.0.0-backend` | Feb 2025 | Backend milestone complete |
| `v1.0.0-frontend` | Feb 2025 | Frontend milestone complete |
| `v1.3.0` | Current | See above |
