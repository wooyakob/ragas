"""
Generates sample Agent Catalog activity JSONL files for testing the evaluation framework.

Usage::

    python -m ragas.integrations.agentc.sample_generator --output activity.jsonl --sessions 5
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone


SAMPLE_SCENARIOS = [
    {
        "task": "weather_query",
        "user_input": "What is the weather like in London today?",
        "tool_calls": [
            {"name": "get_weather", "args": {"city": "London", "units": "celsius"}}
        ],
        "tool_results": [{"temperature": 15, "condition": "cloudy", "humidity": 72}],
        "final_response": "The weather in London is 15°C and cloudy with 72% humidity.",
    },
    {
        "task": "multi_step_research",
        "user_input": "Find the latest news about AI and summarise the top story.",
        "tool_calls": [
            {"name": "search_news", "args": {"query": "AI latest news", "limit": 5}},
            {"name": "fetch_article", "args": {"url": "https://example.com/ai-story-1"}},
        ],
        "tool_results": [
            {"results": [{"title": "AI Breakthrough in 2026", "url": "https://example.com/ai-story-1"}]},
            {"title": "AI Breakthrough", "content": "Scientists announce major AI advancement..."},
        ],
        "final_response": "The top AI story today is about a major breakthrough announced by scientists.",
    },
    {
        "task": "calculation",
        "user_input": "Calculate compound interest on $10,000 at 5% for 3 years.",
        "tool_calls": [
            {"name": "calculate", "args": {"expression": "10000 * (1 + 0.05) ** 3"}}
        ],
        "tool_results": [{"result": 11576.25, "expression": "10000 * (1.05)^3"}],
        "final_response": "Compound interest on $10,000 at 5% for 3 years results in $11,576.25.",
    },
]


def generate_session(
    scenario: dict,
    session_id: str,
    span_root: str = "eval_agent",
    base_time: datetime = None,
) -> list:
    """Generate a list of Log dicts for a single scenario session."""
    if base_time is None:
        base_time = datetime.now(timezone.utc)

    catalog_version = {
        "identifier": "abc123def456",
        "source_type": "git",
        "timestamp": base_time.isoformat(),
    }

    def make_log(kind_content: dict, offset_seconds: float) -> dict:
        return {
            "identifier": uuid.uuid4().hex,
            "span": {"session": session_id, "name": [span_root, scenario["task"]]},
            "timestamp": (base_time + timedelta(seconds=offset_seconds)).isoformat(),
            "content": kind_content,
            "annotations": None,
            "catalog_version": catalog_version,
        }

    logs = []
    t = 0.0

    logs.append(make_log({"kind": "begin", "state": {"task": scenario["task"]}}, t))
    t += 0.1

    logs.append(make_log({"kind": "user", "value": scenario["user_input"]}, t))
    t += 0.5

    for i, tc in enumerate(scenario["tool_calls"]):
        tool_call_id = uuid.uuid4().hex[:8]
        logs.append(make_log(
            {
                "kind": "tool-call",
                "tool_name": tc["name"],
                "tool_args": tc["args"],
                "tool_call_id": tool_call_id,
                "status": "success",
            },
            t,
        ))
        t += 0.2

        logs.append(make_log(
            {
                "kind": "tool-result",
                "tool_call_id": tool_call_id,
                "tool_result": scenario["tool_results"][i],
                "status": "success",
            },
            t,
        ))
        t += 0.3

    logs.append(make_log(
        {"kind": "assistant", "value": scenario["final_response"]},
        t,
    ))
    t += 0.1

    logs.append(make_log({"kind": "end", "state": {"completed": True}}, t))

    return logs


def generate_jsonl(num_sessions: int = 5, output_path: str = "sample_activity.jsonl") -> str:
    """Generate a sample JSONL file with multiple sessions."""
    all_logs = []
    for i in range(num_sessions):
        scenario = SAMPLE_SCENARIOS[i % len(SAMPLE_SCENARIOS)]
        session_id = uuid.uuid4().hex
        base_time = datetime.now(timezone.utc) - timedelta(minutes=num_sessions - i)
        logs = generate_session(scenario, session_id, base_time=base_time)
        all_logs.extend(logs)

    with open(output_path, "w") as f:
        for log in all_logs:
            f.write(json.dumps(log) + "\n")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample agentc activity JSONL")
    parser.add_argument("--output", default="sample_activity.jsonl")
    parser.add_argument("--sessions", type=int, default=5)
    args = parser.parse_args()
    path = generate_jsonl(args.sessions, args.output)
    print(f"Generated {args.sessions} sessions -> {path}")
