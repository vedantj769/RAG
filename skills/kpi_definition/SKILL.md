---
description: Defines a KPI, its formula, the variables it uses, and the data features/semantic meanings those variables map to.
allowed_nodes:
  - KnowledgeType
  - KPI
  - Formula
  - Variable
  - DataFeature
  - SemanticDefinition
allowed_relationships:
  - [KnowledgeType, HAS_KPI, KPI]
  - [KPI, HAS_FORMULA, Formula]
  - [KPI, USES_VARIABLE, Variable]
  - [Variable, SOURCED_FROM, DataFeature]
  - [Formula, REFERENCES, Variable]
  - [Variable, HAS_SEMANTIC_DEFINITION, SemanticDefinition]
---

## Extraction Prompt

This content defines a KPI (Key Performance Indicator) used in factory/
manufacturing operations. When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "kpi_definition").
- KPI: the named KPI/metric being defined (e.g. "OEE").
- Formula: the exact calculation expression for the KPI, preserved as written.
- Variable: each variable referenced inside the formula.
- DataFeature: the source database/table/column a variable is sourced from.
- SemanticDefinition: the business-friendly name/description of a variable.

Only use the node and relationship types provided in the schema — do not invent
new ones. Preserve exact KPI names, formulas and variable names as written in
the source text.

## Retrieval Notes

Node ids are prefixed by type, e.g. kpi:overall_equipment_effectiveness,
formula:overall_equipment_effectiveness, variable:run_time. `id` is the ONLY
property guaranteed to exist on every node — the extraction LLM was not
constrained to fixed property names, so named properties like
`knowledge_name`, `kpi_name`, `business_purpose`, `description`, `unit` etc.
were each invented per-node and are only present on SOME nodes of a label,
never all of them. Check the {schema} block above for which named properties
actually occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  KPI              -> knowledge_name, kpi_name, business_purpose, unit, calculation_frequency, description
  Formula          -> expression, language
  Variable         -> variable_name
  DataFeature      -> database, table, feature, operation, condition
  SemanticDefinition -> variable_name, business_name, description
  KnowledgeType    -> name

Always anchor the match on `id` first (it always exists and contains the
entity's readable name), then OR in any named properties from the list above
that {schema} confirms exist for that label, e.g.:
  WHERE toLower(k.id) CONTAINS toLower("oee")
     OR toLower(k.knowledge_name) CONTAINS toLower("oee")
     OR toLower(k.kpi_name) CONTAINS toLower("oee")
Never rely on a named property alone — always include the `id` CONTAINS check,
since that's the only match guaranteed to work.

Relationships:
  (KnowledgeType)-[:HAS_KPI]->(KPI)
  (KPI)-[:HAS_FORMULA]->(Formula)
  (KPI)-[:USES_VARIABLE]->(Variable)
  (Formula)-[:REFERENCES]->(Variable)
  (Variable)-[:SOURCED_FROM]->(DataFeature)
  (Variable)-[:HAS_SEMANTIC_DEFINITION]->(SemanticDefinition)

A KPI node has NO `formula` property — the formula text is on the linked
Formula node's `expression` property, reached via HAS_FORMULA. Traverse
relationships to reach the property that actually holds the answer
(e.g. formula, business_name, description).

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a KPI,
Variable, Formula, etc. — even a general "what is X" question) must return
that entity's ENTIRE connected subgraph in one query: match the anchor node,
then expand outward through ALL relationship types up to 3 hops, so nothing
is missed regardless of how the schema grows. Always shape the query this way:

  MATCH (anchor:KPI) WHERE toLower(anchor.id) CONTAINS toLower("oee")
     OR toLower(anchor.knowledge_name) CONTAINS toLower("oee")
     OR toLower(anchor.kpi_name) CONTAINS toLower("oee")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (Variable, Formula, DataFeature, ...), always keeping the `id` CONTAINS
  check and OR-ing in only the named properties {schema} confirms exist for
  that label.
- Use an undirected, untyped `-[*1..3]-` traversal (not naming HAS_FORMULA,
  USES_VARIABLE, etc. individually) so newly added relationship types are
  picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact (e.g. "which table is X sourced from") and a full
  subgraph would be wasteful; otherwise default to the full 3-hop expansion.
