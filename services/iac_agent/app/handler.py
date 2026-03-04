import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import read_json, write_bytes


TEMPLATES_DIR = Path(
    os.environ.get("TEMPLATES_DIR", "shared/templates/terraform")
).resolve()


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    """Zip the contents of src_dir into zip_path."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(src_dir).as_posix())


def _render(j2: Environment, template_name: str, out_path: Path, ctx: dict) -> None:
    """Render a template from the jinja environment and write to out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(j2.get_template(template_name).render(**ctx), encoding="utf-8")


def _copytree_compat(src: Path, dst: Path) -> None:
    """
    Copy directory tree from src to dst.
    Compatible with Python versions that don't support shutil.copytree(dirs_exist_ok=True).
    """
    if not src.exists():
        raise FileNotFoundError(f"Module template path not found: {src}")

    if not dst.exists():
        shutil.copytree(src, dst)
        return

    # If dst exists, merge-copy files
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def run_step(env_dict: dict) -> dict:
    env = Envelope(**env_dict)

    try:
        normalized_uri = env.input["normalized_uri"]
        normalized = read_json(normalized_uri)

        resources = normalized.get("resources", [])
        naming = normalized.get("naming", {"prefix": "proj", "env": "dev"})
        tags = normalized.get("tags", {})
        azure = normalized.get("azure", {"location": "eastus"})

        # StrictUndefined helps catch missing template vars early
        j2 = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            undefined=StrictUndefined,
            autoescape=False,
        )

        with tempfile.TemporaryDirectory() as td_str:
            td = Path(td_str)
            (td / "modules").mkdir(parents=True, exist_ok=True)

            ctx = {"resources": resources, "naming": naming, "tags": tags, "azure": azure}

            # Root terraform files
            _render(j2, "root/providers.tf.j2", td / "providers.tf", ctx)
            _render(j2, "root/variables.tf.j2", td / "variables.tf", ctx)
            _render(j2, "root/main.tf.j2", td / "main.tf", ctx)
            _render(j2, "root/terraform.tfvars.j2", td / "terraform.tfvars", ctx)

            # Copy modules referenced by resources
            modules_src = TEMPLATES_DIR / "modules"

            for r in resources:
                mod = r.get("module") or "resource_group"
                src = modules_src / mod
                dst = td / "modules" / mod

                if not src.exists():
                    # Fallback: create a minimal resource_group module if missing
                    dst.mkdir(parents=True, exist_ok=True)

                    (dst / "variables.tf").write_text(
                        'variable "name" {\n'
                        "  type = string\n"
                        "}\n\n"
                        'variable "location" {\n'
                        "  type = string\n"
                        "}\n\n"
                        'variable "tags" {\n'
                        "  type    = map(string)\n"
                        "  default = {}\n"
                        "}\n",
                        encoding="utf-8",
                    )

                    (dst / "main.tf").write_text(
                        'resource "azurerm_resource_group" "rg" {\n'
                        "  name     = var.name\n"
                        "  location = var.location\n"
                        "  tags     = var.tags\n"
                        "}\n",
                        encoding="utf-8",
                    )
                else:
                    _copytree_compat(src, dst)

                    # If module template is main.tf.j2, render into main.tf
                    mt = dst / "main.tf.j2"
                    if mt.exists():
                        template_text = mt.read_text(encoding="utf-8")
                        rendered = Environment(undefined=StrictUndefined).from_string(
                            template_text
                        ).render(resource=r, **ctx)

                        (dst / "main.tf").write_text(rendered, encoding="utf-8")
                        mt.unlink()

            zip_path = td / "workspace.zip"
            _zip_dir(td, zip_path)

            uri = write_bytes(env.run_id, "iac/workspace.zip", zip_path.read_bytes())

        env.step = "iac_agent"
        env.output = {"workspace_zip_uri": uri}
        env.artifacts = [
            ArtifactRef(name="workspace_zip", uri=uri, content_type="application/zip")
        ]
        env.status = "ok"
        return env.model_dump()

    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="IAC_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()