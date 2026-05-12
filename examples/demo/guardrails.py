"""
Guardrails demo: stop_on_loop saves a runaway agent.

Shows how AgentDbg's stop_on_loop guardrail intercepts a stuck ReAct-style
agent loop before it burns more tokens. The trace captures the full evidence
(all events up to and including the LOOP_WARNING that tripped the guardrail),
so you can inspect exactly what pattern repeated.

Run from repo root:
   uv run python -m examples.demo.guardrails
Then:
   maida view
"""

import os

from maida import (
    LoopAbort,
    record_llm_call,
    record_state,
    record_tool_call,
    trace,
)


def _ensure_demo_defaults() -> None:
    # Lower the loop window so the repetition is detected quickly.
    # The default is 12; a window of 6 with repetitions=3 means the warning
    # fires after 3 identical (tool, llm) pairs -- exactly what this demo produces.
    os.environ.setdefault("MAIDA_LOOP_WINDOW", "6")
    os.environ.setdefault("MAIDA_LOOP_REPETITIONS", "3")


@trace(
    name="Demo agent, with guardrails",
    stop_on_loop=True,
    stop_on_loop_min_repetitions=3,
    max_llm_calls=20,  # hard ceiling; loop fires first in this demo
    max_tool_calls=20,
)
def run_demo() -> None:
    """
    Simulate a ReAct-style agent that gets stuck retrying the same search.

    A real agent would update its query based on the response, but this one
    keeps sending the same request because the LLM response tells it to
    "try again" without changing anything. AgentDbg's stop_on_loop
    guardrail detects the repeated pattern and aborts the run cleanly.
    """
    record_state(
        state={"phase": "init", "goal": "look up current pricing"},
        meta={"demo": "guardrails"},
    )

    # First iteration: normal-looking call
    record_tool_call(
        name="search_docs",
        args={"query": "current pricing tiers", "filter": "public"},
        result={"hits": [], "total": 0},
        meta={"demo": "guardrails", "iteration": 0},
    )
    record_llm_call(
        model="demo-model-local",
        prompt="The search returned no results. What should I do?",
        response="The search returned nothing. Try again with the same query.",
        usage={"prompt_tokens": 18, "completion_tokens": 12, "total_tokens": 30},
        meta={"demo": "guardrails", "iteration": 0},
    )

    # Subsequent iterations: agent is stuck -- same tool call, same LLM advice.
    # No state updates here: the repeating unit must be exactly (TOOL_CALL, LLM_CALL)
    # so the pattern length m=2 fits in the window (2 × repetitions=3 = 6 = window).
    # A state update inside the loop would make m=3, requiring window >= 9 to detect.
    for i in range(1, 15):
        record_tool_call(
            name="search_docs",
            args={"query": "current pricing tiers", "filter": "public"},
            result={"hits": [], "total": 0},
            meta={"demo": "guardrails", "iteration": i},
        )
        record_llm_call(
            model="demo-model-local",
            prompt="Still no results. What should I do?",
            response="The search returned nothing. Try again with the same query.",
            usage={"prompt_tokens": 16, "completion_tokens": 12, "total_tokens": 28},
            meta={"demo": "guardrails", "iteration": i},
        )
        # The guardrail fires from within record_llm_call on the iteration where
        # the last 6 window events become exactly [T, L, T, L, T, L] -- three
        # consecutive (search_docs, demo-model-local) pairs.


if __name__ == "__main__":
    _ensure_demo_defaults()
    print("[demo] Running runaway agent with stop_on_loop=True ...")
    try:
        run_demo()
        print("[demo] run completed without triggering guardrail (unexpected)")
    except LoopAbort as e:
        print(f"[demo] AgentDbg stopped the agent: {e}")
        print("[demo] The full trace is saved with the LOOP_WARNING and ERROR events.")
        print("[demo] Open the timeline with: maida view")
