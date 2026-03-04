from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uuid, json, re
from lxml import etree
from bs4 import BeautifulSoup

from shared.contracts.envelope import Envelope, ArtifactRef
from shared.storage.local_storage import write_bytes
from shared.llm.azure_openai_client import chat_json
from shared.llm.prompts import SYSTEM_PROMPT, build_user_prompt

app = FastAPI(title="upload_agent")

# CORS so UI can call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_type(filename: str) -> str:
    f = (filename or "").lower()
    if f.endswith(".drawio") or f.endswith(".xml"):
        return "drawio"
    return "unknown"

def _strip_html(s: str) -> str:
    return BeautifulSoup(s or "", "html.parser").get_text(" ").strip()

def extract_labels_drawio(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    cells = root.xpath(".//mxCell[@value]")
    labels = []
    for c in cells:
        v = _strip_html(c.get("value", ""))
        if v:
            labels.append(v)

    seen = set()
    out = []
    for x in labels:
        k = re.sub(r"\s+", " ", x.lower()).strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out[:200]

def safe_suggestions(s: dict) -> dict:
    naming = s.get("naming") or {}
    tags = s.get("tags") or {}
    azure = s.get("azure") or {}
    overrides = s.get("mapping_overrides") or []
    questions = s.get("questions") or []

    def cut(x, n): return str(x)[:n]

    return {
        "naming": {"prefix": cut(naming.get("prefix", "proj"), 20), "env": cut(naming.get("env", "dev"), 10)},
        "tags": {cut(k, 30): cut(v, 80) for k, v in list(tags.items())[:25]},
        "azure": {"location": cut(azure.get("location", "eastus"), 20)},
        "mapping_overrides": [
            {
                "label_contains": cut(o.get("label_contains", ""), 60),
                "resource_type": cut(o.get("resource_type", ""), 60),
                "module": cut(o.get("module", ""), 40),
            } for o in overrides[:25]
        ],
        "questions": [cut(q, 140) for q in questions[:20]]
    }

@app.post("/upload")
async def upload(file: UploadFile = File(...), run_id: str = Form(default="")):
    rid = run_id or str(uuid.uuid4())
    data = await file.read()

    artifact_type = detect_type(file.filename)
    uri = write_bytes(rid, f"raw/{file.filename}", data)

    extracted_labels = extract_labels_drawio(data) if artifact_type == "drawio" else []

    # LLM suggestions
    llm_suggestions = {}
    if extracted_labels:
        try:
            raw = chat_json(SYSTEM_PROMPT, build_user_prompt(extracted_labels))
            llm_suggestions = safe_suggestions(json.loads(raw))
        except Exception as e:
            llm_suggestions = safe_suggestions({})
            llm_suggestions["questions"] = [f"LLM failed: {str(e)}"]

    env = Envelope(
        run_id=rid,
        step="upload_agent",
        output={
            "artifact_type": artifact_type,
            "filename": file.filename,
            "storage_uri": uri,
            "extracted_labels": extracted_labels,
            "llm_suggestions": llm_suggestions,
        },
        artifacts=[ArtifactRef(name="raw_file", uri=uri, content_type=file.content_type)]
    )
    return env