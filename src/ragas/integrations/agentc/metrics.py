"""
Novel agent-specific Ragas metrics using Agent Catalog execution traces.

These metrics complement standard Ragas metrics by leveraging the full execution
trace captured by Agent Catalog — tool calls, tool results, and agent behaviour —
rather than just the final input/output pair.

Metrics provided:

    ToolStepEfficiency
        Measures whether the agent used the right number of tool calls.
        Reference-free when no reference_tool_calls is provided.

    ToolSequenceCompleteness
        Fraction of expected tools invoked in the correct relative order
        (measured via longest common subsequence). Requires reference_tool_calls.

    AgentResponseFaithfulness
        LLM-as-judge metric: checks if the agent's final answer is grounded in
        the tool results it received, catching hallucinations and fabrications.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ragas.dataset_schema import MultiTurnSample
from ragas.messages import AIMessage, ToolMessage
from ragas.metrics.base import (
    MetricOutputType,
    MetricType,
    MetricWithLLM,
    MultiTurnMetric,
)
from ragas.prompt import PydanticPrompt

if t.TYPE_CHECKING:
    from langchain_core.callbacks.base import Callbacks


# ---------------------------------------------------------------------------
# ToolStepEfficiency
# ---------------------------------------------------------------------------


@dataclass
class ToolStepEfficiency(MultiTurnMetric):
    """Measures how efficiently the agent used tools.

    With reference_tool_calls:
        score = min(actual, expected) / max(actual, expected)
        Perfect score 1.0 when counts match; penalises over- and under-use equally.
        An empty reference (expected 0 tool calls) scores 1.0 when actual is also 0,
        and 0.0 otherwise.

    Without reference_tool_calls (reference-free mode):
        score = max(0, 1 - (actual - 1) / max_penalised_calls)
        Agents that use 1 tool score 1.0; the score decays linearly.
    """

    name: str = "tool_step_efficiency"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {MetricType.MULTI_TURN: {"user_input"}}
    )
    max_penalised_calls: int = 10

    def init(self, run_config: t.Any) -> None:
        pass

    def _count_tool_calls(self, sample: MultiTurnSample) -> int:
        count = 0
        for msg in sample.user_input:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                count += len(msg.tool_calls)
        return count

    async def _multi_turn_ascore(
        self, sample: MultiTurnSample, callbacks: "Callbacks"
    ) -> float:
        actual = self._count_tool_calls(sample)

        if actual == 0:
            # No tools called — perfect only if reference also expects none
            if sample.reference_tool_calls is not None:
                return 1.0 if len(sample.reference_tool_calls) == 0 else 0.0
            return 1.0

        if sample.reference_tool_calls is not None:
            expected = len(sample.reference_tool_calls)
            if expected == 0:
                # Reference expected no tools but agent called some
                return 0.0
            return min(actual, expected) / max(actual, expected)

        # Reference-free: penalise linearly above 1 tool call
        return max(0.0, 1.0 - (actual - 1) / self.max_penalised_calls)

    async def _ascore(self, row: t.Dict, callbacks: "Callbacks") -> float:
        return await self._multi_turn_ascore(MultiTurnSample(**row), callbacks)


# ---------------------------------------------------------------------------
# ToolSequenceCompleteness
# ---------------------------------------------------------------------------


@dataclass
class ToolSequenceCompleteness(MultiTurnMetric):
    """Fraction of expected tools invoked in the correct relative order.

    Uses longest common subsequence (LCS) to handle partial matches and
    extra/missing steps gracefully.

    Score = LCS(predicted_sequence, reference_sequence) / len(reference_sequence)

    Requires reference_tool_calls.
    """

    name: str = "tool_sequence_completeness"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.MULTI_TURN: {"user_input", "reference_tool_calls"}
        }
    )

    def init(self, run_config: t.Any) -> None:
        pass

    async def _multi_turn_ascore(
        self, sample: MultiTurnSample, callbacks: "Callbacks"
    ) -> float:
        assert sample.reference_tool_calls is not None, (
            "reference_tool_calls is required for ToolSequenceCompleteness"
        )

        pred_names = [
            tc.name
            for msg in sample.user_input
            if isinstance(msg, AIMessage) and msg.tool_calls
            for tc in msg.tool_calls
        ]
        ref_names = [tc.name for tc in sample.reference_tool_calls]

        if not ref_names:
            return 1.0 if not pred_names else 0.0

        lcs = _lcs_length(pred_names, ref_names)
        return lcs / len(ref_names)

    async def _ascore(self, row: t.Dict, callbacks: "Callbacks") -> float:
        return await self._multi_turn_ascore(MultiTurnSample(**row), callbacks)


def _lcs_length(a: t.List[str], b: t.List[str]) -> int:
    """Compute the length of the longest common subsequence."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


# ---------------------------------------------------------------------------
# AgentResponseFaithfulness
# ---------------------------------------------------------------------------


class FaithfulnessInput(BaseModel):
    tool_results: str = Field(
        ..., description="All tool results from the agent execution trace, joined by ---."
    )
    final_response: str = Field(
        ..., description="The agent's final response served back to the user."
    )


class FaithfulnessOutput(BaseModel):
    verdict: t.Literal["faithful", "unfaithful"] = Field(
        ...,
        description=(
            "faithful if the final response only uses information from tool results; "
            "unfaithful if it introduces external information or contradicts tools."
        ),
    )
    reason: str = Field(..., description="Brief justification for the verdict.")


class AgentFaithfulnessPrompt(
    PydanticPrompt[FaithfulnessInput, FaithfulnessOutput]
):
    instruction = (
        "You are evaluating an AI agent's response. "
        "Given the tool results from the agent's execution trace and its final response, "
        "determine whether the final response is faithful to the tool results. "
        "Respond 'faithful' if the response only uses information present in the tool results. "
        "Respond 'unfaithful' if it introduces facts not present in the tool results, "
        "or contradicts what the tools returned."
    )
    input_model = FaithfulnessInput
    output_model = FaithfulnessOutput
    examples = [
        (
            FaithfulnessInput(
                tool_results='{"temperature": 18, "condition": "sunny", "city": "London"}',
                final_response="The weather in London is 18°C and sunny.",
            ),
            FaithfulnessOutput(
                verdict="faithful",
                reason="Response accurately reflects the tool result.",
            ),
        ),
        (
            FaithfulnessInput(
                tool_results='{"temperature": 18, "condition": "sunny", "city": "London"}',
                final_response="The weather in London is 25°C with heavy rain.",
            ),
            FaithfulnessOutput(
                verdict="unfaithful",
                reason="Temperature and condition contradict the tool result.",
            ),
        ),
    ]


@dataclass
class AgentResponseFaithfulness(MetricWithLLM, MultiTurnMetric):
    """LLM-as-judge metric: checks if the agent's final response is grounded in tool outputs.

    This metric is specific to tool-augmented agents and catches a common failure mode:
    the agent producing a plausible-sounding answer that is not supported by (or
    contradicts) what its tools actually returned.

    Unlike standard Ragas Faithfulness (which checks against retrieved text contexts),
    this metric uses the trace's ToolMessage outputs as the grounding source.
    """

    name: str = "agent_response_faithfulness"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {MetricType.MULTI_TURN: {"user_input"}}
    )
    output_type: t.Optional[MetricOutputType] = MetricOutputType.BINARY
    faithfulness_prompt: PydanticPrompt = field(
        default_factory=lambda: AgentFaithfulnessPrompt()
    )

    async def _multi_turn_ascore(
        self, sample: MultiTurnSample, callbacks: "Callbacks"
    ) -> float:
        assert self.llm is not None, "LLM must be set on AgentResponseFaithfulness"

        tool_results = []
        final_response = ""

        for msg in sample.user_input:
            if isinstance(msg, ToolMessage):
                tool_results.append(msg.content)
            elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                final_response = msg.content  # last non-tool-call AI message

        if not tool_results or not final_response:
            return 1.0  # nothing to evaluate faithfulness against

        result = await self.faithfulness_prompt.generate(
            data=FaithfulnessInput(
                tool_results="\n---\n".join(tool_results),
                final_response=final_response,
            ),
            llm=self.llm,
            callbacks=callbacks,
        )
        return 1.0 if result.verdict == "faithful" else 0.0

    async def _ascore(self, row: t.Dict, callbacks: "Callbacks") -> float:
        return await self._multi_turn_ascore(MultiTurnSample(**row), callbacks)
