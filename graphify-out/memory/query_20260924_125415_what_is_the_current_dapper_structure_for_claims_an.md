---
type: "query"
date: "2026-09-24T12:54:15.061117+00:00"
question: "What is the current DAPPER structure for claims and hypotheses?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Hypothesis", "CausalStep", "EvidenceItem"]
---

# Q: What is the current DAPPER structure for claims and hypotheses?

## Answer

Expanded against graph vocabulary: hypothesis, causal, evidence, nanopub. The graph locates the older Hypothesis, CausalStep, Mechanism, EvidenceItem and nanopublication model, but omits the newer claims module and has stale source line numbers. Source verification at commit ebfc471 shows schema/claims.yaml defines Proposition, Claim, ClaimScore and CompositeClaim and is imported by dapper.yaml. Hypothesis does not reference Proposition and is not a Claim subclass. It separately stores statement, confidence, status, causal steps and evidence. ScientificAccount, BiologicalQuestion, Paragraph and the proposed Interpretation structure exist only in schema/docs/claims.md. Use current schema source for this inventory; do not infer absence from the old graph.

## Outcome

- Signal: useful

## Source Nodes

- Hypothesis
- CausalStep
- EvidenceItem