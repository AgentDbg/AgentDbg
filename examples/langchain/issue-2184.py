"""
Reproduction of issue #2184:
https://github.com/langchain-ai/deepagents/issues/2184

To run:

```
uv run \
    --with "langchain-openai" \
    --with "deepagents==0.4.12" \
    --with "langchain-core==1.2.20" \
    python examples/langchain/issue-2184.py
```
"""

import os
from dotenv import load_dotenv

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent, CompiledSubAgent

import agentdbg
from agentdbg.integrations import AgentDbgLangChainCallbackHandler

# 1. Environment Configuration (Standalone)
load_dotenv()
model_name = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
llm_config = {
    "model": model_name,
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "api_key": "ollama",
}

# Standard LLM instance
llm = ChatOpenAI(**llm_config)

# 2. Define a Simple Subagent Graph
# This subagent provides a definitive answer in an AIMessage
# def subagent_work(state: MessagesState):
#     # This simulates an expert providing a result
#     return {"messages": [AIMessage(content="The current user count is exactly 1200.")]}
# sub_builder = StateGraph(MessagesState)
# sub_builder.add_node("expert", subagent_work)
# sub_builder.set_entry_point("expert")
# sub_builder.add_edge("expert", END)


@tool
def get_user_count() -> str:
    """Get the current user count."""
    return "The current user count is exactly 1200."


def call_tool(state: MessagesState):
    """Simulate a subagent that decides to call a tool."""
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "get_user_count", "args": {}}],
            )
        ]
    }


sub_builder = StateGraph(MessagesState)
sub_builder.add_node("call_tool", call_tool)
sub_builder.add_node("tools", ToolNode([get_user_count]))
sub_builder.set_entry_point("call_tool")
sub_builder.add_edge("call_tool", "tools")
sub_builder.add_edge("tools", END)

sql_subagent = CompiledSubAgent(
    name="data-specialist",
    description="Use this agent to check user counts or data stats.",
    # description="This is a subagent.",
    runnable=sub_builder.compile(),
)

# 3. Parent Orchestrator
# This orchestrator uses the SubAgentMiddleware automatically via 'subagents' parameter
orchestrator = create_deep_agent(
    model=llm,
    subagents=[sql_subagent],
    name="NETS Orchestrator",
)

# 4. RUN REPRODUCTION
print(f"\n---  Starting STANDALONE Loop Reproduction with {model_name} ---")
print(
    "Scenario: Subagent returns AIMessage, but Parent's middleware wraps it in ToolMessage."
)
print(
    "Some models see this ToolMessage as 'more work needed' instead of 'task finished'."
)

try:
    # Changed query to English for global reporting
    query = "Please use the data-specialist to check the current total user count."
    print(f"\nUser Query: {query}")

    # We set debug=True to see the internal tool calls (task tool) looping.
    # config={"recursion_limit": 6} prevents the loop from hanging your system indefinitely.
    with agentdbg.traced_run(name="NETS Orchestrator"):
        result = orchestrator.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={
                "recursion_limit": 25,
                "callbacks": [AgentDbgLangChainCallbackHandler()],
            },
            debug=True,
        )

    print("\n--- Execution Finished (Unexpectedly?) ---")
    print(f"Final Answer: {result['messages'][-1].content}")

except Exception as e:
    print("\n---  Loop Detected or Limit Reached  ---")
    print(f"Captured Error: {e}")
    print(
        "\n[Technical Analysis] The parent agent repeatedly invoked the 'task' tool because it "
    )
    print(
        "did not recognize the subagent's response (wrapped in a ToolMessage) as a termination signal."
    )
