"""
Minimal OpenAI Agents tracing example with fake spans only.

Run from the repo root:
  uv run --extra openai-agents python examples/openai_agents/minimal.py

Then:
  agentdbg view
"""

from agentdbg import trace
from agentdbg.integrations import openai_agents
from agents.tracing import (
    function_span,
    generation_span,
    handoff_span,
    set_trace_processors,
    trace as agents_trace,
)


@trace(name="openai-agents minimal example")
def run_agent():
    """Emit deterministic SDK spans without making any model or network calls."""
    # Keep the SDK tracing local-only for this example: no backend exporter, no API key.
    set_trace_processors([openai_agents.PROCESSOR])

    with agents_trace("AgentDbg OpenAI Agents example"):
        with generation_span(
            input=[{"role": "user", "content": "Summarize AgentDbg in one sentence."}],
            output=[
                {
                    "role": "assistant",
                    "content": "AgentDbg is a local-first timeline debugger for AI agents.",
                }
            ],
            model="gpt-4o-mini",
            model_config={"temperature": 0.0},
            usage={"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
        ):
            pass

        with function_span(
            name="lookup_docs",
            input={"query": "AgentDbg integrations"},
            output={"hits": 2},
        ):
            pass

        with handoff_span(from_agent="router_agent", to_agent="docs_agent"):
            pass


if __name__ == "__main__":
    run_agent()
    print("Run complete. View with: agentdbg view")
