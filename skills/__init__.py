"""
RCA_1 skills — one folder per knowledge_type (skills/<knowledge_type>/SKILL.md),
each declaring a short description plus the graph schema (allowed_nodes,
allowed_relationships) and the extraction prompt to use once that skill is picked.

graph_builder.py does not match chunks to skills by exact name — it shows the
LLM every skill's description (list_skills()) and lets it decide which one is
relevant to a given chunk; only the chosen skill's full schema/prompt is then
loaded (load_skill()) for extraction.
"""
from skills.registry import SkillPackage, list_skills, load_skill

__all__ = ["SkillPackage", "list_skills", "load_skill"]

