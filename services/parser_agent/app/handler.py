from lxml import etree
from bs4 import BeautifulSoup
from pathlib import Path

from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import write_json

def _strip_html(s: str) -> str:
    return BeautifulSoup(s or "", "html.parser").get_text(" ").strip()

def parse_drawio(xml_path: str):
    xml = Path(xml_path).read_bytes()
    root = etree.fromstring(xml)
    cells = root.xpath(".//mxCell")

    elements = []
    connections = []

    for c in cells:
        if c.get("vertex") == "1":
            cid = c.get("id")
            value = _strip_html(c.get("value", ""))
            style = c.get("style", "")
            geom = c.find("mxGeometry")
            pos = {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
            if geom is not None:
                pos = {
                    "x": float(geom.get("x", "0")),
                    "y": float(geom.get("y", "0")),
                    "w": float(geom.get("width", "0")),
                    "h": float(geom.get("height", "0")),
                }
            elements.append({
                "id": cid,
                "raw_label": value,
                "shape_type": "vertex",
                "style": style,
                "position": pos
            })

    for c in cells:
        if c.get("edge") == "1":
            src = c.get("source")
            tgt = c.get("target")
            if src and tgt:
                connections.append({"from": src, "to": tgt, "arrow": True})

    return {"elements": elements, "connections": connections}

def run_step(env_dict: dict) -> dict:
    env = Envelope(**env_dict)
    try:
        xml_path = env.input["storage_uri"]
        artifact_type = env.input.get("artifact_type", "drawio")
        if artifact_type != "drawio":
            raise ValueError(f"Unsupported in MVP: {artifact_type}")

        parsed = parse_drawio(xml_path)
        out_uri = write_json(env.run_id, "parsed/diagram.json", parsed)

        env.step = "parser_agent"
        env.output = {"parsed_uri": out_uri, **parsed}
        env.artifacts = [ArtifactRef(name="parsed_json", uri=out_uri, content_type="application/json")]
        return env.model_dump()
    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="PARSER_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()