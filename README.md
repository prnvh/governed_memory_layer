# Governed Memory Layer 

A governed memory pipeline for multi-agent systems. Agents work in private working memory; a promotion pipeline decides what becomes shared canonical truth.

Shared memory is SQLite-backed with an append-only event ledger and bucketed canonical views. Agents never write shared memory directly — all writes flow through the pipeline.

---

## Architecture

```
Agent
  └─► Working Memory (per-agent, NL notes, run-scoped)
            │
            │  [end-of-step or tool-result trigger]
            ▼
       Interpreter (LLM)
            │  reject ──► dropped
            │  accept ──► { bucket, target, operation, payload }
            ▼
        Validator (schema check)
            │  invalid ──► dropped + logged
            │  valid
            ▼
         Inputter
            ├─► memory_events (append-only event ledger)
            └─► Projector ──► canonical view tables
                              (plan, issues, constraints,
                               decisions, results, task_state,
                               learnings)
                                    │
                                    ▼
                            Agents read from here
```

---

## Components

- **WorkingMemory** — per-agent, run-scoped NL note store. Private and ephemeral.
- **Interpreter** — LLM-based classifier. Decides whether a note warrants promotion and produces a structured write request.
- **Validator** — schema and rule checker. Rejects malformed or invalid write requests before any write happens.
- **Inputter** — the only writer. Appends to the event ledger and triggers the projector.
- **Projector** — updates canonical view tables deterministically from a validated event.
- **SharedMemory** — read API for canonical views. What agents query.
- **Promotion** — orchestrates the full pipeline: WorkingMemory → Interpreter → Validator → Inputter.

---

## Phases

- **Phase 1** — working pipeline: schema, connection, working memory, interpreter, validator, projector, inputter, shared memory, promotion.
- **Phase 2** — full domain coverage + validator rules for all buckets.
- **Phase 3** — promotion quality: interpreter prompt tuning, rejection rate tracking.
- **Phase 4** — provenance: full event history queryable per target.
- **Phase 5** — eval harness: benchmark trajectories, scorer, CLI runner.

---

## Hard Rules

- Agents never write to shared memory directly. Only the Inputter does.
- The event ledger (`memory_events`) is append-only. No updates or deletes.
- Agents read from canonical view tables, not the event ledger.
- Working memory is per-agent and run-scoped. It is not authoritative.
- Interpreter output must be validated before any write happens.

---

## Running Tests

```bash
# All fast tests (no API key needed):
pytest tests/ -m "not integration"

# Real API integration tests (requires ANTHROPIC_API_KEY):
pytest tests/test_integration_real_api.py -m integration
```

## Environment Variables

```
ANTHROPIC_API_KEY=...       # required for Interpreter and agents
AGENT_MEMORY_DB_PATH=...    # optional, defaults to agent_memory.db
AGENT_MEMORY_LOG_LEVEL=...  # optional: DEBUG|INFO|WARNING, defaults to INFO
```