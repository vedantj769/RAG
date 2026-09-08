---
description: Documents a business term/concept — its definition, synonyms, examples, and related KPIs, tables and rules.
allowed_nodes:
  - KnowledgeType
  - DomainConcept
  - KPI
  - Table
  - BusinessRule
allowed_relationships:
  - [KnowledgeType, HAS_TERM, DomainConcept]
  - [DomainConcept, RELATED_TO, KPI]
  - [DomainConcept, RELATED_TO, Table]
  - [DomainConcept, RELATED_TO, BusinessRule]
  - [DomainConcept, RELATED_TO, DomainConcept]
---

## Extraction Prompt

This content documents a Domain Concept (template section 8): Knowledge Name,
Term, Definition, Business Meaning, Synonyms/Alternate Names, Examples,
Related Knowledge Names, Source Reference, Business Notes. When extracting
the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "domain_concept").
- DomainConcept: the term itself (e.g. "Planned Production Time"). Capture as
  properties whatever of these are present: term, definition, business_meaning,
  synonyms, examples.
- KPI / Table / BusinessRule: for every name under "Related Knowledge Names"
  that is clearly one of these, create/reference that node using the EXACT
  same name text the owning skill (kpi_definition / data_model / business_rule)
  would use for it, so they merge instead of creating duplicates.

Relationships to create:
- (KnowledgeType)-[:HAS_TERM]->(DomainConcept)
- (DomainConcept)-[:RELATED_TO]->(KPI) / (Table) / (BusinessRule) / (DomainConcept)
  for every name under "Related Knowledge Names".

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact term names and definitions as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. domainconcept:planned_production_time,
kpi:oee, table:shift_oee_details_for_workcenter,
businessrule:oee_aggregation_rule. `id` is the ONLY property guaranteed to
exist on every node — named properties were invented per-node by the
extraction LLM and are only present on SOME nodes of a label, never all of
them. Check the {schema} block above for which named properties actually
occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  DomainConcept -> term, definition, business_meaning, synonyms, examples
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  Table         -> model_name, business_name, description, database, schema
  BusinessRule  -> rule_name, condition, description
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label, e.g.:
  WHERE toLower(d.id) CONTAINS toLower("planned production time")
     OR toLower(d.term) CONTAINS toLower("planned production time")
Never rely on a named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_TERM]->(DomainConcept)
  (DomainConcept)-[:RELATED_TO]->(KPI)
  (DomainConcept)-[:RELATED_TO]->(Table)
  (DomainConcept)-[:RELATED_TO]->(BusinessRule)
  (DomainConcept)-[:RELATED_TO]->(DomainConcept)

KPI, Table and BusinessRule nodes here are the SAME nodes the kpi_definition,
data_model and business_rule skills extract (same label + same `id`
convention) — so a question about a business term reaches whichever KPI,
table or rule it relates to, and vice versa, without needing to know which
skill "owns" that data.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a DomainConcept,
KPI, Table, BusinessRule, ...) must return that entity's ENTIRE connected
subgraph in one query: match the anchor node, then expand outward through ALL
relationship types up to 3 hops, so nothing is missed regardless of how the
schema grows. Always shape the query this way:

  MATCH (anchor:DomainConcept) WHERE toLower(anchor.id) CONTAINS toLower("planned production time")
     OR toLower(anchor.term) CONTAINS toLower("planned production time")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (DomainConcept, KPI, Table, BusinessRule), always keeping the `id` CONTAINS
  check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
