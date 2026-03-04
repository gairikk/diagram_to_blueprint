import os, json, shutil
from pathlib import Path
from typing import Any

RUNS_DIR = Path(os.environ.get("RUNS_DIR", "./runs")).resolve()

def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_json(run_id: str, rel_path: str, obj: Any) -> str:
    p = run_dir(run_id) / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2))
    return str(p)

def read_json(path: str) -> Any:
    return json.loads(Path(path).read_text())

def write_bytes(run_id: str, rel_path: str, data: bytes) -> str:
    p = run_dir(run_id) / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)

def copy_to_run(run_id: str, rel_path: str, src_path: str) -> str:
    p = run_dir(run_id) / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, p)
    return str(p)