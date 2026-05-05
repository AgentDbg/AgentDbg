# Roadmap

AgentDbg is a **local-first debugger for AI agents**. This roadmap reflects what's shipped, what's next, and what's on the horizon.

Guiding principle: every feature must make the debugging workflow faster and clearer. If it looks more like observability than debugging, it doesn't belong here.

---

## v0.1 (released 2026-02-28)

- `@trace` decorator + `record_llm_call` / `record_tool_call` / `record_state`
- Local JSONL storage with automatic redaction
- `agentdbg list`, `agentdbg view` (timeline UI), `agentdbg export`
- Loop detection (`LOOP_WARNING` events)
- LangChain / LangGraph callback handler


## v0.2 (released 2026-03-24)

**Theme: "The one that saves you money"**

- **Run guardrails** - opt-in `stop_on_loop`, `max_llm_calls`, `max_tool_calls`, `max_events`, `max_duration_s`. Your agent loops? It dies before burning your budget.
- **Live-refresh viewer** - `agentdbg view` stays running. New runs appear in the sidebar automatically. Events stream in real-time for running agents. No more restart-to-refresh.
- **OpenAI Agents SDK integration** - `pip install agentdbg[openai]`, import the processor, done. Maps generation spans, function calls, and handoffs to the AgentDbg timeline.
- **CrewAI integration** - hook-based adapter with automatic lifecycle management.
- **Run summary panel** - status badge, KPI chips (LLM calls, tool calls, errors, loop warnings), jump-to-first-error, jump-to-first-loop-warning.
- **Rename & delete runs** from the UI.

Everything from v0.1 still applies: local storage, automatic redaction, zero accounts, zero cloud.

---

## v0.3 (current)

**Theme: "What changed?"**

Candidates (prioritized by user feedback):

- **Run compare / diff** - select two runs, see what changed side-by-side: event sequence, prompt text, tool arguments, outcomes.
- **Enhanced loop detection categories** - distinguish single-step loops, alternating loops, error-retry loops, and "no progress" loops.
- **Prompt fingerprinting** - lightweight hash of prompt text per LLM call, enabling cross-run detection of prompt regressions.
- **Additional framework integrations** - LlamaIndex, AutoGen, and others based on demand.

---

## v0.4+ (on the horizon)

- **Deterministic replay** - re-run a traced agent with mocked tool outputs. Swap model, adjust temperature, override prompts.
- **Eval CI primitives** - turn traces into regression tests. Assert on tool sequence, token budgets, and outcomes. CLI-first, GitHub Actions friendly.
- **OpenTelemetry export** - optionally emit Maida events as OTel spans for teams that want to feed data into existing infrastructure.

---

## What Maida will not become

- Not a cloud platform. Local-first is the default, always.
- Not an observability dashboard. No metrics aggregation, no alerts, no SLOs.
- Not a prompt management tool. Debugging prompts, not versioning them.

If a team collaboration layer ever ships, it will be opt-in and will never compromise the local experience.
