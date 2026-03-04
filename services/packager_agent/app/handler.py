import os
import tempfile
import zipfile
from pathlib import Path

from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import read_json, write_bytes

def _unzip(zip_path: Path, out_dir: Path):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

def _zip_dir(src_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(src_dir).as_posix())

def _make_readme(normalized: dict | None, report: dict | None) -> str:
    lines = []
    lines.append("# Diagram → Terraform (Azure)\n\n")
    lines.append("This repository was generated from a draw.io diagram.\n\n")

    if normalized:
        lines.append("## Resource Mapping\n\n")
        for r in normalized.get("resources", []):
            lines.append(f"- **{r.get('logical_name')}** → `{r.get('resource_type')}`"
                         f" (module: `{r.get('module')}`) — from diagram label: `{r.get('diagram_label','')}`\n")
        lines.append("\n")

        lines.append("## Naming & Tags\n\n")
        lines.append(f"- Prefix: `{normalized.get('naming', {}).get('prefix', '')}`\n")
        lines.append(f"- Env: `{normalized.get('naming', {}).get('env', '')}`\n")
        lines.append(f"- Location: `{normalized.get('azure', {}).get('location', '')}`\n\n")

    if report:
        lines.append("## Validation Summary\n\n")
        lines.append(f"- Status: **{report.get('status','unknown')}**\n\n")

    lines.append("## Deploy\n\n")
    lines.append("```bash\nterraform init\nterraform plan\nterraform apply\n```\n")
    return "".join(lines)

def _ado_pipeline_yaml() -> str:
    return """trigger:
- main

pool:
  vmImage: ubuntu-latest

steps:
- checkout: self
- task: TerraformInstaller@1
  inputs:
    terraformVersion: '1.7.5'
- script: |
    terraform init -backend=false
    terraform fmt -recursive
    terraform validate
    terraform plan
  displayName: 'Terraform validate & plan'
"""

def run_step(env_dict: dict) -> dict:
    env = Envelope(**env_dict)
    try:
        validated_zip_uri = env.input["validated_zip_uri"]
        normalized_uri = env.input.get("normalized_uri")
        report_uri = env.input.get("report_uri")
        include_ado = bool(env.input.get("include_ado_pipeline", True))

        validated_zip = Path(validated_zip_uri)
        if not validated_zip.exists():
            raise FileNotFoundError(f"validated_zip_uri not found: {validated_zip_uri}")

        normalized = read_json(normalized_uri) if normalized_uri else None
        report = read_json(report_uri) if report_uri else None

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _unzip(validated_zip, td)

            # Add README
            (td / "README.md").write_text(_make_readme(normalized, report), encoding="utf-8")

            # Optional Azure DevOps pipeline
            if include_ado:
                (td / "azure-pipelines.yml").write_text(_ado_pipeline_yaml(), encoding="utf-8")

            # Create final deliverable
            out_zip = td / "repo.zip"
            _zip_dir(td, out_zip)

            repo_uri = write_bytes(env.run_id, "deliverables/repo.zip", out_zip.read_bytes())

        env.step = "packager_agent"
        env.output = {"repo_zip_uri": repo_uri}
        env.artifacts = [ArtifactRef(name="repo_zip", uri=repo_uri, content_type="application/zip")]
        env.status = "ok"
        return env.model_dump()

    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="PACKAGER_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()