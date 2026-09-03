---
description: Documents data lineage — how a source table/field flows and transforms (business logic, not code) into a target table/field or KPI.
allowed_nodes:
  - KnowledgeType
  - LineageFlow
  - Table
  - Field
  - KPI
allowed_relationships:
  - [KnowledgeType, HAS_LINEAGE, LineageFlow]
  - [KPI, DERIVED_FROM, LineageFlow]
  - [Table, DERIVED_FROM, LineageFlow]
  - [Field, DERIVED_FROM, LineageFlow]
  - [LineageFlow, USES_DATA, Table]
  - [LineageFlow, USES_DATA, Field]
---

## Extraction Prompt

This content documents Data Lineage (template section 7): a table of Source
System/Table, Source Field, Transformation/Business Logic, Target, Target
Field, Notes — describing the business transformation (not implementation
code), e.g. "Aggregate GoodQuantity and TotalQuantity, then calculate
Quality = GoodQuantity / TotalQuantity × 100." When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "data_lineage").
- LineageFlow: one node per lineage row, representing that one source-to-target
  transformation. Capture as properties: transformation_logic (the business
  logic text, preserved as written), notes.
- Table / Field: the source table/field AND the target table/field (when the
  target is itself a table/field, not a KPI). Use the EXACT same names the
  data_model skill would use for these, so they merge instead of duplicating.
- KPI: when the Target is a KPI (e.g. "OEE"), create/reference that KPI node
  using the EXACT same name text the kpi_definition skill would use for it.

Relationships to create:
- (KnowledgeType)-[:HAS_LINEAGE]->(LineageFlow)
- (LineageFlow)-[:USES_DATA]->(Table) and/or (Field): the SOURCE table/field
  this lineage row reads from.
- (Table)-[:DERIVED_FROM]->(LineageFlow), (Field)-[:DERIVED_FROM]->(LineageFlow),
  or (KPI)-[:DERIVED_FROM]->(LineageFlow): whichever of Table/Field/KPI is the
  TARGET this lineage row produces.

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact table/field names and the transformation
logic text as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. lineageflow:production_events_to_oee,
table:production_events, kpi:oee. `id` is the ONLY property guaranteed to
exist on every node — named properties were invented per-node by the
extraction LLM and are only present on SOME nodes of a label, never all of
them. Check the {schema} block above for which named properties actually
occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  LineageFlow   -> transformation_logic, notes
  Table         -> model_name, business_name, description, database, schema
  Field         -> data_type, business_meaning, notes
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label. Never rely on a
named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_LINEAGE]->(LineageFlow)
  (LineageFlow)-[:USES_DATA]->(Table)
  (LineageFlow)-[:USES_DATA]->(Field)
  (Table)-[:DERIVED_FROM]->(LineageFlow)
  (Field)-[:DERIVED_FROM]->(LineageFlow)
  (KPI)-[:DERIVED_FROM]->(LineageFlow)

Table, Field and KPI nodes here are the SAME nodes the data_model and
kpi_definition skills extract (same label + same `id` convention) — so a
question like "where does OEE's data come from" anchors on the KPI node and
traverses `(KPI)-[:DERIVED_FROM]->(LineageFlow)-[:USES_DATA]->(Table/Field)`
to reach the exact upstream source, without needing to know which skill
"owns" that source data.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a LineageFlow,
Table, Field, KPI, ...) must return that entity's ENTIRE connected subgraph in
one query: match the anchor node, then expand outward through ALL
relationship types up to 3 hops, so nothing is missed regardless of how the
schema grows. Always shape the query this way:

  MATCH (anchor:KPI) WHERE toLower(anchor.id) CONTAINS toLower("oee")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (LineageFlow, Table, Field, KPI), always keeping the `id` CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
