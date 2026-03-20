# Governed Shared Memory for Multi-Agent AI

A memory system for multi-agent AI where agents propose, a gatekeeper approves, and memory stays clean. Free-form agent writes lose to governed mutation.

## The Problem

Multi-agent systems fail not because they lack storage—they fail because they lack **governed memory mutation**. When agents write directly to shared memory:

- ❌ Stale facts don't get updated; newer contradictions go unresolved
- ❌ Duplicates accumulate; agents can't distinguish valid from obsolete
- ❌ No audit trail; impossible to debug which agent corrupted state
- ❌ Free-form text is noisy; retrieval is unreliable

## The Solution

Agents **propose** memory, a Claude gatekeeper **filters + normalizes** it, and a **deterministic reducer** compiles it into clean canonical state.

```
agent proposes → gatekeeper validates → append-only log → reducer → agents read clean state
```

Five core pieces:

1. **Candidate ingress**: Agents emit `MemoryWriteCandidate` (not direct writes)
2. **LLM gatekeeper**: Claude decides accept/reject, normalizes into structured `MemoryEvent`
3. **Append-only log**: Immutable JSONL event store (source of truth)
4. **Deterministic reducer**: Replays events → produces canonical state (no LLM in reducer)
5. **Memory reader**: Agents query from projected state, not free-form text

## How It Works

### Write Path
```python
# 1. Agent proposes memory
candidate = CandidateMemoryEvent(
    agent_id="planner",
    content="Use dataset B instead of A",
    confidence=0.91,
    scope="benchmark_plan_4"
)

# 2. Gatekeeper normalizes
decision = gatekeeper.compile(candidate)
# → accept + extract: event_type, entity_id, upsert_key, payload

# 3. Event appended to log
event_log.append(decision)

# 4. Reducer computes state
canonical_state = reducer.reduce(event_log.read_all())
```

### Read Path
```python
# Agents read from projected state, not chat history
facts = memory_reader.get_facts(entity_id="benchmark_plan_4")
issues = memory_reader.get_active_issues(entity_id="benchmark_run_7")
decisions = memory_reader.get_decision_history(entity_id="project_1")
```

## Key Features

- **Governed writes**: Gatekeeper enforces schema, rejects noise
- **Transparent mutations**: Every state change is auditable (provenance tracked)
- **Conflict handling**: Detects contradictions, marks them, preserves history
- **Deterministic state**: Same events always produce same canonical state
- **No LLM in reducer**: Fast, consistent, rule-based state computation
- **Structured retrieval**: Agents query by entity/topic, not embeddings alone
- **Provenance tracking**: Every memory item links to source events


## Architecture

```
┌─────────────┐
│   Agents    │  propose memory (not direct writes)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Candidate Ingress   │  queue proposals
└──────┬──────────────┘
       │
       ▼
┌──────────────────────┐
│ LLM Gatekeeper      │  validate + normalize
│ (Claude Sonnet)     │  → MemoryEvent
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Append-Only Log      │  immutable event store
│ (JSONL)              │  source of truth
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Deterministic        │  replay events
│ Reducer              │  → canonical state
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Projected State      │  issues, facts, decisions,
│ (JSON snapshot)      │  constraints, results
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Memory Reader        │  agents query here
└──────────────────────┘
```

## Schema

### Entity Types
- `project`, `task`, `benchmark_run`, `experiment`, `code_artifact`, `hypothesis`

### Event Types
- `fact_asserted` — store a fact
- `issue_observed` — flag a problem
- `issue_resolved` — close an issue
- `decision_made` — record a choice
- `constraint_added` / `constraint_removed` — manage constraints
- `result_logged` — append experiment result

### Canonical State
```json
{
  "facts": {
    "entity_id:topic": {
      "value": "...",
      "confidence": 0.92,
      "provenance": ["mem_001", "mem_042"],
      "history": ["mem_001"],
      "last_updated_at": "2026-03-21T10:00:00Z"
    }
  },
  "issues": { "entity_id:issue_key": { "status": "open", ... } },
  "decisions": { ... },
  "constraints": { ... },
  "results": { ... }
}
```

## Future Work

- Semantic search over provenance events
- Time-travel queries (state at any point in history)
- Conflict resolution strategies (voting, expert override)
- Integration with tool use (agents emit memory from function results)
- Multi-user authorization (who can write to which entities)


## License

Apache 2.0
.