"""
Writes agent evaluation results to Couchbase for storage and SQL++ querying.

The documents are stored with the following structure, optimised for SQL++ analysis::

    {
      "id": "eval_abc123",
      "type": "agent_evaluation",
      "session_id": "<agentc session UUID>",
      "span_name": ["root", "my_agent"],
      "timestamp": "2026-06-27T12:00:00+00:00",
      "metrics": {
        "tool_step_efficiency": 0.85,
        "agent_goal_accuracy": 0.9
      },
      "trace_summary": {
        "total_tool_calls": 3,
        "unique_tools": ["search", "calculate"],
        "tool_sequence": ["search", "search", "calculate"],
        "num_turns": 7
      },
      "metadata": { "catalog_version": { ... } },
      "sample_preview": { "messages": [...], "reference": null }
    }

Example SQL++ queries::

    -- Average scores by agent
    SELECT span_name[0] AS agent, AVG(metrics.tool_step_efficiency) AS avg_efficiency
    FROM `agent_evals`.`_default`.`evaluations`
    WHERE type = 'agent_evaluation'
    GROUP BY span_name[0];

    -- Sessions with poor goal accuracy
    SELECT session_id, metrics, trace_summary
    FROM `agent_evals`.`_default`.`evaluations`
    WHERE metrics.agent_goal_accuracy < 0.5;
"""

from __future__ import annotations

import typing as t


class CouchbaseEvalWriter:
    """Writes evaluation results to a Couchbase collection.

    Usage::

        with CouchbaseEvalWriter(
            connection_string="couchbase://localhost",
            username="Administrator",
            password="password",
            bucket="agent_evals",
        ) as writer:
            writer.write(results_json)
    """

    def __init__(
        self,
        connection_string: str,
        username: str,
        password: str,
        bucket: str = "agent_evals",
        scope: str = "_default",
        collection: str = "evaluations",
    ):
        self.connection_string = connection_string
        self.username = username
        self.password = password
        self.bucket_name = bucket
        self.scope_name = scope
        self.collection_name = collection
        self._cluster: t.Any = None
        self._collection: t.Any = None

    def connect(self) -> None:
        """Establish connection to the Couchbase cluster."""
        try:
            from datetime import timedelta
            from couchbase.auth import PasswordAuthenticator
            from couchbase.cluster import Cluster
            from couchbase.options import ClusterOptions
        except ImportError:
            raise ImportError(
                "couchbase SDK not installed. Run: pip install couchbase"
            )

        auth = PasswordAuthenticator(self.username, self.password)
        self._cluster = Cluster(self.connection_string, ClusterOptions(auth))
        self._cluster.wait_until_ready(timedelta(seconds=10))
        bucket = self._cluster.bucket(self.bucket_name)
        self._collection = bucket.scope(self.scope_name).collection(
            self.collection_name
        )

    def write(self, results: t.List[t.Dict[str, t.Any]]) -> t.List[str]:
        """Upsert evaluation result documents. Returns list of document IDs."""
        if self._collection is None:
            self.connect()
        doc_ids = []
        for result in results:
            doc_id = result.get("id", f"eval_{hash(str(result))")
            self._collection.upsert(doc_id, result)
            doc_ids.append(doc_id)
        return doc_ids

    def write_one(self, result: t.Dict[str, t.Any]) -> str:
        """Upsert a single evaluation result document."""
        return self.write([result])[0]

    def close(self) -> None:
        if self._cluster is not None:
            self._cluster.close()

    def __enter__(self) -> "CouchbaseEvalWriter":
        self.connect()
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.close()

    @staticmethod
    def example_queries() -> t.Dict[str, str]:
        """Returns example SQL++ queries for analysing stored evaluations."""
        return {
            "avg_scores_by_agent": (
                "SELECT span_name[0] AS agent_name,\n"
                "       AVG(metrics.tool_step_efficiency) AS avg_efficiency,\n"
                "       AVG(metrics.agent_goal_accuracy) AS avg_goal_accuracy,\n"
                "       COUNT(*) AS num_sessions\n"
                "FROM `agent_evals`.`_default`.`evaluations`\n"
                "WHERE type = 'agent_evaluation'\n"
                "GROUP BY span_name[0]\n"
                "ORDER BY avg_goal_accuracy DESC;"
            ),
            "low_performing_sessions": (
                "SELECT session_id, metrics, trace_summary.total_tool_calls,\n"
                "       trace_summary.tool_sequence, timestamp\n"
                "FROM `agent_evals`.`_default`.`evaluations`\n"
                "WHERE type = 'agent_evaluation'\n"
                "  AND (metrics.agent_goal_accuracy < 0.5\n"
                "       OR metrics.tool_step_efficiency < 0.5)\n"
                "ORDER BY timestamp DESC\n"
                "LIMIT 20;"
            ),
            "tool_usage_frequency": (
                "SELECT t AS tool_name, COUNT(*) AS call_count\n"
                "FROM `agent_evals`.`_default`.`evaluations` AS e\n"
                "UNNEST e.trace_summary.unique_tools AS t\n"
                "WHERE e.type = 'agent_evaluation'\n"
                "GROUP BY t\n"
                "ORDER BY call_count DESC;"
            ),
            "daily_score_trend": (
                "SELECT SUBSTR(timestamp, 0, 10) AS date,\n"
                "       AVG(metrics.agent_goal_accuracy) AS avg_goal_accuracy,\n"
                "       COUNT(*) AS num_evals\n"
                "FROM `agent_evals`.`_default`.`evaluations`\n"
                "WHERE type = 'agent_evaluation'\n"
                "GROUP BY SUBSTR(timestamp, 0, 10)\n"
                "ORDER BY date;"
            ),
            "sessions_with_excess_tool_calls": (
                "SELECT session_id, trace_summary.total_tool_calls,\n"
                "       trace_summary.tool_sequence,\n"
                "       metrics.tool_step_efficiency\n"
                "FROM `agent_evals`.`_default`.`evaluations`\n"
                "WHERE trace_summary.total_tool_calls > 5\n"
                "  AND metrics.tool_step_efficiency < 0.7\n"
                "ORDER BY trace_summary.total_tool_calls DESC;"
            ),
        }
