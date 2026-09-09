"""Pick which skills/<knowledge_type>/SKILL.md schema applies to a document section.

As documented in `skills/__init__.py`: chunks are not matched to skills by exact name -
every skill's short `description` is shown to the LLM and it decides which single skill
(if any) is relevant, so only that skill's allowed_nodes/allowed_relationships/prompt are
then used to constrain extraction for that section.
"""
from __future__ import annotations

import logging

from langchain_core.language_models import BaseLanguageModel

from skills.registry import SkillPackage

logger = logging.getLogger(__name__)

_NONE_ANSWER = "NONE"

_ROUTER_PROMPT = """You are routing a section of a knowledge document to the ONE knowledge \
type it belongs to, based on these available types:

{options}

Section heading: {heading}
Section content (excerpt):
{excerpt}

Reply with ONLY the knowledge_type value from the list above that best matches this \
section, or {none_answer} if none of them apply. Do not explain your answer."""


def select_skill(
    llm: BaseLanguageModel, skills: list[SkillPackage], heading: str, content: str
) -> SkillPackage | None:
    """Ask the LLM which skill's knowledge type best matches a section.

    Returns the matching `SkillPackage`, or None if the LLM answers "NONE" or names a
    type that isn't one of the loaded skills.
    """
    if not skills:
        return None

    options = "\n".join(f"- {skill.knowledge_type}: {skill.description}" for skill in skills)
    prompt = _ROUTER_PROMPT.format(
        options=options, heading=heading, excerpt=content[:500], none_answer=_NONE_ANSWER
    )
    response = llm.invoke(prompt)
    answer = str(response.content).strip().strip('"').strip("'").lower()

    for skill in skills:
        if skill.knowledge_type.lower() == answer:
            return skill

    if answer != _NONE_ANSWER.lower():
        logger.info("No skill matched section %r (router answered %r)", heading, answer)
    return None
