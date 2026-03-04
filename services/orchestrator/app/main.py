import os fails (you can change this behavior)
    validation_status = env.output.get("status", "fail") if env.output else "fail"
    report_uri = env.output.get("report_uri") if env.output else None
    validated_zip_uri = env.output.get("validated_zip_uri") if env.output else None

    if not validated_zip_uri:
        # If validation crashed completely, fall back to packaging workspace.zip (best effort)
        validated_zip_uri = workspace_zip_uri

    # 6) Package
    env = Envelope(run_id=rid, step="packager_agent", input={
        "validated_zip_uri": validated_zip_uri,
        "normalized_uri": normalized_uri,
        "report_uri": report_uri,
        "include_ado
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from shared.contracts.envelope import Envelope
from shared.storage.local_storage import RUNS_DIR, read_json

app = FastAPI(title="orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent endpoints (docker compose service names by default)
PARSER_URL = os.environ.get("PARSER_URL", "http://parser_agent:8000/run")
GRAPH_URL = os.environ.get("GRAPH_URL", "http://graph_agent:8000/run")
NORMALIZER_URL = os.environ.get("NORMALIZER_URL", "http://normalizer_agent:8000/run")
IAC_URL = os.environ.get("IAC_URL", "http://iac_agent:8000/run")
VALIDATE_URL = os.environ.get("VALIDATE_URL", "http://validate_agent:8000/run")
PACKAGER_URL = os.environ.get("PACKAGER_URL", "http://packager_agent:8000/run")

STEP_TIMEOUT = int(os.environ.get("STEP_TIMEOUT", "600"))

class StartRunRequest(BaseModel):
    run_id: str = ""
    storage_uri: str
    artifact_type: str = "drawio"
    naming: dict = Field(default_factory=lambda: {"prefix": "proj", "env": "dev"})
    tags: dict = Field(default_factory=dict)
    azure: dict = Field(default_factory=lambda: {"location": "eastus"})
    mapping_overrides: list[dict] = Field(default_factory=list)
    tooling: list[str] = Field(default_factory=lambda: ["terraform", "tflint", "checkov"])
    include_ado_pipeline: bool = True

def _call(url: str, env: Envelope) -> Envelope:
    r = requests.post(url, json=env.model_dump(), timeout=STEP_TIMEOUT)
    r.raise_for_status()
    return Envelope(**r.json())

@app.post("/runs/start")
def start_run(req: StartRunRequest):
    rid = req.run_id or str(uuid.uuid4())

    # 1) Parser
    env = Envelope(run_id=rid, step="parser_agent", input={
        "storage_uri": req.storage_uri,
        "artifact_type": req.artifact_type
    })
    env = _call(PARSER_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "parser_agent", "envelope": env.model_dump()}

    parsed_uri = env.output["parsed_uri"]

    # 2) Graph
    env = Envelope(run_id=rid, step="graph_agent", input={"parsed_uri": parsed_uri})
    env = _call(GRAPH_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "graph_agent", "envelope": env.model_dump()}

    graph_uri = env.output["graph_uri"]

    # 3) Normalize (apply UI/LLM overrides)
    env = Envelope(run_id=rid, step="normalizer_agent", input={
        "graph_uri": graph_uri,
        "naming": req.naming,
        "tags": req.tags,
        "azure": req.azure,
        "mapping_overrides": req.mapping_overrides
    })
    env = _call(NORMALIZER_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "normalizer_agent", "envelope": env.model_dump()}

    normalized_uri = env.output["normalized_uri"]

    # 4) IaC
    env = Envelope(run_id=rid, step="iac_agent", input={"normalized_uri": normalized_uri})
    env = _call(IAC_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "iac_agent", "envelope": env.model_dump()}

    workspace_zip_uri = env.output["workspace_zip_uri"]

    # 5) Validate + Policy
    env = Envelope(run_id=rid, step="validate_agent", input={
        "workspace_zip_uri": workspace_zip_uri,
        "tooling": req.tooling
    })
    env = _call(VALIDATE_URL, env)

