---
description: Documents a troubleshooting case — symptom, possible causes, diagnostics, corrective action, escalation, and which KPIs/tables/rules it affects.
allowed_nodes:
  - KnowledgeType
  - TroubleshootingCase
  - KPI
  - Table
  - BusinessRule
allowed_relationships:
  - [KnowledgeType, HAS_CASE, TroubleshootingCase]
  - [TroubleshootingCase, AFFECTS, KPI]
  - [TroubleshootingCase, AFFECTS, Table]
  - [TroubleshootingCase, RELATED_TO, BusinessRule]
---

## Extraction Prompt

This content documents Troubleshooting knowledge (template section 10):
Knowledge Name, Problem/Symptom, Description, Possible Cause(s), Diagnostic
Checks, Corrective Action, Escalation, Expected Outcome, Related Knowledge
Names, Source Reference, Business Notes. When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "troubleshooting").
- TroubleshootingCase: the problem/symptom itself (e.g. "Machine Not
  Running"). Capture as properties whatever of these are present:
  symptom, description, possible_causes, diagnostic_checks,
  corrective_action, escalation, expected_outcome.
- KPI / Table / BusinessRule: for every name under "Related Knowledge Names"
  that is clearly one of these, create/reference that node using the EXACT
  same name text the owning skill (kpi_definition / data_model /
  business_rule) would use for it, so they merge instead of duplicating.

Relationships to create:
- (KnowledgeType)-[:HAS_CASE]->(TroubleshootingCase)
- (TroubleshootingCase)-[:AFFECTS]->(KPI): when the symptom impacts a KPI's
  value or calculation.
- (TroubleshootingCase)-[:AFFECTS]->(Table): when the symptom relates to data
  in a specific table.
- (TroubleshootingCase)-[:RELATED_TO]->(BusinessRule): when a rule governs
  how the symptom/case is classified or handled.

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact symptom/cause/action text as written.

## Retrieval Notes

Node ids are prefixed by type, e.g.
troubleshootingcase:machine_not_running, kpi:oee,
table:shift_oee_details_for_workcenter, businessrule:oee_aggregation_rule.
`id` is the ONLY property guaranteed to exist on every node — named
properties were invented per-node by the extraction LLM and are only present
on SOME nodes of a label, never all of them. Check the {schema} block above
for which named properties actually occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  TroubleshootingCase -> symptom, description, possible_causes, diagnostic_checks, corrective_action, escalation, expected_outcome
  KPI                 -> knowledge_name, kpi_name, business_purpose, description
  Table               -> model_name, business_name, description, database, schema
  BusinessRule        -> rule_name, condition, description
  KnowledgeType       -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label, e.g.:
  WHERE toLower(t.id) CONTAINS toLower("machine not running")
     OR toLower(t.symptom) CONTAINS toLower("machine not running")
Never rely on a named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_CASE]->(TroubleshootingCase)
  (TroubleshootingCase)-[:AFFECTS]->(KPI)
  (TroubleshootingCase)-[:AFFECTS]->(Table)
  (TroubleshootingCase)-[:RELATED_TO]->(BusinessRule)

KPI, Table and BusinessRule nodes here are the SAME nodes the kpi_definition,
data_model and business_rule skills extract (same label + same `id`
convention) — so a question like "why is OEE dropping" anchors on the KPI
node and reaches whichever troubleshooting case affects it.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a
TroubleshootingCase, KPI, Table, ...) must return that entity's ENTIRE
connected subgraph in one query: match the anchor node, then expand outward
through ALL relationship types up to 3 hops, so nothing is missed regardless
of how the schema grows. Always shape the query this way:

  MATCH (anchor:TroubleshootingCase) WHERE toLower(anchor.id) CONTAINS toLower("machine not running")
     OR toLower(anchor.symptom) CONTAINS toLower("machine not running")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (TroubleshootingCase, KPI, Table, BusinessRule), always keeping the `id`
  CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
