---
description: Documents how a business question is answered from data — required inputs, source table, filters, calculation/aggregation rule, and output fields. This is the retrieval recipe behind a KPI's live value.
allowed_nodes:
  - KnowledgeType
  - Query
  - OutputField
  - KPI
  - Table
  - BusinessRule
allowed_relationships:
  - [KnowledgeType, HAS_QUERY, Query]
  - [Query, USES_DATA, Table]
  - [Query, SUPPORTS_ANALYSIS_OF, KPI]
  - [Query, REQUIRES, BusinessRule]
  - [Query, HAS_COMPONENT, OutputField]
---

## Extraction Prompt

This content documents a Data Query Definition (template section 12): Knowledge
Name, Query/Use Case Name, Business Question, Business Purpose, Required/
Optional Inputs, Data Source/System, Table/Dataset/Entity, Business Key,
Filter Criteria, Time Range Logic, Expected Output, Calculation Required?,
Calculation/Aggregation Rule, Business Rules to Apply, Exceptions/Exclusions,
Related Knowledge Names, Source Reference, Business Notes — followed by an
output table (section 12.1: Output Field, Business Meaning, Format/Unit,
Example). When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "data_query_definition").
- Query: the query/use case itself (e.g. "Shift OEE Lookup"). Capture as
  properties whatever of these are present: business_question,
  business_purpose, required_inputs, optional_inputs, data_source,
  business_key, filter_criteria, time_range_logic, expected_output,
  calculation_required, calculation_rule, exceptions.
- OutputField: one node per row of the output table. Capture business_meaning,
  format_unit, example as properties. Every output field row belongs to the
  ONE Query described earlier in this same content, even though the query's
  metadata and its output fields are two separate physical tables in the
  source document.
- Table: the "Table/Dataset/Entity" this query reads from — use the EXACT
  same name text the data_model skill would use for it, so they merge
  instead of creating duplicates.
- KPI: when the Business Question or Expected Output is clearly about a KPI's
  value (e.g. "Shift OEE Lookup" answers a question about "OEE"), create/
  reference that KPI node using the EXACT same name text the kpi_definition
  skill would use for it.
- BusinessRule: for every name under "Business Rules to Apply" or "Related
  Knowledge Names" that is a rule, create/reference it using the EXACT same
  name text the business_rule skill would use for it.

Relationships to create:
- (KnowledgeType)-[:HAS_QUERY]->(Query)
- (Query)-[:USES_DATA]->(Table)
- (Query)-[:SUPPORTS_ANALYSIS_OF]->(KPI): this is the MOST IMPORTANT
  relationship in this skill — it is what lets a question about a KPI's
  current/live value be traced to the exact query/table that retrieves it.
- (Query)-[:REQUIRES]->(BusinessRule)
- (Query)-[:HAS_COMPONENT]->(OutputField) for every output row.

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact query names, filter/calculation text as
written.

## Retrieval Notes

Node ids are prefixed by type, e.g. query:shift_oee_lookup,
outputfield:oee, kpi:oee, table:shift_oee_details_for_workcenter,
businessrule:oee_aggregation_rule. `id` is the ONLY property guaranteed to
exist on every node — named properties were invented per-node by the
extraction LLM and are only present on SOME nodes of a label, never all of
them. Check the {schema} block above for which named properties actually
occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  Query         -> business_question, business_purpose, required_inputs, data_source, business_key, filter_criteria, time_range_logic, expected_output, calculation_rule
  OutputField   -> business_meaning, format_unit, example
  Table         -> model_name, business_name, description, database, schema, business_key, granularity
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  BusinessRule  -> rule_name, condition, description
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label, e.g.:
  WHERE toLower(q.id) CONTAINS toLower("shift oee lookup")
Never rely on a named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_QUERY]->(Query)
  (Query)-[:USES_DATA]->(Table)
  (Query)-[:SUPPORTS_ANALYSIS_OF]->(KPI)
  (Query)-[:REQUIRES]->(BusinessRule)
  (Query)-[:HAS_COMPONENT]->(OutputField)

KPI, Table and BusinessRule nodes here are the SAME nodes the kpi_definition,
data_model and business_rule skills extract (same label + same `id`
convention). This is the skill that answers "where/how do I actually get a
KPI's current value" — a question anchored on a KPI can traverse
`(KPI)<-[:SUPPORTS_ANALYSIS_OF]-(Query)-[:USES_DATA]->(Table)` to reach the
exact query, table, filter criteria and calculation rule that produce that
KPI's live value, even though the KPI's formula/variables and the query's
retrieval recipe were extracted from two different documents/skills.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a Query,
OutputField, KPI, Table, BusinessRule, ...) must return that entity's ENTIRE
connected subgraph in one query: match the anchor node, then expand outward
through ALL relationship types up to 3 hops, so nothing is missed regardless
of how the schema grows. Always shape the query this way:

  MATCH (anchor:Query) WHERE toLower(anchor.id) CONTAINS toLower("shift oee lookup")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (Query, OutputField, KPI, Table, BusinessRule), always keeping the `id`
  CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
