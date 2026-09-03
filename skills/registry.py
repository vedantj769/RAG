"""
skills/registry.py — discovers skill folders (skills/<knowledge_type>/SKILL.md)
and parses each SKILL.md's YAML frontmatter (description, allowed_nodes,
allowed_relationships) plus its markdown body. The body holds two optional
sections used by different consumers:
  "## Extraction Prompt" — graph_builder.py's LLMGraphTransformer instructions.
  "## Retrieval Notes"   — retrieve.py's Cypher-generation schema/traversal notes.
If neither heading is present, the whole body is treated as the extraction prompt.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

SKILLS_DIR = Path(__file__).resolve().parent


@dataclass
class SkillPackage:
    knowledge_type: str
    description: str
    allowed_nodes: list[str]
    allowed_relationships: list[tuple[str, str, str]]
    prompt: str = ""
    retrieval_notes: str = ""


def _split_body(body: str) -> tuple[str, str]:
    """Split a SKILL.md body into (extraction_prompt, retrieval_notes) on the
    "## Retrieval Notes" heading, if present."""
    marker = "## Retrieval Notes"
    if marker in body:
        before, after = body.split(marker, 1)
        return before.replace("## Extraction Prompt", "").strip(), after.strip()
    return body.replace("## Extraction Prompt", "").strip(), ""


def _parse_skill_md(path: Path) -> dict:
    """SKILL.md = "---" YAML frontmatter (description/allowed_nodes/allowed_relationships)
    + a markdown body split into an extraction prompt and retrieval notes."""
    _, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    meta["prompt"], meta["retrieval_notes"] = _split_body(body)
    return meta


def load_skill(knowledge_type: str) -> Optional[SkillPackage]:
    """Load skills/<knowledge_type>/SKILL.md, if it exists; None otherwise."""
    path = SKILLS_DIR / knowledge_type / "SKILL.md"
    if not path.is_file():
        return None

    meta = _parse_skill_md(path)
    return SkillPackage(
        knowledge_type=knowledge_type,
        description=meta.get("description", ""),
        allowed_nodes=list(meta.get("allowed_nodes", [])),
        allowed_relationships=[tuple(r) for r in meta.get("allowed_relationships", [])],
        prompt=meta.get("prompt", ""),
        retrieval_notes=meta.get("retrieval_notes", ""),
    )


def list_skills() -> list[SkillPackage]:
    """Load every skills/<knowledge_type>/SKILL.md — used to show the LLM each
    skill's short description so it can pick the relevant one before extraction."""
    skills = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            skill = load_skill(child.name)
            if skill is not None:
                skills.append(skill)
    return skills
