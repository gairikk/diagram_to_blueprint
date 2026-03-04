import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Any

from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import write_bytes


def _run_cmd(cmd: List[str], cwd: str, timeout: int = 600) -> Dict[str, Any]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": (p.stdout or "")[-20000:],
        "stderr": (p.stderr or "")[-20000:],
    }


def _has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def _unzip(zip_path: Path, out_dir: Path) -> None:
    with zipfile.ZipFile(str(zip_path), "r") as z:
        z.extractall(str(out_dir))


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(str(p), p.relative_to(src_dir).as_posix())


def run_step(env_dict: Dict[str, Any]) -> Dict[str, Any]:
    env = Envelope(**env_dict)

    try:
        workspace_zip_uri = env.input["workspace_zip_uri"]
        tooling = env.input.get("tooling") or ["terraform", "tflint", "checkov"]

        zip_path = Path(workspace_zip_uri)
        if not zip_path.exists():
            raise FileNotFoundError("workspace_zip_uri not found: {}".format(workspace_zip_uri))

        report: Dict[str, Any] = {
            "status": "pass",
            "steps": [],
            "tools": {},
            "issues": [],
        }

        with tempfile.TemporaryDirectory() as td_str:
            td = Path(td_str)
            _unzip(zip_path, td)

            # Terraform required
            if "terraform" in tooling:
                report["tools"]["terraform"] = _has_tool("terraform")
                if not report["tools"]["terraform"]:
                    raise RuntimeError("terraform binary not found in validate_agent container")

                report["steps"].append(_run_cmd(["terraform", "fmt", "-recursive"], cwd=str(td)))
                report["steps"].append(_run_cmd(["terraform", "init", "-backend=false"], cwd=str(td)))
                report["steps"].append(_run_cmd(["terraform", "validate"], cwd=str(td)))

            # tflint optional
            if "tflint" in tooling and _has_tool("tflint"):
                report["tools"]["tflint"] = True
                report["steps"].append(_run_cmd(["tflint", "--init"], cwd=str(td)))

                tfl = _run_cmd(["tflint", "-f", "json"], cwd=str(td))
                report["steps"].append(tfl)
                try:
                    parsed = json.loads(tfl.get("stdout") or "{}")
                    report["issues"].append({"tool": "tflint", "raw": parsed})
                except Exception:
                    report["issues"].append({"tool": "tflint", "raw": tfl.get("stdout")})
            else:
                report["tools"]["tflint"] = False

            # checkov optional
            if "checkov" in tooling and _has_tool("checkov"):
                report["tools"]["checkov"] = True
                ck = _run_cmd(["checkov", "-d", ".", "-o", "json"], cwd=str(td), timeout=900)
                report["steps"].append(ck)
                try:
                    ckjson = json.loads(ck.get("stdout") or "{}")
                    report["issues"].append({"tool": "checkov", "raw": ckjson})
                except Exception:
                    report["issues"].append({"tool": "checkov", "raw": ck.get("stdout")})
            else:
                report["tools"]["checkov"] = False

            # Decide PASS/FAIL based on return codes
            failed_cmds = [s for s in report["steps"] if s.get("returncode", 0) != 0]
            if failed_cmds:
                report["status"] = "fail"

            # Policy gating for HIGH/CRITICAL
            severity_block = set(
                s.strip().upper()
                for s in os.environ.get("CHECKOV_BLOCK_SEVERITY", "HIGH,CRITICAL").split(",")
                if s.strip()
            )
            for issue in report["issues"]:
                if issue.get("tool") != "checkov":
                    continue
                raw = issue.get("raw", {})
                failed = []
                try:
                    if isinstance(raw, dict):
                        results = raw.get("results", {}) or {}
                        failed = results.get("failed_checks", []) or []
                except Exception:
                    failed = []

                for f in failed:
                    sev = (f.get("severity") or "").upper()
                    if sev in severity_block:
                        report["status"] = "fail"
                        break

            report_bytes = json.dumps(report, indent=2).encode("utf-8")
            report_uri = write_bytes(env.run_id, "validated/report.json", report_bytes)

            out_zip = td / "validated.zip"
            _zip_dir(td, out_zip)
            validated_uri = write_bytes(env.run_id, "validated/validated.zip", out_zip.read_bytes())

        env.step = "validate_agent"
        env.output = {
            "status": report["status"],
            "validated_zip_uri": validated_uri,
            "report_uri": report_uri,
        }
        env.artifacts = [
            ArtifactRef(name="validated_zip", uri=validated_uri, content_type="application/zip"),
            ArtifactRef(name="validation_report", uri=report_uri, content_type="application/json"),
        ]
        env.status = "ok" if report["status"] == "pass" else "error"
        env.confidence = 1.0 if report["status"] == "pass" else 0.6
        return env.model_dump()

    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="VALIDATION_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()