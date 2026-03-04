import os
import re
from pathlib import Path
import yaml

from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import read_json, write_json

MAP_PATH = Path(os.environ.get("AZURE_MAP_PATH", "shared/mapping/azure_map.yaml")).resolve()

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _slug(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "x"

def _logical_name(base: str, index: int) -> str:
    return f"{_slug(base)}_{index}"

def _match_rule(label_norm: str, rules: list[dict]) -> tuple[dict | None, float]:
    """
    Returns (emit, confidence) if match found.
    Rule schema:
      { match: { label_contains: ["..."] }, emit: { resource_type: "...", module: "..." } }
    """
    best = None
    best_score = 0.0

    for r in rules:
        match = r.get("match", {}) or {}
        needles = match.get("label_contains", []) or []
        needles_norm = [_norm(x) for x in needles if x]

        if not needles_norm:
            continue

        # Score based on longest matching needle length
        score = 0.0
        for n in needles_norm:
            if n in label_norm:
                score = max(score, min(0.95, 0.5 + len(n) / 100.0))
        if score > best_score:
            best_score = score
            best = r.get("emit", {}) or {}

    return best, best_score

def _overrides_to_rules(overrides: list[dict]) -> list[dict]:
    """
    UI/LLM override schema example:
      { label_contains: "Web UI", resource_type: "azurerm_static_web_app", module: "static_web_app" }
    Convert to rule format and treat as highest priority.
    """
    out = []
    for o in overrides or []:
        lc = o.get("label_contains")
        rt = o.get("resource_type")
        mod = o.get("module")
        if lc and rt and mod:
            out.append({
                "match": {"label_contains": [lc]},
                "emit": {"resource_type": rt, "module": mod}
            })
    return out

def run_step(env_dict: dict) -> dict:
    env = Envelope(**env_dict)
    try:
        graph_uri = env.input["graph_uri"]
        graph = read_json(graph_uri)

        cfg = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
        base_rules = cfg.get("rules", []) or []
        defaults = cfg.get("defaults", {}) or {}
        default_tags = (defaults.get("tags", {}) or {})
        default_azure = (defaults.get("azure", {}) or {})

        # Inputs from UI/LLM
        naming = env.input.get("naming") or {"prefix": "proj", "env": "dev"}
        tags = {**default_tags, **(env.input.get("tags") or {})}
        azure = {**default_azure, **(env.input.get("azure") or {})}
        overrides = env.input.get("mapping_overrides") or []

        rules = _overrides_to_rules(overrides) + base_rules

        # Create normalized resources
        resources = []
        type_counts: dict[str, int] = {}
        confidences = []

        for node in graph.get("nodes", []):
            node_id = node.get("node_id")
            label = node.get("label", "") or ""
            label_norm = _norm(label)

            emit, score = _match_rule(label_norm, rules)

            # Fallback if no match: resource group module/type
            if not emit:
                emit = {"resource_type": "azurerm_resource_group", "module": "resource_group"}
                score = 0.35

            rtype = emit.get("resource_type", "azurerm_resource_group")
            module = emit.get("module", "resource_group")

            short = rtype.replace("azurerm_", "")
            type_counts[short] = type_counts.get(short, 0) + 1
            logical = _logical_name(short, type_counts[short])

            resources.append({
                "diagram_node_id": node_id,
                "diagram_label": label,
                "logical_name": logical,
                "provider": "azurerm",
                "resource_type": rtype,
                "module": module,
                "properties": {
                    # Keep room for later enrichment (SKU, size, etc.)
                },
                "tags": tags
            })
            confidences.append(score)

        # Relationships (depends_on) from graph edges
        node_to_logical = {r["diagram_node_id"]: r["logical_name"] for r in resources}
        relationships = []
        for edge in graph.get("edges", []):
            src = node_to_logical.get(edge.get("source"))
            tgt = node_to_logical.get(edge.get("target"))
            if src and tgt:
                relationships.append({"from": src, "to": tgt, "type": "depends_on"})

        normalized = {
            "resources": resources,
            "relationships": relationships,
            "naming": naming,
            "tags": tags,
            "azure": azure,
            "mapping_overrides": overrides
        }

        out_uri = write_json(env.run_id, "normalized/normalized.json", normalized)

        env.step = "normalizer_agent"
        env.output = {"normalized_uri": out_uri, **normalized}
        env.artifacts = [ArtifactRef(name="normalized_json", uri=out_uri, content_type="application/json")]
        env.status = "ok"
        env.confidence = round(sum(confidences) / max(len(confidences), 1), 3)
        return env.model_dump()

    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="NORMALIZE_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()