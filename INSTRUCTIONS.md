# 📖 AI Council - System Instructions & Principles

This document provides a brief overview of the project's architecture, file structure, and the working principles of each major component.

## 🏗️ Core Architecture
AI Council is built on a **5-layer orchestration pipeline** that transforms raw user intent into high-quality, validated AI responses.

1.  **🎯 Analysis Layer**: Decomposes user requests into atomic subtasks and assigns complexity scores.
2.  **🗺️ Routing Layer**: Selects the optimal AI models for each subtask based on capabilities, cost, and latency.
3.  **⚡ Execution Layer**: Manages parallel model calls with retries, circuit breakers, and self-assessment.
4.  **⚖️ Arbitration Layer**: Detects conflicts between model outputs and resolves them via confidence weighting.
5.  **🔄 Synthesis Layer**: Aggregates validated outputs into a coherent final response with metadata.

---

## 📁 File Structure & Working Principles

### 📂 Root Directory
- `ai_council/`: The primary Python package containing the core orchestration engine.
- `web_app/`: Full-stack application (FastAPI + React) for interactive model orchestration.
- `pyproject.toml`: Project metadata, dependencies, and build configuration for PyPI.
- `CHANGELOG.md`: Detailed history of all versions and unreleased features.
- `CONTRIBUTING.md`: Guidelines for setting up the environment and submitting PRs.

### 📂 `ai_council/` (Core Engine)
- `main.py`: Entry point for the `AICouncil` class; coordinates the 5-layer pipeline.
- `factory.py`: Implements the Dependency Injection (DI) pattern for easy system initialization.
- `core/models.py`: Defines the foundational data schemas (Task, Subtask, SelfAssessment, etc.).
- `analysis/`: Contains intent classifiers and task decomposers.
- `routing/`: Houses the `ModelRegistry` and cost-aware routing logic.
- `execution/`: Implements model adapters (OpenAI, Anthropic, Gemini) and resilience patterns.
- `arbitration/`: Logic for detecting contradictions and quality threshold filtering.
- `synthesis/`: Utilities for merging multi-model responses into a single output.
- `worker/`: (v1.2.0+) Redis MQ based worker system for asynchronous task execution.

### 📂 `web_app/` (Web Application)
- `backend/`: FastAPI server providing REST and WebSocket endpoints for the engine.
- `auth-backend/`: Express/Node.js service managing user authentication and MongoDB sessions.
- `frontend-react/`: Modern React dashboard for real-time orchestration monitoring.
- `start.sh` / `start.bat`: Convenience scripts to launch the entire stack locally.

### 📂 `scripts/` & `examples/`
- `scripts/`: Internal utility scripts for infrastructure validation and PyPI publishing.
- `examples/`: Guided demonstrations of basic usage, orchestration features, and custom configs.

---

## 🚀 Key Operational Principles

- **Specialization over Generality**: The system treats AI models as specialized tools rather than general-purpose oracles.
- **Resilience by Design**: Every external API call is protected by circuit breakers and fallback chains.
- **Explainability**: Every response includes metadata about which models were used and why they were chosen.
- **Cost-Quality Balance**: Users can toggle between `FAST`, `BALANCED`, and `BEST_QUALITY` modes to optimize for their specific constraints.
