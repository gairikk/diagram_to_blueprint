from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class AgentError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ArtifactRef(BaseModel):
    name: str
    uri: str
    content_type: Optional[str] = None

class Envelope(BaseModel):
    run_id: str
    step: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"  # ok|error
    errors: List[AgentError] = Field(default_factory=list)
    confidence: float = 1.0
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)