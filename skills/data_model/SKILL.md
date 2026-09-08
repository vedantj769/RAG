---
description: Documents a database table/entity — its metadata (system, schema, business key, granularity) and its field-by-field column definitions, including which fields relate to KPIs and business rules.
allowed_nodes:
  - KnowledgeType
  - Table
  - Field
  - KPI
  - BusinessRule
allowed_relationships:
  - [KnowledgeType, HAS_TABLE, Table]
  - [Table, HAS_FIELD, Field]
  - [Table, RELATED_TO_KPI, KPI]
  - [BusinessRule, GOVERNS, Table]
  - [Table, RELATED_TO_TABLE, Table]
  - [Field, COMPUTES_KPI, KPI]
---

## Extraction Prompt

This content documents a data model: one database table/entity, described by a
metadata block (Model / Table / Entity Name, Business Name, Description,
Database/System, Schema, Business Key, Granularity, Related Tables/Entities,
Related KPIs, Related Business Rules, Source Reference), followed by a
field-by-field breakdown table (Field Name, Data Type, Business Meaning,
Required?, Key/Relationship, Notes). When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "data_model").
- Table: the table/entity itself (its Knowledge Name, e.g. "Shift OEE Details for
  WorkCenter"). Capture as properties whatever of these are present: model_name
  (Model/Table/Entity Name, e.g. "KPI.dbo.Shift OEE"), business_name,
  description, database (Database/System, e.g. "MSSQL"), schema, business_key,
  granularity, source_reference.
- Field: one node per row of the field table (e.g. "WorkCenter",
  "PlannedProductionTimeInSec", "OEE"). Capture data_type, business_meaning
  (the full business meaning text, including any embedded formula exactly as
  written), required, and notes as properties, whichever are present. Every
  field row belongs to the ONE Table described by the metadata block earlier
  in this same content — always link each Field to that Table via HAS_FIELD,
  even though the metadata block and the field breakdown are two separate
  physical tables in the source document.
- KPI: for every name listed under "Related KPIs" (e.g. "OEE", "Availability",
  "Performance", "Quality"), create a KPI node using the EXACT same name text
  a KPI-definition document would use for it — this lets this table's KPI
  nodes merge with the ones extracted from kpi_definition content instead of
  creating duplicates.
- BusinessRule: for every name listed under "Related Business Rules" (e.g.
  "OEE Aggregation Rule"), create a BusinessRule node the same way.

Relationships to create:
- (KnowledgeType)-[:HAS_TABLE]->(Table)
- (Table)-[:HAS_FIELD]->(Field) for every field row.
- (Table)-[:RELATED_TO_KPI]->(KPI) for every name under "Related KPIs".
- (BusinessRule)-[:GOVERNS]->(Table) for every name under "Related
  Business Rules" — use the SAME relationship type/direction the business_rule
  skill uses, so both merge into one edge instead of creating a redundant,
  differently-named duplicate.
- (Table)-[:RELATED_TO_TABLE]->(Table) for every entry under "Related
  Tables / Entities", if any are listed.
- (Field)-[:COMPUTES_KPI]->(KPI): whenever a field's name or business meaning
  shows it IS a KPI's live computed value (e.g. fields literally named "OEE",
  "Availability", "Performance", "Quality"), link that field to the matching
  KPI node (same name-matching rule as above). This is the most important
  relationship in this skill — it is what lets a question about a KPI's value
  be traced to the exact table/field that stores it.

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact table names, field names and formulas as
written in the source text.

## Retrieval Notes

Node ids are prefixed by type, e.g. table:shift_oee_details_for_workcenter,
field:workcenter, field:oee, kpi:oee, businessrule:oee_aggregation_rule.
`id` is the ONLY property guaranteed to exist on every node — named
properties were invented per-node by the extraction LLM and are only present
on SOME nodes of a label, never all of them. Check the {schema} block above
for which named properties actually occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  Table         -> model_name, business_name, description, database, schema, business_key, granularity, source_reference
  Field         -> data_type, business_meaning, required, notes
  KPI           -> knowledge_name, kpi_name, business_purpose, unit, calculation_frequency, description
  BusinessRule  -> rule_name, description
  KnowledgeType -> name

Always anchor the match on `id` first (it always exists and contains the
entity's readable name), then OR in any named properties from the list above
that {schema} confirms exist for that label, e.g.:
  WHERE toLower(t.id) CONTAINS toLower("shift oee")
     OR toLower(t.business_name) CONTAINS toLower("shift oee")
     OR toLower(t.model_name) CONTAINS toLower("shift oee")
Never rely on a named property alone — always include the `id` CONTAINS check,
since that's the only match guaranteed to work.

Relationships:
  (KnowledgeType)-[:HAS_TABLE]->(Table)
  (Table)-[:HAS_FIELD]->(Field)
  (Table)-[:RELATED_TO_KPI]->(KPI)
  (BusinessRule)-[:GOVERNS]->(Table)
  (Table)-[:RELATED_TO_TABLE]->(Table)
  (Field)-[:COMPUTES_KPI]->(KPI)

KPI nodes here are the SAME nodes the kpi_definition skill extracts (same
label + same `id` convention) — so a query anchored on a KPI can traverse
`(KPI)<-[:COMPUTES_KPI]-(Field)<-[:HAS_FIELD]-(Table)` (or the reverse
direction) to reach the exact table's database/schema/business_key/
granularity properties that back that KPI's live value, without needing to
know in advance which skill "owns" that data. This is how a "what database
does the OEE value come from" question gets answered even though the KPI's
formula/variables and its database details were extracted from two different
documents/skills.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a Table, Field,
KPI, BusinessRule, etc.) must return that entity's ENTIRE connected subgraph
in one query: match the anchor node, then expand outward through ALL
relationship types up to 3 hops, so nothing is missed regardless of how the
schema grows. Always shape the query this way:

  MATCH (anchor:Table) WHERE toLower(anchor.id) CONTAINS toLower("shift oee")
     OR toLower(anchor.business_name) CONTAINS toLower("shift oee")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (Table, Field, KPI, BusinessRule, ...), always keeping the `id` CONTAINS
  check and OR-ing in only the named properties {schema} confirms exist for
  that label.
- Use an undirected, untyped `-[*1..3]-` traversal (not naming HAS_FIELD,
  COMPUTES_KPI, etc. individually) so newly added relationship types are
  picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact (e.g. "which system is table X stored in") and a full
  subgraph would be wasteful; otherwise default to the full 3-hop expansion.
