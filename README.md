# Governed Memory Layer

Governed Memory Layer is a SQLite-backed shared memory system for agents.
Agents write notes into private working memory first. A governed promotion
pipeline decides what becomes shared canonical state.

The short version:

- agents never write shared memory directly
- every committed write is recorded in an append-only ledger
- canonical shared tables are projected from validated writes
- ambiguous lifecycle writes can be held in a pending queue and replayed later
- a benchmark harness evaluates filtering, lifecycle transitions, identity
  resolution, coherence, and replay robustness

For the full system walkthrough, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Quick Start

From the repo root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd agent_memory
```

Set your API key:

```powershell
$env:OPENAI_API_KEY="your-key-here"
```

Or put it in a `.env` file:

```env
OPENAI_API_KEY=your-key-here
```

## Run Tests

Fast core test pass:

```powershell
python -m pytest tests\test_core_pipeline.py -q
```

## Run Benchmarks

Run one benchmark family against the governed system:

```powershell
python -m benchmarks.run --family b --system governed
```

Run all benchmark families:

```powershell
python -m benchmarks.run --system governed
```

Run governed vs baselines:

```powershell
python -m benchmarks.run --family a --system all
```

## Environment

- `OPENAI_API_KEY`: required for the live interpreter and benchmark runs
- `AGENT_MEMORY_DB_PATH`: optional persistent DB path
- `AGENT_MEMORY_LOG_LEVEL`: optional log level

## Repo Layout

- `agent_memory/memory/`: core memory system
- `agent_memory/benchmarks/`: benchmark harness, trajectories, scorer, runner
- `agent_memory/tests/`: local test suite
