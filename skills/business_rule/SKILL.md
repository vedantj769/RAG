---
description: Documents a business rule — its condition, action/outcome, calculation, threshold, exceptions and priority, and which KPIs/tables it governs or applies to.
allowed_nodes:
  - KnowledgeType
  - BusinessRule
  - KPI
  - Table
allowed_relationships:
  - [KnowledgeType, HAS_RULE, BusinessRule]
  - [BusinessRule, GOVERNS, Table]
  - [BusinessRule, APPLIES_TO, KPI]
  - [BusinessRule, RELATED_TO, BusinessRule]
---

## Extraction Prompt

This content documents a Business Rule (template section 6): Knowledge Name,
Rule Name, Description, Condition, Action/Outcome, Calculation/Formula,
Threshold/Limit, Exception/Exclusion, Priority, Applicable Product/Domain,
Applicable Hierarchy, Effective Date, Related Knowledge Names, Source
Reference, Business Notes. When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "business_rule").
- BusinessRule: the rule itself (its Knowledge Name/Rule Name, e.g. "OEE
  Aggregation Rule", "Long Stop Classification"). Capture as properties
  whatever of these are present: condition, action, calculation, threshold,
  exception, priority, applicable_domain, applicable_hierarchy,
  effective_date, description. Use the EXACT same name text the data_model
  skill's "Related Business Rules" would use for this rule, so both merge
  into the same node instead of creating duplicates.
- KPI / Table: for every name under "Related Knowledge Names" (or implied by
  "Applicable Product/Domain") that is clearly a KPI or a data model table,
  create that node using the EXACT same name text the kpi_definition /
  data_model skills would use for it, so they merge with those instead of
  creating duplicates. Do not invent a KPI/Table that isn't named in the text.

Relationships to create:
- (KnowledgeType)-[:HAS_RULE]->(BusinessRule)
- (BusinessRule)-[:GOVERNS]->(Table): when the rule's condition/action clearly
  applies to a specific table/entity's data.
- (BusinessRule)-[:APPLIES_TO]->(KPI): when the rule affects how a KPI is
  calculated or interpreted (e.g. an aggregation or exclusion rule for OEE).
- (BusinessRule)-[:RELATED_TO]->(BusinessRule): for any other rule named
  under "Related Knowledge Names".

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact rule names and formulas as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. businessrule:oee_aggregation_rule,
kpi:oee, table:shift_oee_details_for_workcenter. `id` is the ONLY property
guaranteed to exist on every node — named properties were invented per-node
by the extraction LLM and are only present on SOME nodes of a label, never
all of them. Check the {schema} block above for which named properties
actually occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  BusinessRule  -> rule_name, condition, action, calculation, threshold, exception, priority, applicable_domain, applicable_hierarchy, effective_date, description
  KPI           -> knowledge_name, kpi_name, business_purpose, unit, calculation_frequency, description
  Table         -> model_name, business_name, description, database, schema, business_key, granularity
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label, e.g.:
  WHERE toLower(r.id) CONTAINS toLower("long stop")
     OR toLower(r.rule_name) CONTAINS toLower("long stop")
Never rely on a named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_RULE]->(BusinessRule)
  (BusinessRule)-[:GOVERNS]->(Table)
  (BusinessRule)-[:APPLIES_TO]->(KPI)
  (BusinessRule)-[:RELATED_TO]->(BusinessRule)

KPI and Table nodes here are the SAME nodes the kpi_definition and data_model
skills extract (same label + same `id` convention), so a query anchored on a
BusinessRule (or on a KPI/Table that a rule governs) can traverse across all
three skills' subgraphs in one query without knowing in advance which skill
"owns" the data.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a BusinessRule,
KPI, Table, ...) must return that entity's ENTIRE connected subgraph in one
query: match the anchor node, then expand outward through ALL relationship
types up to 3 hops, so nothing is missed regardless of how the schema grows.
Always shape the query this way:

  MATCH (anchor:BusinessRule) WHERE toLower(anchor.id) CONTAINS toLower("long stop")
     OR toLower(anchor.rule_name) CONTAINS toLower("long stop")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (BusinessRule, KPI, Table), always keeping the `id` CONTAINS check and
  OR-ing in only the named properties {schema} confirms exist for that label.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
