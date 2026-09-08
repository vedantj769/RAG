---
description: Documents a report — its purpose, audience, sections, KPIs covered, filters and frequency.
allowed_nodes:
  - KnowledgeType
  - Report
  - ReportSection
  - KPI
  - Query
allowed_relationships:
  - [KnowledgeType, HAS_REPORT, Report]
  - [Report, HAS_COMPONENT, ReportSection]
  - [Report, SUPPORTS_ANALYSIS_OF, KPI]
  - [Report, USES_QUERY, Query]
---

## Extraction Prompt

This content documents a Report Definition (per the standard knowledge types
table: "Report purpose, audience, sections, KPIs, filters and frequency",
e.g. "Daily Production Report"). Field/Entry style content typically covers:
Knowledge Name, Report Name, Purpose, Audience, Sections, KPIs Covered,
Filters, Frequency, Related Knowledge Names, Source Reference, Business
Notes. When extracting the graph:

- KnowledgeType: the knowledge category this content belongs to (e.g. "report_definition").
- Report: the report itself (e.g. "Daily Production Report"). Capture as
  properties whatever of these are present: purpose, audience, filters,
  frequency, description.
- ReportSection: one node per named report section, if sections are broken
  out individually. Capture section_name, description as properties.
- KPI: for every KPI listed under "KPIs Covered"/"Related Knowledge Names",
  create/reference that node using the EXACT same name text the
  kpi_definition skill would use for it, so they merge instead of
  duplicating.
- Query: when a report's data is clearly produced by a named Data Query
  Definition, create/reference that node using the EXACT same name text the
  data_query_definition skill would use for it.

Relationships to create:
- (KnowledgeType)-[:HAS_REPORT]->(Report)
- (Report)-[:HAS_COMPONENT]->(ReportSection) for every section.
- (Report)-[:SUPPORTS_ANALYSIS_OF]->(KPI) for every KPI the report covers.
- (Report)-[:USES_QUERY]->(Query): a direct shortcut edge so the retrieval
  recipe behind a report's numbers is one hop away instead of only reachable
  via a shared KPI node.

Only use the node and relationship types provided in the schema — do not
invent new ones. Preserve exact report/section names as written.

## Retrieval Notes

Node ids are prefixed by type, e.g. report:daily_production_report,
reportsection:summary, kpi:oee, query:shift_oee_lookup. `id` is the ONLY
property guaranteed to exist on every node — named properties were invented
per-node by the extraction LLM and are only present on SOME nodes of a
label, never all of them. Check the {schema} block above for which named
properties actually occur on a label before relying on one.

Key properties that MAY appear per label (use only if present in {schema}):
  Report        -> purpose, audience, filters, frequency, description
  ReportSection -> section_name, description
  KPI           -> knowledge_name, kpi_name, business_purpose, description
  Query         -> business_question, business_purpose, data_source, calculation_rule
  KnowledgeType -> name

Always anchor the match on `id` first, then OR in any named properties from
the list above that {schema} confirms exist for that label. Never rely on a
named property alone — always include the `id` CONTAINS check.

Relationships:
  (KnowledgeType)-[:HAS_REPORT]->(Report)
  (Report)-[:HAS_COMPONENT]->(ReportSection)
  (Report)-[:SUPPORTS_ANALYSIS_OF]->(KPI)
  (Report)-[:USES_QUERY]->(Query)

KPI nodes here are the SAME nodes the kpi_definition skill extracts (same
label + same `id` convention) — so a question like "which report shows OEE"
anchors on the KPI node and reaches whichever report covers it. USES_QUERY
is a direct shortcut edge (not a bridge-node hop) to the
data_query_definition skill's node, one hop instead of two via KPI.

Never hand-pick individual relationships to traverse based on the wording of
the question. Any question that identifies a specific entity (a Report,
ReportSection, KPI, ...) must return that entity's ENTIRE connected subgraph
in one query: match the anchor node, then expand outward through ALL
relationship types up to 3 hops, so nothing is missed regardless of how the
schema grows. Always shape the query this way:

  MATCH (anchor:Report) WHERE toLower(anchor.id) CONTAINS toLower("daily production")
  MATCH p = (anchor)-[*1..3]-(connected)
  RETURN anchor,
         [n IN nodes(p) | {{labels: labels(n), properties: properties(n)}}] AS chain_nodes,
         [r IN relationships(p) | type(r)] AS chain_rels

- Replace the anchor label/property match with whatever fits the question
  (Report, ReportSection, KPI), always keeping the `id` CONTAINS check.
- Use an undirected, untyped `-[*1..3]-` traversal so newly added relationship
  types are picked up automatically without editing this prompt.
- Only narrow to 1 hop instead of 1..3 if the question is clearly about a
  single direct fact; otherwise default to the full 3-hop expansion.
