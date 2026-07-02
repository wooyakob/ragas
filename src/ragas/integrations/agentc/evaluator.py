"""
Evaluates Agent Catalog traces using Ragas metrics.

Converts agentc sessions into an EvaluationDataset, runs Ragas evaluation,
and returns structured JSON results ready for storage in Couchbase or local JSON files.

Usage::

    from ragas.integrations.agentc import AgentCEvaluator
    from ragas.integrations.agentc.metrics import ToolStepEfficiency, ToolSequenceCompleteness

    evaluator = AgentCEvaluator()
    results = evaluator.evaluate_file(
        "agent_activity.jsonl",
        metrics=[ToolStepEfficiency(), ToolSequenceCompleteness()],
    )
    for r in results:
        print(r.session_id, r.metrics)
"""

from __future__ import annotations

import json
import typing as t
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ragas.integrations.agentc.trace_parser import AgentCTraceParser, ParsedSession
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage


@dataclass
class AgentEvalResult:
    """Structured evaluation result for a single agent session."""

    eval_id: str
    session_id: str
    span_name: t.List[str]
    timestamp: str
    metrics: t.Dict[str, t.Optional[float]]
    trace_summary: t.Dict[str, t.Any]
    metadata: t.Dict[str, t.Any]
    sample_preview: t.Dict[str, t.Any]

    def to_dict(self) -> t.Dict[str, t.Any]:
        return {
            "id": self.eval_id,
            "type": "agent_evaluation",
            "session_id": self.session_id,
            "span_name": self.span_name,
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "trace_summary": self.trace_summary,
            "metadata": self.metadata,
            "sample_preview": self.sample_preview,
        }


class AgentCEvaluator:
    """Evaluates Agent Catalog traces using Ragas metrics."""

    def __init__(self, llm: t.Any = None, metrics: t.Optional[t.List[t.Any]] = None):
        self.llm = llm
        self._metrics = metrics or []
        self.parser = AgentCTraceParser()

    def evaluate_file(
        self,
        path: str,
        metrics: t.Optional[t.List[t.Any]] = None,
        references: t.Optional[t.Dict[str, str]] = None,
        reference_tool_calls: t.Optional[t.Dict[str, t.List[t.Dict]]] = None,
    ) -> t.List[AgentEvalResult]:
        """Evaluate all sessions in a JSONL activity log file."""
        sessions = self.parser.parse_file(path)
        return self.evaluate_sessions(sessions, metrics, references, reference_tool_calls)

    def evaluate_sessions(
        self,
        sessions: t.List[ParsedSession],
        metrics: t.Optional[t.List[t.Any]] = None,
        references: t.Optional[t.Dict[str, str]] = None,
        reference_tool_calls: t.Optional[t.Dict[str, t.List[t.Dict]]] = None,
    ) -> t.List[AgentEvalResult]:
        """Evaluate a list of ParsedSessions with the given metrics."""
        if not sessions:
            return []

        active_metrics = metrics if metrics is not None else self._metrics

        # Attach references
        if references:
            for s in sessions:
                if s.session_id in references:
                    s.sample.reference = references[s.session_id]

        if reference_tool_calls:
            for s in sessions:
                if s.session_id in reference_tool_calls:
                    s.sample.reference_tool_calls = [
                        ToolCall(**tc) for tc in reference_tool_calls[s.session_id]
                    ]

        # Attach LLM to metrics that need it
        if self.llm is not None:
            for metric in active_metrics:
                if hasattr(metric, "llm"):
                    metric.llm = self.llm

        from ragas import evaluate

        dataset = self.parser.to_evaluation_dataset(sessions)
        eval_result = evaluate(dataset=dataset, metrics=active_metrics)

        results = []
        for i, session in enumerate(sessions):
            score_row = eval_result.scores[i] if i < len(eval_result.scores) else {}
            tool_summary = self.parser.get_tool_calls_summary(session)

            results.append(
                AgentEvalResult(
                    eval_id=f"eval_{uuid.uuid4().hex[:12]}",
                    session_id=session.session_id,
                    span_name=session.span_name,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    metrics={
                        k: float(v) if v is not None and v == v else None
                        for k, v in score_row.items()
                    },
                    trace_summary={
                        **tool_summary,
                        "num_turns": len(session.sample.user_input),
                    },
                    metadata=session.metadata,
                    sample_preview=self._sample_preview(session),
                )
            )

        return results

    def _sample_preview(self, session: ParsedSession) -> t.Dict[str, t.Any]:
        preview = []
        for msg in session.sample.user_input[:8]:
            if isinstance(msg, HumanMessage):
                preview.append({"role": "human", "content": msg.content[:300]})
            elif isinstance(msg, AIMessage):
                entry: t.Dict[str, t.Any] = {"role": "ai", "content": msg.content[:300]}
                if msg.tool_calls:
                    entry["tool_calls"] = [{"name": tc.name, "args": tc.args} for tc in msg.tool_calls]
                preview.append(entry)
            elif isinstance(msg, ToolMessage):
                preview.append({"role": "tool", "content": msg.content[:300]})
        return {"messages": preview, "reference": session.sample.reference}

    def results_to_json(self, results: t.List[AgentEvalResult]) -> t.List[t.Dict]:
        """Convert results to JSON-serializable dicts."""
        return [r.to_dict() for r in results]

    def save_json(self, results: t.List[AgentEvalResult], path: str) -> None:
        """Save evaluation results to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results_to_json(results), f, indent=2)
