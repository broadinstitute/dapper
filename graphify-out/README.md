# DAPPER knowledge graph

Open `graph.html` to browse the graph, or use these commands from the repository root:

```sh
graphify explain C2M2File
graphify explain File.drs_representation
graphify path C2M2File File
graphify query "file drs representation" --budget 3000
```

The index contains 1,007 nodes and 2,809 connections. It covers every declaration
in the current schema: 65 classes, 9 global slots, 256 attributes, 36 slot
specializations, 14 enums, and 84 permissible values. Inheritance, mixins,
declared and inherited slots, ranges, ontology mappings, and enum meanings have
source line references. Textual class mentions are labeled `mentions_class`,
so they are distinguishable from formal LinkML range constraints.
Source paths are relative to the repository root so the shared index is portable.

`graph.json` is the navigable projection; `extraction.json` retains the original
statements. Where a node pair has several statements, `relations` and `evidence`
preserve them and their directions. The default graph is undirected for traversal.
`GRAPH_REPORT.md` contains community scores, scope limits, and estimated extraction
token counts. `graph-health.json` records the integrity checks.

The stock code extractor does not index the five JSON fixture/vector files'
contents. It also leaves 69 unresolved code references; these are preserved in
`unresolved-code-references.json`, outside the navigable graph. Schema coverage is
complete. The HTML viewer loads vis-network from a CDN and therefore needs network
access; the JSON, report, and CLI queries work locally.

For schema updates, regenerate the deterministic fragment:

```sh
uv run --with pyyaml tools/graphify_schema.py
```

Then rerun the graphify skill, including `linkml-extraction.json` as a structural
fragment with priority over documentation mentions. Regenerating this fragment
alone does not update `graph.json`. Keep the schema pass when rebuilding: generic
YAML/document extraction does not guarantee full class/slot/enum coverage.
