---
description: Documents a Standard Operating Procedure — its purpose, prerequisites, ordered steps, expected outcomes, and related KPIs, rules and concepts.
allowed_nodes:
  - KnowledgeType
  - SOP
  - Step
  - KPI
  - BusinessRule
  - DomainConcept
allowed_relationships:
  - [KnowledgeType, HAS_SOP, SOP]
  - [SOP, HAS_STEP, Step]
  - [Step, PRECEDES, Step]
  - [SOP, APPLIES_TO, KPI]
  - [SOP, REQUIRES, BusinessRule]
  - [SOP, RELATED_TO, DomainConcept]
---

## Extraction Prompt

This content documents an SOP/Procedure (template section 9): Knowledge Name,
SOP Name, Purpose, Applicable Area/Product, Prerequisites, Warnings/Safety
Notes, Expected Outcome, Related Knowledge Names, Source Reference, Business
Notes — followed by a steps table (section 9.1: Step No., Action/Instruction,
Expected Result, Decision/Condition, Exception/Escalation). When extracting
the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "sop_procedure").
- SOP: the procedure itself (e.g. "Unplanned Stop Handling"). Capture as
  properties whatever of these are present: purpose, applicable_area,
  prerequisites, warnings, expected_outcome.
- Step: one node per row of the steps table. Capture step_no, action,
  expected_result, decision_condition, exception_escalation as properties.
  Every step row belongs to the ONE SOP described earlier in this same
  content, even though the SOP metadata and the steps are two separate
  physical tables in the source document.
- KPI / BusinessRule / DomainConcept: for every name under "Related Knowledge
  Names" that is clearly one of these, create/reference that node using the
  EXACT same name text the owning skill (kpi_definition / business_rule /
  domain_concept) would use for it, so they merge instead of duplicating.

Relationships to create:
- (KnowledgeType)-[:HAS_SOP]->(SOP)
- (SOP)-[:HAS_STEP]->(Step) for every step row.
- (Step)-[:PRECEDES]->(Step): link each step to the NEXT step by step_no, to
  preserve execution order.
- (SOP)-[:APPLIES_TO]->(KPI), (SOP)-[:REQUIRES]->(BusinessRule),
  (SOP)-[:RELATED_TO]->(DomainConcept): for names under "Related Knowledge Names".

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact step instructions as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. sop:unplanned_stop_handling, step:1,
kpi:oee, businessrule:oee_aggregation_rule,
domainconcept:planned_production_time. `id` is the ONLY property guaranteed
to exist on every node — named properties were invented per-node by the
extraction LLM and are only present on SOME nodes of a label, never all of
them. Check the {schema} block above for which named properties actually
occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  SOP           -> purpose, applicable_area, prerequisites, warnings, expected_outcome
  Step          -> step_no, action, expected_result, decision_condition, exception_escalation
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  BusinessRule  -> rule_name, condition, description
  DomainConcept -> term, definition
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label, e.g.:
  WHERE toLower(s.id) CONTAINS toLower("unplanned stop")
Never rely on a named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_SOP]->(SOP)
  (SOP)-[:HAS_STEP]->(Step)
  (Step)-[:PRECEDES]->(Step)
  (SOP)-[:APPLIES_TO]->(KPI)
  (SOP)-[:REQUIRES]->(BusinessRule)
  (SOP)-[:RELATED_TO]->(DomainConcept)

KPI, BusinessRule and DomainConcept nodes here are the SAME nodes the
kpi_definition, business_rule and domain_concept skills extract (same label +
same `id` convention) — so a question like "what's the procedure for X KPI"
anchors on the KPI node and traverses to the SOP that applies to it.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (an SOP, Step,
KPI, ...) must return that entity's ENTIRE connected subgraph in one query:
match the anchor node, then expand outward through ALL relationship types up
to 3 hops, so nothing is missed regardless of how the schema grows. Always
shape the query this way:

  MATCH (anchor:SOP) WHERE toLower(anchor.id) CONTAINS toLower("unplanned stop")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (SOP, Step, KPI, BusinessRule, DomainConcept), always keeping the `id`
  CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact (e.g. "what is step 3"); otherwise default to the full
  3-hop expansion.
