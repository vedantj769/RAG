---
description: Not a graph-extraction skill — after the vector DB + graph DB knowledge has already been combined into an answer, decides whether that answer is sufficient for root cause analysis or whether live/actual values from the SQL operational database are still required. Used as a gate after synthesize_answer(), not before retrieval.
allowed_nodes: []
allowed_relationships: []
---

## Extraction Prompt

This skill has no ingestion-time role — it is never assigned to a document
chunk by classifier.classify_texts(), so no extraction ever happens under it.
It exists only for its Retrieval Notes, consulted after an answer has already
been synthesized from the vector DB + graph DB.

## Retrieval Notes

You are given a question and the answer already produced by combining the
vector DB (document chunks) and the graph DB (KPI/Table/Field/BusinessRule/
DomainConcept definitions, formulas, relationships). Decide whether that
answer is ENOUGH to complete root cause analysis, or whether the actual,
current operational data (real numbers from the SQL production database) is
still needed to finish the analysis.

Respond "not needed" when the combined answer already fully satisfies the
question, e.g.:
- The question only asks for a definition, formula, meaning, schema detail,
  or relationship (e.g. "what is planned production time", "what table is
  OEE stored in", "which fields compute the Quality KPI") — this is
  knowledge about the data, not the data itself, so no SQL lookup is needed,
  REGARDLESS of whether the combined answer fully or only partially answered it.

Respond "sql needed" when finishing the analysis requires actual current
values, not just definitions, e.g.:
- The question asks WHY something happened, what caused a specific stop/
  defect/loss, or asks to diagnose/troubleshoot a real incident.
- The question asks for a specific value, trend, count, or comparison over
  actual production data (e.g. "what was yesterday's OEE for Line 3", "how
  many long stops happened this shift", "which work order had the most
  downtime").
- The combined answer identifies WHICH table/field holds the relevant data
  (from the graph) but the question is really asking for that data's actual
  value, not just where it lives.
- The combined answer says "I don't know" / found nothing AND the question
  is about a real event/value/incident rather than a definition — the graph
  and vector DB only ever contain definitions/schema/documentation, never
  live production data, so "I don't know" on an incident question means SQL
  is the ONLY place that could still have the answer, not a dead end.

When in doubt, prefer "sql needed" for anything that smells like an
incident/root-cause question rather than a pure definition question — a
wasted SQL lookup is cheaper than an RCA that stops short of real evidence.

Reply with ONLY one of these two exact phrases, nothing else: "sql needed"
or "not needed".
