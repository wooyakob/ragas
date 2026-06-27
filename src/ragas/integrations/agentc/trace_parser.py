"""
Converts Agent Catalog (agentc) activity logs into Ragas evaluation samples.

Agent Catalog logs are JSONL files where each line is a Log record with typed content.
This parser groups logs by session and converts them to Ragas MultiTurnSample objects.

Log kinds handled:
  - user           -> HumanMessage
  - tool-call      -> accumulated into AIMessage.tool_calls
  - tool-result    -> ToolMessage
  - chat-completion / assistant -> AIMessage
  - system, begin, end, edge, key-value, request-header -> skipped
"""

from __future__ import annotations

import json
import logging
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from ragas.dataset_schema import EvaluationDataset, MultiTurnSample
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage

logger = logging.getLogger(__name__)


@dataclass
class ParsedSession:
    """A parsed agent session ready for Ragas evaluation."""

    session_id: str
    span_name: t.List[str]
    sample: MultiTurnSample
    metadata: t.Dict[str, t.Any] = field(default_factory=dict)
    raw_logs: t.List[t.Dict] = field(default_factory=list)


class AgentCTraceParser:
    """Parses Agent Catalog JSONL activity logs into Ragas evaluation samples.

    Usage::

        parser = AgentCTraceParser()
        sessions = parser.parse_file("activity.jsonl")
        # Optionally attach reference answers
        sessions[0].sample.reference = "The expected final answer"
        dataset = parser.to_evaluation_dataset(sessions)
    """

    def parse_file(self, path: t.Union[str, Path]) -> t.List[ParsedSession]:
        """Parse a JSONL activity log file into sessions."""
        logs: t.List[t.Dict] = []
        with open(Path(path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return self.parse_logs(logs)

    def parse_logs(self, logs: t.List[t.Dict]) -> t.List[ParsedSession]:
        """Parse a list of log dicts (from JSONL) into sessions."""
        sessions: t.Dict[str, t.List[t.Dict]] = {}
        for log in logs:
            session_id = log.get("span", {}).get("session", "unknown")
            sessions.setdefault(session_id, []).append(log)

        # Sort each session's logs by timestamp
        for sid in sessions:
            sessions[sid].sort(key=lambda x: x.get("timestamp", ""))

        result = []
        for session_id, session_logs in sessions.items():
            parsed = self._convert_session(session_id, session_logs)
            if parsed is not None:
                result.append(parsed)
        return result

    def _convert_session(
        self, session_id: str, logs: t.List[t.Dict]
    ) -> t.Optional[ParsedSession]:
        """Convert logs for a single session into a ParsedSession."""
        messages: t.List[t.Union[HumanMessage, AIMessage, ToolMessage]] = []
        pending_tool_calls: t.List[ToolCall] = []
        span_name: t.List[str] = []
        metadata: t.Dict[str, t.Any] = {}

        for log in logs:
            content = log.get("content", {})
            kind = content.get("kind", "")

            if not span_name:
                span_name = log.get("span", {}).get("name", [])

            if "catalog_version" in log and not metadata.get("catalog_version"):
                metadata["catalog_version"] = log["catalog_version"]

            if kind == "user":
                self._flush_tool_calls(messages, pending_tool_calls)
                pending_tool_calls = []
                value = content.get("value", "")
                if value:
                    messages.append(HumanMessage(content=value))

            elif kind == "tool-call":
                # Accumulate consecutive tool calls into one AIMessage
                pending_tool_calls.append(
                    ToolCall(
                        name=content.get("tool_name", "unknown"),
                        args=content.get("tool_args", {}),
                    )
                )

            elif kind == "tool-result":
                self._flush_tool_calls(messages, pending_tool_calls)
                pending_tool_calls = []
                result = content.get("tool_result", "")
                result_str = (
                    json.dumps(result) if not isinstance(result, str) else result
                )
                messages.append(ToolMessage(content=result_str))

            elif kind in ("chat-completion", "assistant"):
                self._flush_tool_calls(messages, pending_tool_calls)
                pending_tool_calls = []
                value = content.get("output") or content.get("value", "")
                if value:
                    # Avoid duplicate consecutive AI messages with same content
                    if messages and isinstance(messages[-1], AIMessage) and messages[-1].content == value:
                        continue
                    messages.append(AIMessage(content=value))

            # Structural kinds (begin, end, edge, key-value, system, request-header)
            # are intentionally skipped for evaluation purposes

        self._flush_tool_calls(messages, pending_tool_calls)

        has_human = any(isinstance(m, HumanMessage) for m in messages)
        has_ai = any(isinstance(m, AIMessage) for m in messages)
        if not has_human or not has_ai or len(messages) < 2:
            return None

        try:
            sample = MultiTurnSample(user_input=messages)
        except ValueError as e:
            logger.warning(
                "Skipping session %s — MultiTurnSample validation failed: %s",
                session_id,
                e,
            )
            return None

        return ParsedSession(
            session_id=session_id,
            span_name=span_name,
            sample=sample,
            metadata=metadata,
            raw_logs=logs,
        )

    @staticmethod
    def _flush_tool_calls(
        messages: t.List, pending: t.List[ToolCall]
    ) -> None:
        if pending:
            messages.append(AIMessage(content="", tool_calls=list(pending)))
            pending.clear()

    def to_evaluation_dataset(self, sessions: t.List[ParsedSession]) -> EvaluationDataset:
        """Convert a list of ParsedSessions into an EvaluationDataset."""
        return EvaluationDataset(samples=[s.sample for s in sessions])

    def get_tool_calls_summary(self, session: ParsedSession) -> t.Dict[str, t.Any]:
        """Extract tool call statistics from a session."""
        tool_calls: t.List[ToolCall] = []
        for msg in session.sample.user_input:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
        return {
            "total_tool_calls": len(tool_calls),
            "unique_tools": list({tc.name for tc in tool_calls}),
            "tool_sequence": [tc.name for tc in tool_calls],
        }
