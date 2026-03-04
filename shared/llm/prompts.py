SYSTEM_PROMPT = """You are an Azure Cloud Infrastructure assistant.
Given diagram labels extracted from a draw.io architecture diagram, propose conservative defaults:
- naming.prefix, naming.env
- azure.location
- tags (owner, cost_center, app, env if possible)
- mapping_overrides (label_contains, resource_type, module) for Azure Terraform
- questions for any missing critical info
Return STRICT JSON with keys: naming, tags, azure, mapping_overrides, questions.
Do not include extra keys.
"""

def build_user_prompt(labels: list[str]) -> str:
    joined = "\n".join(f"- {x}" for x in labels[:200])
    return f"""Diagram labels detected:
{joined}

Constraints:
- Cloud target: Azure (Terraform azurerm)
- Terraform style: modules-per-resource
- Keep suggestions conservative; if uncertain, ask questions.
"""