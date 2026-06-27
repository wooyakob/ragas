"""Couchbase writer for storing agent evaluation results."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class CouchbaseConfig:
    """Configuration for Couchbase connection."""

    connection_string: str
    username: str
    password: str
    bucket_name: str
    scope_name: str = "_default"
    collection_name: str = "agent_evaluations"


class CouchbaseEvalWriter:
    """Writer for storing agent evaluation results in Couchbase."""

    def __init__(self, config: CouchbaseConfig):
        self.config = config
        self._cluster = None
        self._collection = None

    def connect(self) -> "CouchbaseEvalWriter":
        """Connect to Couchbase cluster."""
        try:
            import datetime

            from couchbase.auth import PasswordAuthenticator
            from couchbase.cluster import Cluster
            from couchbase.options import ClusterOptions

            auth = PasswordAuthenticator(self.config.username, self.config.password)
            options = ClusterOptions(auth)
            self._cluster = Cluster(self.config.connection_string, options)
            self._cluster.wait_until_ready(datetime.timedelta(seconds=10))

            bucket = self._cluster.bucket(self.config.bucket_name)
            scope = bucket.scope(self.config.scope_name)
            self._collection = scope.collection(self.config.collection_name)

            logger.info(
                "Connected to Couchbase at %s, bucket=%s, scope=%s, collection=%s",
                self.config.connection_string,
                self.config.bucket_name,
                self.config.scope_name,
                self.config.collection_name,
            )
        except ImportError:
            raise ImportError(
                "The 'couchbase' package is required to use CouchbaseEvalWriter. "
                "Install it with: pip install couchbase"
            )
        return self

    @staticmethod
    def _fallback_doc_id(result: Dict[str, Any]) -> str:
        """Derive a deterministic document ID from stable result fields."""
        key = f"{result.get('session_id', '')}|{result.get('timestamp', '')}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"eval_{digest}"

    def write(self, results: List[Dict[str, Any]]) -> int:
        """Write a list of evaluation results to Couchbase. Returns count written."""
        if self._collection is None:
            raise RuntimeError("Not connected. Call connect() first.")

        written = 0
        for result in results:
            try:
                self.write_one(result)
                written += 1
            except Exception as e:
                logger.error("Failed to write result %s: %s", result.get("id", "unknown"), e)

        logger.info("Wrote %d/%d evaluation results to Couchbase", written, len(results))
        return written

    def write_one(self, result: Dict[str, Any]) -> None:
        """Write a single evaluation result to Couchbase."""
        if self._collection is None:
            raise RuntimeError("Not connected. Call connect() first.")

        doc_id = result.get("id") or self._fallback_doc_id(result)
        self._collection.upsert(doc_id, result)
        logger.debug("Wrote document %s", doc_id)

    def close(self) -> None:
        """Close the Couchbase connection."""
        if self._cluster is not None:
            self._cluster.close()
            self._cluster = None
            self._collection = None
            logger.info("Closed Couchbase connection")

    def __enter__(self) -> "CouchbaseEvalWriter":
        return self.connect()

    def __exit__(self, *args) -> None:
        self.close()

    @staticmethod
    def example_queries() -> Dict[str, str]:
        """Return example SQL++ queries for analysing stored evaluation results."""
        return {
            "avg_scores_by_agent": """
-- Average metric scores grouped by agent (span_name)
SELECT span_name,
       AVG(metrics.tool_step_efficiency)        AS avg_tool_efficiency,
       AVG(metrics.agent_response_faithfulness) AS avg_faithfulness,
       COUNT(*)                                 AS num_evaluations
FROM `{bucket}`.`{scope}`.`{collection}`
WHERE type = 'agent_evaluation'
GROUP BY span_name
ORDER BY avg_faithfulness DESC;
""",
            "low_performing_sessions": """
-- Sessions where any metric score fell below 0.5
SELECT id, session_id, span_name, timestamp, metrics
FROM `{bucket}`.`{scope}`.`{collection}`
WHERE type = 'agent_evaluation'
  AND (
    metrics.tool_step_efficiency < 0.5
    OR metrics.agent_response_faithfulness < 0.5
    OR metrics.tool_sequence_completeness < 0.5
  )
ORDER BY timestamp DESC
LIMIT 50;
""",
            "tool_usage_frequency": """
-- Frequency of each tool used across all evaluated sessions
SELECT tool, COUNT(*) AS usage_count
FROM `{bucket}`.`{scope}`.`{collection}` AS e
UNNEST e.trace_summary.tool_sequence AS tool
WHERE e.type = 'agent_evaluation'
GROUP BY tool
ORDER BY usage_count DESC;
""",
            "daily_score_trend": """
-- Daily average scores over time (requires ISO-8601 timestamps)
SELECT DATE_TRUNC_STR(timestamp, 'day')        AS day,
       AVG(metrics.tool_step_efficiency)        AS avg_efficiency,
       AVG(metrics.agent_response_faithfulness) AS avg_faithfulness,
       COUNT(*)                                 AS evaluations
FROM `{bucket}`.`{scope}`.`{collection}`
WHERE type = 'agent_evaluation'
GROUP BY DATE_TRUNC_STR(timestamp, 'day')
ORDER BY day DESC;
""",
            "sessions_with_excess_tool_calls": """
-- Sessions that made more than 10 tool calls (potential over-use)
SELECT id, session_id, span_name,
       trace_summary.total_tool_calls,
       metrics.tool_step_efficiency
FROM `{bucket}`.`{scope}`.`{collection}`
WHERE type = 'agent_evaluation'
  AND trace_summary.total_tool_calls > 10
ORDER BY trace_summary.total_tool_calls DESC;
""",
        }
