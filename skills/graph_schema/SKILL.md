---
description: Reference-only master schema — the union of every allowed_nodes/allowed_relationships pair declared across skills/*/SKILL.md. Documents how the 11 separate per-section subgraphs interconnect into one graph. Never assigned to a document section by the per-section skill router; each section is still extracted using its OWN (narrower) skill schema.
allowed_nodes:
  - KnowledgeType
  - KPI
  - Formula
  - Variable
  - DataFeature
  - SemanticDefinition
  - BusinessRule
  - Table
  - Field
  - LineageFlow
  - Query
  - OutputField
  - DomainConcept
  - Policy
  - Report
  - ReportSection
  - SOP
  - Step
  - TrainingTopic
  - TroubleshootingCase
allowed_relationships:
  - [KnowledgeType, HAS_KPI, KPI]
  - [KPI, HAS_FORMULA, Formula]
  - [KPI, USES_VARIABLE, Variable]
  - [Variable, SOURCED_FROM, DataFeature]
  - [Formula, REFERENCES, Variable]
  - [Variable, HAS_SEMANTIC_DEFINITION, SemanticDefinition]
  - [DataFeature, MAPS_TO_TABLE, Table]
  - [DataFeature, MAPS_TO_FIELD, Field]
  - [KnowledgeType, HAS_RULE, BusinessRule]
  - [BusinessRule, GOVERNS, Table]
  - [BusinessRule, APPLIES_TO, KPI]
  - [BusinessRule, RELATED_TO, BusinessRule]
  - [KnowledgeType, HAS_TABLE, Table]
  - [Table, HAS_FIELD, Field]
  - [Table, RELATED_TO_KPI, KPI]
  - [Table, RELATED_TO_TABLE, Table]
  - [Field, COMPUTES_KPI, KPI]
  - [KnowledgeType, HAS_LINEAGE, LineageFlow]
  - [KPI, DERIVED_FROM, LineageFlow]
  - [Table, DERIVED_FROM, LineageFlow]
  - [Field, DERIVED_FROM, LineageFlow]
  - [LineageFlow, USES_DATA, Table]
  - [LineageFlow, USES_DATA, Field]
  - [KnowledgeType, HAS_QUERY, Query]
  - [Query, USES_DATA, Table]
  - [Query, SUPPORTS_ANALYSIS_OF, KPI]
  - [Query, REQUIRES, BusinessRule]
  - [Query, HAS_COMPONENT, OutputField]
  - [KnowledgeType, HAS_TERM, DomainConcept]
  - [DomainConcept, RELATED_TO, KPI]
  - [DomainConcept, RELATED_TO, Table]
  - [DomainConcept, RELATED_TO, BusinessRule]
  - [DomainConcept, RELATED_TO, DomainConcept]
  - [KnowledgeType, HAS_POLICY, Policy]
  - [Policy, GOVERNS, Table]
  - [Policy, APPLIES_TO, KPI]
  - [Policy, RELATED_TO, BusinessRule]
  - [Policy, REFERENCES_CONCEPT, DomainConcept]
  - [KnowledgeType, HAS_REPORT, Report]
  - [Report, HAS_COMPONENT, ReportSection]
  - [Report, SUPPORTS_ANALYSIS_OF, KPI]
  - [Report, USES_QUERY, Query]
  - [KnowledgeType, HAS_SOP, SOP]
  - [SOP, HAS_STEP, Step]
  - [Step, PRECEDES, Step]
  - [SOP, APPLIES_TO, KPI]
  - [SOP, REQUIRES, BusinessRule]
  - [SOP, RELATED_TO, DomainConcept]
  - [KnowledgeType, HAS_TOPIC, TrainingTopic]
  - [TrainingTopic, RELATED_TO, KPI]
  - [TrainingTopic, RELATED_TO, Table]
  - [TrainingTopic, RELATED_TO, BusinessRule]
  - [TrainingTopic, RELATED_TO, DomainConcept]
  - [TrainingTopic, RELATED_TO, SOP]
  - [KnowledgeType, HAS_CASE, TroubleshootingCase]
  - [TroubleshootingCase, AFFECTS, KPI]
  - [TroubleshootingCase, AFFECTS, Table]
  - [TroubleshootingCase, RELATED_TO, BusinessRule]
  - [TroubleshootingCase, RESOLVED_BY, SOP]
  - [TroubleshootingCase, DIAGNOSED_VIA, Query]
---

## Extraction Prompt

This skill has no ingestion-time role of its own — it is never assigned to a
document section by `graph_builder.py`'s per-section router (`select_skill`),
so no extraction ever happens under it directly. It exists purely as a single
place documenting how the OTHER 11 extraction skills' subgraphs interconnect,
since each of those skills is only ever shown its own narrower schema.

Every node label above other than `KnowledgeType` is a "bridge" label shared
by two or more skills (e.g. `KPI` is extracted by `kpi_definition`,
`business_rule`, `data_model`, `data_lineage`, `data_query_definition`,
`domain_concept`, `policy_compliance`, `report_definition`, `sop_procedure`,
`training_reference` and `troubleshooting` alike). Every skill is instructed
to reuse the EXACT same name text for these bridge entities that the node's
"owning" skill would use, so Neo4j's `MERGE`-based write (see
`graph_rag/neo4j_store.py::write_graph_documents`) unifies them into one node
per entity instead of creating per-skill duplicates. That shared-id
convention — not any relationship created by this skill — is what actually
interconnects the 11 subgraphs into one graph.

Most cross-skill pairs are only reachable by hopping through a shared bridge
node (e.g. `Report` and `Policy` both point at `KPI` but have no edge to each
other directly, so reaching one from the other costs 2 hops). Six pairs that
come up often enough to matter now also have a DIRECT edge, added to the
producing skill's OWN schema (extraction really creates them - this file only
documents them) so retrieval resolves them in ONE hop instead of two or three:

  (DataFeature)-[:MAPS_TO_TABLE]->(Table)         - kpi_definition
  (DataFeature)-[:MAPS_TO_FIELD]->(Field)          - kpi_definition
  (TroubleshootingCase)-[:RESOLVED_BY]->(SOP)      - troubleshooting
  (TroubleshootingCase)-[:DIAGNOSED_VIA]->(Query)  - troubleshooting
  (Policy)-[:REFERENCES_CONCEPT]->(DomainConcept)  - policy_compliance
  (Report)-[:USES_QUERY]->(Query)                  - report_definition

These close real structural gaps: previously a KPI's formula `Variable` only
referenced its source data via a flat `DataFeature.table`/`feature` STRING
property with no edge to the actual `Table`/`Field` node from `data_model`;
a `TroubleshootingCase`'s fix/diagnostic only existed as free text in its
`corrective_action`/`diagnostic_checks` properties with no edge to the real
`SOP`/`Query` node; and `Policy`/`Report` could only reach a `DomainConcept`/
`Query` by a 2-hop detour through a shared `KPI`.

## Retrieval Notes

Node ids across every skill are prefixed by type, e.g. `kpi:oee`,
`table:shift_oee_details_for_workcenter`,
`businessrule:oee_aggregation_rule`, `domainconcept:planned_production_time`,
`sop:unplanned_stop_handling`, `troubleshootingcase:machine_not_running`.
`id`, `knowledge_name`, `knowledge_type`, and `description` are the ONLY
properties guaranteed to exist on every node across every skill — each
extraction skill's LLM invents its own additional named properties per
node, so check the {schema} block above for which of those actually occur
on a label before relying on one; see each skill's own SKILL.md for its
label-specific optional property list.

This is the schema to consult when a question doesn't obviously belong to
one skill, or when it spans several (e.g. "why is OEE dropping and what SOP
handles it" touches `troubleshooting`, `kpi_definition` and `sop_procedure`
at once). Never hand-pick individual relationship types to traverse based on
the wording of the question — match the anchor entity by `id` (OR any named
property confirmed present in {schema}), then expand outward through ALL
relationship types/directions up to 3 hops, exactly as every individual
skill's Retrieval Notes describe:

  MATCH (anchor:__Entity__) WHERE toLower(anchor.id) CONTAINS toLower("oee")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

The generic `[*1..3]` expansion above still finds the six direct shortcut
edges listed above (they're just relationships like any other), so no
special-casing is required for correctness. But if the question is clearly
about ONLY one of those six specific relationships (e.g. "what query
diagnoses the machine-not-running case"), prefer a 1-hop query naming that
edge directly - it's faster and returns a smaller, more precise result than
expanding 3 hops in every direction:

  MATCH (anchor:TroubleshootingCase)-[:DIAGNOSED_VIA]->(q:Query)
  WHERE toLower(anchor.id) CONTAINS toLower("machine not running")
  RETURN q

- Replace the anchor `id` match with whatever entity the question names,
  regardless of which skill originally extracted it — a KPI anchor can reach
  its Formula/Variables (`kpi_definition`), the Table/Field that computes its
  live value (`data_model`), the Query that retrieves it
  (`data_query_definition`), the BusinessRule/Policy that governs it
  (`business_rule`/`policy_compliance`), the SOP that handles it
  (`sop_procedure`), the TroubleshootingCase it affects (`troubleshooting`),
  the Report/DomainConcept/TrainingTopic that references it, and its
  LineageFlow (`data_lineage`) — all in ONE `[*1..3]` expansion, because they
  are all the same connected graph.
- Use an undirected, untyped `-[*1..3]-` traversal (never naming
  `HAS_FORMULA`, `GOVERNS`, `AFFECTS`, etc. individually) so relationship
  types added by any skill are picked up automatically without editing this
  file.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
- `graph_rag/retrieval.py::structured_retriever` already implements this
  exact schema-agnostic `[*1..3]` expansion in Python against `__Entity__`
  nodes, so this file's Cypher is a reference for anyone hand-writing a
  query, not a requirement to change that code.
