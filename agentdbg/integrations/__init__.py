"""
Optional framework integrations. No heavy imports at package load.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentdbg.integrations.langchain import AgentDbgLangChainCallbackHandler


def __getattr__(name: str):
    """Lazy load optional integrations so heavy deps are not required at import time."""
    if name == "AgentDbgLangChainCallbackHandler":
        from agentdbg.integrations.langchain import AgentDbgLangChainCallbackHandler
        return AgentDbgLangChainCallbackHandler
    if name == "crewai":
        from agentdbg.integrations import crewai as crewai_mod
        return crewai_mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
