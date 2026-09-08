"""Tests for skill routing (fake LLM, no Groq/Neo4j required)."""
from __future__ import annotations

from dataclasses import dataclass

from graph_rag.skill_router import select_skill
from skills.registry import SkillPackage

SKILLS = [
    SkillPackage(
        knowledge_type="kpi_definition",
        description="Defines a KPI, its formula and variables.",
        allowed_nodes=["KPI"],
        allowed_relationships=[],
    ),
    SkillPackage(
        knowledge_type="business_rule",
        description="Defines a business rule that governs data or calculations.",
        allowed_nodes=["BusinessRule"],
        allowed_relationships=[],
    ),
]


@dataclass
class _FakeResponse:
    content: str


class _FakeLLM:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    def invoke(self, _prompt: str) -> _FakeResponse:
        return _FakeResponse(content=self._answer)


def test_select_skill_returns_matching_skill() -> None:
    llm = _FakeLLM("kpi_definition")

    skill = select_skill(llm, SKILLS, heading="2. KPI Definitions", content="OEE = ...")

    assert skill is not None
    assert skill.knowledge_type == "kpi_definition"


def test_select_skill_returns_none_when_llm_says_none() -> None:
    llm = _FakeLLM("NONE")

    skill = select_skill(llm, SKILLS, heading="1. Knowledge Summary", content="Overview text")

    assert skill is None


def test_select_skill_returns_none_for_unknown_answer() -> None:
    llm = _FakeLLM("some_unrelated_type")

    skill = select_skill(llm, SKILLS, heading="X", content="Y")

    assert skill is None


def test_select_skill_returns_none_when_no_skills_loaded() -> None:
    skill = select_skill(_FakeLLM("kpi_definition"), [], heading="X", content="Y")

    assert skill is None
