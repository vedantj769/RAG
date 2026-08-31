"""Graph schema for KPI-definition style content (KPI, its formula, variables, and the
data features/semantic meanings those variables map to).

Mirrors the KPI Definition extraction skill 1:1 - see that skill's markdown file for
the full retrieval query guidance this schema is designed around.
"""
from __future__ import annotations

ALLOWED_NODES = [
    "KnowledgeType",
    "KPI",
    "Formula",
    "Variable",
    "DataFeature",
    "SemanticDefinition",
]

ALLOWED_RELATIONSHIPS: list[tuple[str, str, str]] = [
    ("KnowledgeType", "HAS_KPI", "KPI"),
    ("KPI", "HAS_FORMULA", "Formula"),
    ("KPI", "USES_VARIABLE", "Variable"),
    ("Variable", "SOURCED_FROM", "DataFeature"),
    ("Formula", "REFERENCES", "Variable"),
    ("Variable", "HAS_SEMANTIC_DEFINITION", "SemanticDefinition"),
]

EXTRACTION_INSTRUCTIONS = """
This content defines a KPI (Key Performance Indicator) used in factory/manufacturing
operations. When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "kpi_definition").
- KPI: the named KPI/metric being defined (e.g. "OEE").
- Formula: the exact calculation expression for the KPI, preserved as written.
- Variable: each variable referenced inside the formula.
- DataFeature: the source database/table/column a variable is sourced from.
- SemanticDefinition: the business-friendly name/description of a variable.

Only use the node and relationship types provided in the schema - do not invent new
ones. Preserve exact KPI names, formulas and variable names as written in the source
text. Extract every stated node property (e.g. a KPI's kpi_name/business_purpose/
unit/description, a Formula's expression, a Variable's variable_name, a DataFeature's
database/table/feature, a SemanticDefinition's business_name/description) - these
properties are how retrieval later finds and explains each node, so omitting them
makes the node effectively unanswerable.
""".strip()
