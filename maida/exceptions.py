"""
AgentDbg guardrail exceptions.

Raised when a run guardrail threshold is exceeded; lifecycle records ERROR + RUN_END
and re-raises so the caller can handle the abort.
"""


class _AgentDbgAbortSignal(BaseException):
    """Internal BaseException used by integration handlers to bypass framework
    error handling (e.g. LangGraph's ``except Exception``).

    Not part of the public API.  The ``_run_context`` lifecycle catches this
    signal, records ERROR + RUN_END, and re-raises the wrapped
    ``AgentDbgGuardrailExceeded`` so callers see the normal exception type.
    """

    def __init__(self, cause: "AgentDbgGuardrailExceeded") -> None:
        super().__init__(str(cause))
        self.cause = cause


class AgentDbgGuardrailExceeded(Exception):
    """
    Raised when a guardrail limit is exceeded (stop_on_loop, max_llm_calls, etc.).

    Attributes:
        guardrail: Identifier of the guardrail that fired (e.g. "stop_on_loop", "max_llm_calls").
        threshold: Configured limit that was exceeded.
        actual: Current value that exceeded the threshold.
        message: Human-readable description.
    """

    def __init__(
        self,
        guardrail: str,
        threshold: int | float,
        actual: int | float,
        message: str,
    ) -> None:
        super().__init__(message)
        self.guardrail = guardrail
        self.threshold = threshold
        self.actual = actual
        self.message = message


class AgentDbgLoopAbort(AgentDbgGuardrailExceeded):
    """
    Raised when stop_on_loop is enabled and loop detection fires above the threshold.

    Subclass of AgentDbgGuardrailExceeded so callers can catch loop aborts specifically.
    """

    def __init__(
        self,
        threshold: int,
        actual: int,
        message: str,
    ) -> None:
        super().__init__(
            guardrail="stop_on_loop",
            threshold=threshold,
            actual=actual,
            message=message,
        )
