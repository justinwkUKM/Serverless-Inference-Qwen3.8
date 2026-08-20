# Implementation Plan for Google ADK

## Summary

Restructure Quicksilver into two local services:

```text
Browser
  │ Existing /api/* + SSE contract
  ▼
Node BFF
  ├── Frontend/static assets
  ├── Chat CRUD and UI-facing SQLite
  ├── Metrics persistence
  └── Public SSE compatibility adapter
        │ Internal authenticated SSE
        ▼
Python Google ADK service
  ├── Quicksilver root agent
  ├── Persistent ADK sessions
  ├── Tavily search tool
  ├── Context-budget callback
  └── LiteLLM → Verda vLLM → Qwen3.8
```

Use Python because Google's current ADK tooling, templates, evaluations, and persistent database sessions are centered on Python. Verda remains the private model provider through ADK's [LiteLLM integration](https://adk.dev/agents/models/litellm/).

## Implementation Changes

### ADK agent service

- Create an `agent_service/` Python package managed with `uv` and pinned dependencies:
  - `google-adk[extensions]`
  - `litellm`
  - `aiosqlite`
  - `httpx`
  - `pydantic-settings`
  - ASGI server dependencies
- Define one `LlmAgent` named `quicksilver_agent` with:
  - Existing conversational system instructions.
  - `LiteLlm(model="openai/qwen3.8-27b")`.
  - Verda endpoint and inference key supplied only to the Python process.
  - Streaming enabled and thinking disabled by default.
- Add a toggle-gated Tavily function tool:
  - Unavailable when `web_search=false`.
  - Available for agent-selected invocation when enabled.
  - Returns structured title, URL, and excerpt fields.
  - Enforces result, content-length, timeout, and URL limits.
  - Treats search content as untrusted data.
- Use ADK `DatabaseSessionService` with `sqlite+aiosqlite:///data/adk_sessions.sqlite`.
  - `chat_id` becomes the ADK `session_id`.
  - Use `quicksilver-local` as the initial `user_id`.
  - Keep ADK tables separate from the current UI database.
- Add a `before_model_callback` context-budget guard:
  - Target the configured 32,768-token model context.
  - Reserve requested output tokens plus a 2,048-token safety margin.
  - Preserve system instructions, tool definitions, and newest user turn.
  - Remove oldest conversational events first.
  - Record included/omitted event counts in response metadata.
- Support ephemeral sessions when history is disabled:
  - Generate a request-scoped session.
  - Delete it after completion or cancellation.
  - Do not persist the request in Quicksilver's SQLite database.
- Expose internal endpoints:
  - `GET /healthz`: ADK process readiness plus authenticated Verda health.
  - `POST /internal/run`: SSE stream accepting session ID, current user content, attachments, generation settings, enabled tools, and request ID.
  - `DELETE /internal/runs/:request_id`: cancel an active agent run.
- Emit normalized internal events:
  - `run_started`
  - `tool_started` / `tool_finished`
  - `reasoning_delta`
  - `content_delta`
  - `usage`
  - `sources`
  - `context`
  - `completed`
  - `error`

### Node BFF and compatibility

- Preserve the existing public interfaces:
  - `POST /api/chat`
  - `GET /api/status`
  - Existing chat CRUD endpoints.
  - Existing browser-facing SSE fields.
- Replace direct Verda and Tavily calls in `server.mjs` with the internal ADK client.
- Send only the newest user turn to ADK for persisted chats; ADK sessions become the context authority.
- Translate ADK events into the current frontend stream:
  - Content and reasoning remain OpenAI-style deltas.
  - Sources retain the existing shape.
  - Usage, context metadata, and server phase metrics remain compatible.
  - Tool events may be added as optional fields that old frontend code safely ignores.
- Preserve current Node SQLite tables as the UI and metrics projection:
  - Continue storing user/assistant messages, titles, favorites, request status, TTFT, total duration, tokens, Tavily duration, errors, and metadata.
  - Use the shared request ID to correlate Node records with ADK events.
- Measure TTFT at two levels:
  - End-to-end visible TTFT in Node.
  - ADK/model/tool phase timings supplied through metadata.
- Propagate browser cancellation to the ADK cancellation endpoint and abort the active LiteLLM/Verda stream.
- Move `VERDA_INFERENCE_KEY`, `VERDA_ENDPOINT`, and `TAVILY_API_KEY` exclusively into the ADK service environment. Node receives only `ADK_SERVICE_URL` and an internal shared secret.

### Local development and restructuring

- Add separate commands:
  - `npm run dev:web` for Node.
  - `npm run dev:agent` for the Python ADK service through `uv`.
  - `npm run dev` to launch both with coordinated shutdown.
- Keep Terraform for the Verda inference deployment unchanged.
- Update `.env.example` with placeholders only and extend `.gitignore` for:
  - ADK session database files.
  - Python virtual environments and caches.
  - Local ADK artifacts and credentials.
- Document architecture, startup, environment variables, health checks, session behavior, cancellation, context management, Tavily credit policy, and failure recovery.
- Implement migration behind `AI_BACKEND=adk|legacy`, defaulting initially to `legacy`; switch to `adk` after compatibility tests pass, then remove the legacy path in a later cleanup.

## Testing and Acceptance

- Unit-test:
  - ADK agent configuration and LiteLLM Verda routing.
  - Tavily permission gating and prompt-injection boundaries.
  - Context truncation and newest-turn preservation.
  - ADK-to-public SSE event translation.
  - Usage and phase-metric calculations.
  - Ephemeral versus persistent session behavior.
- Integration-test with mocked Verda and Tavily:
  - Multi-turn contextual conversation.
  - Streaming content and reasoning.
  - Tool invocation and citations.
  - Image payload forwarding.
  - Cancellation and upstream disconnect.
  - Context overflow prevention.
  - Verda timeout, zero-replica, malformed stream, and tool failure.
- Run the existing 12 Node tests unchanged, then add contract tests proving the frontend receives the same SSE format.
- Acceptance criteria:
  - Existing frontend requires no breaking API changes.
  - Reopened chats maintain context through ADK sessions.
  - Web search never runs unless enabled.
  - No provider credentials reach the browser or Node public configuration.
  - Clicking Stop cancels the ADK and Verda work.
  - TTFT, throughput, tokens, sources, and per-message metrics remain available.
  - Legacy and ADK backends can be compared using identical benchmark prompts.

## Assumptions and Defaults

- Keep Verda Qwen3.8-27B as the only model; no Gemini fallback.
- Introduce ADK as a local Python sidecar before container or cloud deployment.
- ADK owns conversational context; Node owns frontend presentation and analytics.
- Preserve the current public API and SSE protocol exactly.
- Tavily is an agent tool, but the existing UI toggle remains the explicit permission boundary.
- Use a separate ADK SQLite database to avoid coupling application tables to ADK schema migrations, including the session-schema changes documented by [Google ADK sessions](https://adk.dev/sessions/session/).
