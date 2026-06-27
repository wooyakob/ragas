"""FastAPI backend for the Ragas agent evaluation UI."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ragas Agent Evaluation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for evaluation runs (keyed by run_id)
_eval_store: Dict[str, Any] = {}


# ─────────────────────────── request / response models ───────────────────────

class EvaluateRequest(BaseModel):
    run_id: str
    metrics: List[str] = ["tool_step_efficiency", "agent_response_faithfulness"]
    llm_model: str = "gpt-4o-mini"
    openai_api_key: Optional[str] = None


class CouchbaseConfigModel(BaseModel):
    connection_string: str
    username: str
    password: str
    bucket_name: str
    scope_name: str = "_default"
    collection_name: str = "agent_evaluations"


class SaveToCouchbaseRequest(BaseModel):
    run_id: str
    couchbase: CouchbaseConfigModel


# ─────────────────────────── helpers ─────────────────────────────────────────

def _build_metrics(metric_names: List[str], llm=None):
    from ragas.integrations.agentc.metrics import (
        AgentResponseFaithfulness,
        ToolSequenceCompleteness,
        ToolStepEfficiency,
    )

    mapping = {
        "tool_step_efficiency": ToolStepEfficiency(),
        "tool_sequence_completeness": ToolSequenceCompleteness(),
        "agent_response_faithfulness": AgentResponseFaithfulness(llm=llm),
    }
    return [mapping[n] for n in metric_names if n in mapping]


def _make_llm(model: str, api_key: Optional[str]):
    """Return a LangChain LLM for Ragas metrics, or None on failure."""
    try:
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {"model": model}
        if api_key:
            kwargs["openai_api_key"] = api_key
        return ChatOpenAI(**kwargs)
    except Exception as e:
        logger.warning("Could not create LLM (%s); LLM-based metrics will be skipped.", e)
        return None


# ─────────────────────────── endpoints ───────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/parse")
def parse_traces(file: UploadFile = File(...)):
    """
    Upload a JSONL activity log file and parse it into sessions.

    Uses a sync handler so FastAPI runs it in a thread pool, avoiding
    event-loop blocking during JSON parsing of large files.
    """
    try:
        from ragas.integrations.agentc.trace_parser import AgentCTraceParser

        # Use the synchronous SpooledTemporaryFile read since we're in a thread
        content = file.file.read()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="File must be UTF-8 encoded. Please check your JSONL file encoding.",
            )

        lines = [ln for ln in text.strip().splitlines() if ln.strip()]
        if not lines:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        logs = []
        for i, line in enumerate(lines, 1):
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON on line {i}: {e}")

        parser = AgentCTraceParser()
        sessions = parser.parse_logs(logs)

        run_id = str(uuid.uuid4())
        _eval_store[run_id] = {
            "run_id": run_id,
            "status": "parsed",
            "filename": file.filename,
            "sessions": sessions,
            "results": [],
            "created_at": datetime.utcnow().isoformat(),
        }

        return {
            "run_id": run_id,
            "session_count": len(sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "span_name": s.span_name,
                    "message_count": len(s.sample.user_input),
                    "metadata": s.metadata,
                }
                for s in sessions
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error parsing traces")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate")
def evaluate(request: EvaluateRequest):
    """
    Run evaluation metrics on a previously parsed run.

    Uses a sync handler so FastAPI runs it in a thread pool. This is required
    because ragas.evaluate() calls asyncio.run() internally; calling it from
    an async handler would raise 'asyncio.run() cannot be called from a running
    event loop'.
    """
    run = _eval_store.get(request.run_id)
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {request.run_id} not found. Upload traces first.",
        )
    if run["status"] == "evaluating":
        raise HTTPException(status_code=409, detail="Evaluation already in progress.")

    try:
        from ragas.integrations.agentc.evaluator import AgentCEvaluator

        run["status"] = "evaluating"
        sessions = run["sessions"]

        llm = _make_llm(request.llm_model, request.openai_api_key)
        metrics = _build_metrics(request.metrics, llm=llm)

        if not metrics:
            raise HTTPException(status_code=400, detail="No valid metrics selected.")

        evaluator = AgentCEvaluator(metrics=metrics)
        results = evaluator.evaluate_sessions(sessions)
        json_results = evaluator.results_to_json(results)

        run["results"] = json_results
        run["status"] = "completed"
        run["completed_at"] = datetime.utcnow().isoformat()

        return {
            "run_id": request.run_id,
            "status": "completed",
            "result_count": len(json_results),
            "results": json_results,
        }
    except HTTPException:
        raise
    except Exception as e:
        run["status"] = "error"
        run["error"] = str(e)
        logger.exception("Error during evaluation")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/evaluations")
async def list_evaluations():
    """List all evaluation runs."""
    return [
        {
            "run_id": v["run_id"],
            "status": v["status"],
            "filename": v.get("filename"),
            "session_count": len(v.get("sessions", [])),
            "result_count": len(v.get("results", [])),
            "created_at": v.get("created_at"),
            "completed_at": v.get("completed_at"),
        }
        for v in _eval_store.values()
    ]


@app.get("/evaluations/{run_id}")
async def get_evaluation(run_id: str):
    """Get evaluation results for a specific run."""
    run = _eval_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return {k: v for k, v in run.items() if k != "sessions"}


@app.post("/save-to-couchbase")
def save_to_couchbase(request: SaveToCouchbaseRequest):
    """Save evaluation results to Couchbase (sync handler runs in thread pool)."""
    run = _eval_store.get(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found.")
    if not run.get("results"):
        raise HTTPException(
            status_code=400, detail="No results to save. Run evaluation first."
        )

    try:
        from ragas.integrations.agentc.couchbase_writer import (
            CouchbaseConfig,
            CouchbaseEvalWriter,
        )

        cfg = CouchbaseConfig(
            connection_string=request.couchbase.connection_string,
            username=request.couchbase.username,
            password=request.couchbase.password,
            bucket_name=request.couchbase.bucket_name,
            scope_name=request.couchbase.scope_name,
            collection_name=request.couchbase.collection_name,
        )
        with CouchbaseEvalWriter(cfg) as writer:
            written = writer.write(run["results"])

        return {"written": written, "total": len(run["results"])}
    except ImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error saving to Couchbase")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/example-queries")
async def example_queries():
    """Return example SQL++ queries for analysing stored results."""
    from ragas.integrations.agentc.couchbase_writer import CouchbaseEvalWriter

    return CouchbaseEvalWriter.example_queries()


@app.get("/available-metrics")
async def available_metrics():
    """Return list of available evaluation metrics."""
    return [
        {
            "id": "tool_step_efficiency",
            "name": "Tool Step Efficiency",
            "description": (
                "Measures how efficiently the agent used tools relative to the "
                "expected number of tool calls. Higher is better."
            ),
            "requires_reference": False,
        },
        {
            "id": "tool_sequence_completeness",
            "name": "Tool Sequence Completeness",
            "description": (
                "LCS-based metric measuring how completely the agent followed the "
                "expected tool sequence. Requires reference_tool_calls."
            ),
            "requires_reference": True,
        },
        {
            "id": "agent_response_faithfulness",
            "name": "Agent Response Faithfulness",
            "description": (
                "LLM-as-judge metric measuring whether the final response is "
                "faithful to the tool results gathered. Requires an LLM."
            ),
            "requires_reference": False,
        },
    ]
