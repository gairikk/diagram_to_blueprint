from shared.contracts.envelope import Envelope, ArtifactRef, AgentError
from shared.storage.local_storage import read_json, write_json

def run_step(env_dict: dict) -> dict:
    env = Envelope(**env_dict)
    try:
        parsed = read_json(env.input["parsed_uri"])

        nodes = [{
            "node_id": el["id"],
            "label": el.get("raw_label", ""),
            "metadata": {"style": el.get("style", ""), "position": el.get("position", {})}
        } for el in parsed["elements"]]

        edges = [{
            "source": c["from"],
            "target": c["to"],
            "relationship": "connects_to"
        } for c in parsed["connections"]]

        graph = {"nodes": nodes, "edges": edges}
        out_uri = write_json(env.run_id, "graph/graph.json", graph)

        env.step = "graph_agent"
        env.output = {"graph_uri": out_uri, **graph}
        env.artifacts = [ArtifactRef(name="graph_json", uri=out_uri, content_type="application/json")]
        return env.model_dump()
    except Exception as e:
        env.status = "error"
        env.errors = [AgentError(code="GRAPH_FAILED", message=str(e))]
        env.confidence = 0.0
        return env.model_dump()