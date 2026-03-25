# Architecture

This document explains the current architecture of the Governed Memory Layer.
The system is built to answer one question safely:

How does an agent turn private notes into durable shared memory without letting
noise, ambiguity, or malformed writes corrupt canonical state?

## System Overview

At a high level, the system has four layers:

1. Private note capture
2. Governed promotion
3. Durable storage and canonical projection
4. Evaluation and benchmarking

The flow is:

```text
Agent
  -> WorkingMemory
  -> PromotionPipeline
       -> Interpreter
       -> Resolver
       -> Validator
       -> Inputter
            -> events_memory
            -> shared_* tables
            -> pending_memory_events
  -> SharedMemory reads
```

## Core Design Principles

- Agents never write shared memory directly.
- Canonical state is separate from raw private notes.
- Every committed canonical write is also recorded in an append-only ledger.
- Ambiguous lifecycle references are preserved instead of guessed.
- Canonical shared tables are deterministic projections, not free-form agent output.
- Benchmarks score final shared state, not just model text quality.

## Main Components

### WorkingMemory

`memory/working_memory.py`

This is the private note buffer for one agent during one run.

What it does:

- stores timestamped natural-language notes
- distinguishes agent notes from tool-result notes
- tracks which notes have already been processed by promotion

What it does not do:

- enforce schema
- resolve identity
- write shared memory

It is intentionally cheap and private.

### PromotionPipeline

`memory/promotion.py`

This is the orchestration layer. It processes notes one at a time.

Current flow per note:

1. build fresh canonical context
2. interpret the note into a proposed write
3. resolve whether the write safely binds to an existing entity, creates a new one, or must remain provisional
4. validate the resolved write
5. commit it to the ledger and canonical tables, or enqueue it in pending memory

It also retries pending writes after successful canonical commits, because a new
write can make an earlier ambiguous reference resolvable.

### Interpreter

`memory/interpreter.py`

The interpreter decides whether a note should become shared memory at all.

Input:

- one note
- current canonical context:
  - open issues
  - active constraints
  - active decisions

Output:

- reject, or
- a structured `WriteRequest`

Buckets:

- `plan`
- `constraints`
- `issues`
- `decisions`
- `results`
- `task_state`
- `learnings`

The interpreter has two modes:

- deterministic heuristics for very explicit notes
- LLM-based interpretation for the harder cases

Heuristics are intentionally narrow and are most useful for:

- `Constraint: ...`
- `Decision: ...`
- `Learning: ...`
- direct task-state phrases
- exact lifecycle notes containing one explicit canonical slug

### Resolver

`memory/resolver.py`

The resolver is the identity and lifecycle policy layer.

This is one of the most important parts of the current system.

The interpreter says what a note appears to mean.
The resolver decides whether that meaning can safely mutate canonical state.

For `issues`, `constraints`, and `decisions`, the resolver can:

- bind to an existing canonical entity
- create a new canonical entity
- keep the write provisional if the reference is too ambiguous

This is where the system handles things like:

- "that earlier blocker"
- "the earlier migration freeze"
- "the old nightly warmup choice"

The resolver uses:

- explicit target IDs from the write request
- explicit slugs mentioned in the note
- token overlap with candidate rows
- alias/reference memory stored on canonical rows

It returns a `ResolvedWrite`:

- `commit`
- `provisional`
- `reject`

### Validator

`memory/validator.py`

The validator enforces structural safety before canonical mutation.

It checks:

- valid bucket
- valid operation for that bucket
- non-empty target ID
- required payload fields
- lifecycle targets exist in the current canonical context when needed

It is not an LLM.
It is deterministic and rejects malformed or unsafe writes.

### Inputter

`memory/inputter.py`

The inputter is the only official write path to storage.

It has three write modes:

- `write`: raw write request to ledger plus projector
- `write_resolved`: resolved canonical write
- `write_provisional`: store unresolved work in pending memory

The important invariant is:

- committed canonical writes always go through the ledger first

### SharedMemoryWriter

`memory/shared_memory_writer.py`

This is the deterministic projector.

It converts validated events into updates on the canonical tables:

- `shared_plan`
- `shared_constraints`
- `shared_issues`
- `shared_decisions`
- `shared_results`
- `shared_task_state`
- `shared_learnings`

It also maintains reference memory for some entity buckets so the resolver can
reconnect later paraphrases to earlier canonical rows.

Reference memory currently exists for:

- constraints
- issues
- decisions

It stores things like:

- canonical text
- aliases
- reference phrases
- seen referring expressions

### PendingMemoryQueue

`memory/pending_memory.py`

This is the queue for ambiguous writes that matter but are not yet safe to commit.

Typical example:

- the agent says "the earlier blocker is fixed"
- but there is no safely identifiable canonical blocker yet

Instead of guessing, the system stores a provisional pending event.

Later, once canonical state changes, the pipeline retries pending items.

Possible statuses include:

- `open`
- `on_hold`
- `committed`
- `rejected`

### SharedMemory

`memory/shared_memory.py`

This is the read API for the rest of the system.

Agents and benchmark code read from here, not from raw SQL directly.

It exposes:

- active constraints
- open issues
- decisions by status
- task state
- results
- learnings
- event history
- pending events
- a full `snapshot()` for debugging and benchmarking

## Storage Model

### Ledger

`events_memory`

This is the append-only source of truth for committed canonical writes.

Every committed write includes:

- event ID
- timestamp
- source agent
- bucket
- target ID
- operation
- payload JSON
- raw input
- source reference
- projection success flag

### Pending Queue

`pending_memory_events`

This stores unresolved-but-important writes that are waiting for replay.

It preserves:

- raw input
- intended operation
- target ID
- reference text
- payload
- candidate matches
- original request JSON
- retry state

### Canonical Tables

These are the actual shared state that agents are supposed to read:

- `shared_plan`
- `shared_constraints`
- `shared_issues`
- `shared_decisions`
- `shared_results`
- `shared_task_state`
- `shared_learnings`

## Operational Semantics By Bucket

### Plan

- one canonical row, usually `main`
- `upsert`
- version increments on replacement

### Constraints

- active or invalidated
- created via `upsert`
- ended via `invalidate`

### Issues

- open or resolved
- created via `upsert`
- closed via `resolve`

### Decisions

- active or superseded
- created via `append`
- ended via `invalidate` which projects to `superseded`

### Results

- append-only
- multiple results can coexist

### Task State

- latest state wins
- common states: `pending`, `in_progress`, `blocked`, `done`, `failed`

### Learnings

- append-only active knowledge

## Where The Hard Problems Are

The easiest part of the system is schema validation.
The hardest part is identity continuity across time.

Current reliability bottlenecks are mostly in:

- paraphrased lifecycle references
- binding indirect later notes back to the right earlier entity
- replaying provisional lifecycle notes once enough canonical context exists

Examples of hard references:

- "that earlier blocker"
- "the old freeze"
- "the previous warmup choice"
- "the earlier class-weight decision"

## Benchmark Architecture

The benchmark system lives in `agent_memory/benchmarks/`.

Important files:

- `benchmarks/harness.py`
- `benchmarks/scorer.py`
- `benchmarks/run.py`
- `benchmarks/trajectories/`

### What A Benchmark Trajectory Is

A trajectory is:

- an ordered list of notes
- expected canonical outcomes
- forbidden outcomes
- optional fault-injection config

The benchmark does not just score raw text output.
It scores the final shared-memory snapshot.

### What The Benchmark Measures

The families cover:

- promotion filtering
- lifecycle transitions
- duplicate avoidance
- conflict handling
- cross-bucket coherence
- replay/projection robustness

### Systems Compared

The runner can compare:

- governed system
- append-all baseline
- no-shared-context baseline

### Scoring

The scorer measures:

- canonical accuracy
- governance accuracy
- false positives
- false negatives
- field mismatches
- surplus canonical rows
- pending backlog count
- replay health

Replay health is intentionally separate from canonical correctness so the system
can expose deferred resolution debt explicitly.

## Typical End-to-End Example

Example sequence:

1. Agent writes: `Constraint: do not ship new schema migrations while drift remains unresolved.`
2. Interpreter emits a constraints upsert
3. Resolver decides this is a new constraint
4. Validator approves it
5. Inputter writes an event to `events_memory`
6. Projector writes the canonical row to `shared_constraints`
7. Later note says: `The freeze_schema_migrations constraint no longer applies.`
8. Interpreter emits a constraints invalidate
9. Resolver binds that note back to the original canonical constraint
10. Validator checks that the target exists as an active constraint
11. Inputter records the lifecycle event
12. Projector marks the constraint invalidated

## When The Pending Queue Is Used

Example:

1. Agent writes: `The earlier blocker is fixed.`
2. Interpreter infers an issue resolution
3. Resolver cannot safely identify which open issue is meant
4. The note is preserved in `pending_memory_events`
5. Later a canonical issue appears
6. Pending replay retries the unresolved note
7. If resolution becomes safe, the system commits the canonical event

## What The README Leaves Out On Purpose

The README is intentionally short and reproducible.

This document is the place for:

- component-by-component explanation
- storage semantics
- lifecycle behavior
- resolver logic
- benchmark internals

If you are changing core system behavior, start here.
