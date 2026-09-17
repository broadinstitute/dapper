---
type: "query"
date: "2026-09-16T01:39:27.105084+00:00"
question: "How do File, C2M2File, and DrsObject connect after this implementation?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["File", "C2M2File", "DrsObject"]
---

# Q: How do File, C2M2File, and DrsObject connect after this implementation?

## Answer

Expanded from graph vocabulary: file, drs, representation. C2M2File is_a File (schema/dapper.yaml line 2170). File.drs_representation is an unhashable relationship whose description references DrsObject (line 2156); formal range remains uriorcurie. DrsObject stays a separate HashableNode (line 2023). Generic file locations and DRS registrations do not alter File identity. All 65 classes, 14 enums, 256 attributes and 9 global slots have deterministic coverage in the index.

## Outcome

- Signal: useful

## Source Nodes

- File
- C2M2File
- DrsObject