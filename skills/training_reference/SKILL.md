---
description: Documents training/reference material — a topic, its instructional content, examples, common questions, and related KPIs, tables, rules, concepts and procedures.
allowed_nodes:
  - KnowledgeType
  - TrainingTopic
  - KPI
  - Table
  - BusinessRule
  - DomainConcept
  - SOP
allowed_relationships:
  - [KnowledgeType, HAS_TOPIC, TrainingTopic]
  - [TrainingTopic, RELATED_TO, KPI]
  - [TrainingTopic, RELATED_TO, Table]
  - [TrainingTopic, RELATED_TO, BusinessRule]
  - [TrainingTopic, RELATED_TO, DomainConcept]
  - [TrainingTopic, RELATED_TO, SOP]
---

## Extraction Prompt

This content documents Training/Reference material (template section 13):
Knowledge Name, Topic, Purpose, Audience, Concept/Instruction, Examples,
Common Questions, Related Knowledge Names, Source Reference, Business Notes.
When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "training_reference").
- TrainingTopic: the topic itself (e.g. "Operator Training"). Capture as
  properties whatever of these are present: purpose, audience, concept,
  examples, common_questions.
- KPI / Table / BusinessRule / DomainConcept / SOP: for every name under
  "Related Knowledge Names" that is clearly one of these, create/reference
  that node using the EXACT same name text the owning skill (kpi_definition /
  data_model / business_rule / domain_concept / sop_procedure) would use for
  it, so they merge instead of creating duplicates.

Relationships to create:
- (KnowledgeType)-[:HAS_TOPIC]->(TrainingTopic)
- (TrainingTopic)-[:RELATED_TO]->(KPI) / (Table) / (BusinessRule) /
  (DomainConcept) / (SOP) for every name under "Related Knowledge Names".

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact topic/instruction text as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. trainingtopic:operator_training,
kpi:oee, table:shift_oee_details_for_workcenter,
businessrule:oee_aggregation_rule, domainconcept:planned_production_time,
sop:unplanned_stop_handling. `id` is the ONLY property guaranteed to exist on
every node — named properties were invented per-node by the extraction LLM
and are only present on SOME nodes of a label, never all of them. Check the
{schema} block above for which named properties actually occur on a label
before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  TrainingTopic -> purpose, audience, concept, examples, common_questions
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  Table         -> model_name, business_name, description, database, schema
  BusinessRule  -> rule_name, condition, description
  DomainConcept -> term, definition
  SOP           -> purpose, applicable_area, expected_outcome
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label. Never rely on a
named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_TOPIC]->(TrainingTopic)
  (TrainingTopic)-[:RELATED_TO]->(KPI)
  (TrainingTopic)-[:RELATED_TO]->(Table)
  (TrainingTopic)-[:RELATED_TO]->(BusinessRule)
  (TrainingTopic)-[:RELATED_TO]->(DomainConcept)
  (TrainingTopic)-[:RELATED_TO]->(SOP)

KPI, Table, BusinessRule, DomainConcept and SOP nodes here are the SAME nodes
the kpi_definition, data_model, business_rule, domain_concept and
sop_procedure skills extract (same label + same `id` convention) — so a
question like "is there training material about OEE" anchors on the KPI node
and reaches whichever training topic relates to it.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a
TrainingTopic, KPI, Table, ...) must return that entity's ENTIRE connected
subgraph in one query: match the anchor node, then expand outward through ALL
relationship types up to 3 hops, so nothing is missed regardless of how the
schema grows. Always shape the query this way:

  MATCH (anchor:TrainingTopic) WHERE toLower(anchor.id) CONTAINS toLower("operator training")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (TrainingTopic, KPI, Table, BusinessRule, DomainConcept, SOP), always
  keeping the `id` CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
