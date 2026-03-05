import os
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Create app FIRST to avoid "app not found" if later imports fail
app = FastAPI(title="orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Lazy imports after app creation ---
from shared.contracts.envelope import Envelope
from shared.storage.local_storage import RUNS_DIR

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/runs/start")
def start_run(req: StartRunRequest):
    rid = req.run_id or str(uuid.uuid4())

    env = Envelope(run_id=rid, step="parser_agent", input={
        "storage_uri": req.storage_uri,
        "artifact_type": req.artifact_type
    })
    env = _call(PARSER_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "parser_agent", "envelope": env.model_dump()}

    env = Envelope(run_id=rid, step="graph_agent", input={"parsed_uri": env.output["parsed_uri"]})
    env = _call(GRAPH_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "graph_agent", "envelope": env.model_dump()}

    env = Envelope(run_id=rid, step="normalizer_agent", input={
        "graph_uri": env.output["graph_uri"],
        "naming": req.naming,
        "tags": req.tags,
        "azure": req.azure,
        "mapping_overrides": req.mapping_overrides
    })
    env = _call(NORMALIZER_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "normalizer_agent", "envelope": env.model_dump()}

    normalized_uri = env.output["normalized_uri"]

    env = Envelope(run_id=rid, step="iac_agent", input={"normalized_uri": normalized_uri})
    env = _call(IAC_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "iac_agent", "envelope": env.model_dump()}

    workspace_zip_uri = env.output["workspace_zip_uri"]

    env = Envelope(run_id=rid, step="validate_agent", input={
        "workspace_zip_uri": workspace_zip_uri,
        "tooling": req.tooling
    })
    env = _call(VALIDATE_URL, env)

    validation_status = env.output.get("status", "fail")
    report_uri = env.output.get("report_uri")
    validated_zip_uri = env.output.get("validated_zip_uri") or workspace_zip_uri

    env = Envelope(run_id=rid, step="packager_agent", input={
        "validated_zip_uri": validated_zip_uri,
        "normalized_uri": normalized_uri,
        "report_uri": report_uri,
        "include_ado_pipeline": req.include_ado_pipeline
    })
    env = _call(PACKAGER_URL, env)
    if env.status == "error":
        return {"run_id": rid, "failed_step": "packager_agent", "envelope": env.model_dump()}

    return {
        "run_id": rid,
        "validation_status": validation_status,
        "report_uri": report_uri,
        "repo_zip_uri": env.output.get("repo_zip_uri"),
        "download": {
            "repo": f"/runs/{rid}/download/repo",
            "report": f"/runs/{rid}/download/report"
        }
    }

@app.get("/runs/{run_id}/download/repo")
def download_repo(run_id: str):
    p = Path(RUNS_DIR) / run_id / "deliverables" / "repo.zip"
    if not p.exists():
        return {"error": "repo.zip not found", "path": str(p)}
    return FileResponse(str(p), media_type="application/zip", filename=f"{run_id}-repo.zip")

@app.get("/runs/{run_id}/download/report")
def download_report(run_id: str):
    p = Path(RUNS_DIR) / run_id / "validated" / "report.json"
    if not p.exists():
        return {"error": "report.json not found", "path": str(p)}
    return FileResponse(str(p), media_type="application/json", filename=f"{run_id}-report.json")