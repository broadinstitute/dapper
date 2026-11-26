#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "rdflib", "linkml-runtime"]
# ///
"""Cross-record scientific-content checks and an authored-text paragraph renderer.

    uv run tools/scientific_claims.py examples/example_scientific_account.yaml

This assembles supplied text; it does not infer scientific conclusions. Use the
provenance linter for complete schema, identifier, and provenance validation.
"""
from __future__ import annotations

import argparse
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "identity"))
from dapper_identity import DOC_GROUPS, load_schema


def index_document(document: dict) -> dict[str, tuple[str, dict]]:
    return {node["id"]: (cls, node)
            for group, cls in DOC_GROUPS.items()
            for node in (document.get(group) or [])
            if isinstance(node, dict) and isinstance(node.get("id"), str)}


def _refs(node: dict, field: str) -> list[str]:
    value = node.get(field)
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


@lru_cache(maxsize=None)
def _schema():
    return load_schema()


@lru_cache(maxsize=None)
def _accepts(expected: str, actual: str | None) -> bool:
    """A reference to `expected` accepts it or any subclass (a CausalLink is a
    Proposition; a MechanisticModel is an ExplanatoryModel)."""
    if actual is None:
        return False
    if actual == expected:
        return True
    return expected in _schema().class_ancestors(actual)


def _find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """One directed cycle as a node list (first node repeated), or None."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(u: str) -> list[str] | None:
        state[u] = 1
        stack.append(u)
        for v in sorted(edges.get(u, ())):
            if state.get(v) == 1:
                return stack[stack.index(v):] + [v]
            if not state.get(v):
                found = visit(v)
                if found:
                    return found
        state[u] = 2
        stack.pop()
        return None

    for u in sorted(edges):
        if not state.get(u):
            found = visit(u)
            if found:
                return found
    return None


def check_causal_graph(nid: str, graph: dict,
                       nodes: dict[str, tuple[str, dict]]) -> list[tuple[str, str]]:
    """A graph's links stay inside its variable set, appear once, and form a
    DAG unless the graph declares feedback."""
    problems = []
    variables = set(_refs(graph, "variables"))
    edges: dict[str, set[str]] = {}
    seen = set()
    for i, entry in enumerate(graph.get("links") or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("link"), str):
            continue
        where, ref = f"{nid}.links[{i}]", entry["link"]
        if ref in seen:
            problems.append((where, f"{ref} appears more than once in this graph"))
        seen.add(ref)
        cls, link = nodes.get(ref, (None, {}))
        if not _accepts("CausalLink", cls):
            problems.append((where, f"{ref} must resolve to CausalLink; found {cls or 'no local record'}"))
            continue
        for mechanism in _refs(entry, "via_mechanism"):
            if not _accepts("Mechanism", nodes.get(mechanism, (None, {}))[0]):
                problems.append((where, f"via_mechanism {mechanism} must resolve to Mechanism"))
        cause, effect = link.get("cause"), link.get("effect")
        for end in (cause, effect):
            if isinstance(end, str) and end not in variables:
                problems.append((where, f"{end} is not in this graph's variables"))
        if isinstance(cause, str) and isinstance(effect, str):
            edges.setdefault(cause, set()).add(effect)
    cycle = _find_cycle(edges)
    if cycle and graph.get("has_feedback") is not True:
        problems.append((nid, "directed cycle without has_feedback: " + " -> ".join(cycle)))
    if not cycle and graph.get("has_feedback") is True:
        problems.append((nid, "has_feedback is true but the graph has no directed cycle"))
    return problems


def check_scientific_content(nodes: dict[str, tuple[str, dict]]) -> list[tuple[str, str]]:
    """Return (location, problem) pairs; schema validation checks record shapes."""
    problems = []
    targets = {
        "Proposition": {"explanatory_model": "ExplanatoryModel"},
        "CausalLink": {"explanatory_model": "ExplanatoryModel",
                       "cause": "CausalVariable", "effect": "CausalVariable"},
        "CausalGraph": {"variables": "CausalVariable"},
        "MechanisticModel": {"variables": "CausalVariable"},
        "Claim": {"proposition": "Proposition", "has_score": "ClaimScore", "has_evidence": "EvidenceItem"},
        "ScientificAccount": {"framing": "Framing", "component_claims": "Claim",
                              "conclusion_claims": "Claim", "explanatory_model": "ExplanatoryModel"},
        "Hypothesis": {"proposition": "Proposition"},
        "EvidenceItem": {"source_claims": "Claim", "target_proposition": "Proposition",
                         "explanatory_model": "ExplanatoryModel"},
        "Paragraph": {"scientific_account": "ScientificAccount"},
    }
    for nid, (cls, node) in nodes.items():
        for field, expected in targets.get(cls, {}).items():
            refs = _refs(node, field)
            if len(refs) != len(set(refs)):
                problems.append((f"{nid}.{field}", "references must be distinct"))
            for ref in refs:
                actual = nodes.get(ref, (None, {}))[0]
                if not _accepts(expected, actual):
                    problems.append((f"{nid}.{field}", f"{ref} must resolve to {expected}; found {actual or 'no local record'}"))
        if cls == "ScientificAccount":
            if not _refs(node, "framing"):
                problems.append((nid, "framing needs at least one Question, KnowledgeGap or Hypothesis"))
            members = set(_refs(node, "component_claims"))
            conclusions = set(_refs(node, "conclusion_claims"))
            if not conclusions <= members:
                problems.append((nid, "conclusion_claims must be a subset of component_claims"))
            if not members - conclusions:
                problems.append((nid, "an account needs at least one claim outside its closing conclusions"))
        if cls == "Claim":
            for ref in _refs(node, "has_evidence"):
                evidence = nodes.get(ref, (None, {}))[1]
                target = evidence.get("target_proposition")
                if target and target != node.get("proposition"):
                    problems.append((nid, f"evidence {ref} targets a different proposition"))
        if cls == "Paragraph":
            problems.extend(check_citation_occurrences(nid, node, nodes))
        if _accepts("CausalGraph", cls):
            problems.extend(check_causal_graph(nid, node, nodes))
        if cls == "CausalLink":
            for field in ("relation", "subject_entity", "object_entity"):
                if field in node:
                    problems.append((f"{nid}.{field}", "a CausalLink states its structure with "
                                     "cause, effect and causal_relation, not " + field))

    # Evidence uses must not make a Claim depend on itself, directly or indirectly.
    dependencies = {nid: {source for e in _refs(node, "has_evidence")
                         for source in _refs(nodes.get(e, (None, {}))[1], "source_claims")}
                    for nid, (cls, node) in nodes.items() if cls == "Claim"}
    state = {}

    def visit(nid):
        if state.get(nid) == 1:
            problems.append((nid, "circular evidential support between claims"))
            return
        if state.get(nid) == 2:
            return
        state[nid] = 1
        for source in sorted(dependencies.get(nid, set())):
            visit(source)
        state[nid] = 2

    for nid in dependencies:
        visit(nid)
    return problems


def check_citation_occurrences(nid: str, paragraph: dict,
                               nodes: dict[str, tuple[str, dict]]) -> list[tuple[str, str]]:
    """Check local targets and Unicode code-point spans, independently of style.

    Schema validation checks field types. Registry availability, authorization,
    and whether the prose faithfully represents the cited object need separate
    application checks; a local graph cannot establish them.
    """
    problems = []
    text = paragraph.get("text")
    seen = set()
    for i, occurrence in enumerate(paragraph.get("citations") or []):
        where = f"{nid}.citations[{i}]"
        if not isinstance(occurrence, dict):
            continue
        target = occurrence.get("target_id")
        if not isinstance(target, str):
            continue
        cls = nodes.get(target, (None, {}))[0]
        if cls not in {"Claim", "Question", "KnowledgeGap"}:
            problems.append((where, "citation target must resolve to Claim, Question, or KnowledgeGap; "
                             f"found {cls or 'no local record'}"))
        start, end = occurrence.get("start"), occurrence.get("end")
        if type(start) is not int or type(end) is not int or not isinstance(text, str):
            continue
        if not 0 <= start < end <= len(text):
            problems.append((where, "citation span must satisfy 0 <= start < end <= text length (Unicode code points)"))
        elif "exact_text" in occurrence and occurrence["exact_text"] != text[start:end]:
            problems.append((where, "exact_text does not match the cited span"))
        revision = occurrence.get("citation_metadata_revision")
        if type(revision) is int:
            key = (target, revision, start, end)
            if key in seen:
                problems.append((where, "duplicate citation occurrence"))
            seen.add(key)
    return problems


def assemble_cited_text(segments: list[dict]) -> dict:
    """Join authored segments with spaces and calculate citation offsets.

    Each segment has text and an optional citations list containing target_id and
    citation_metadata_revision. References from render_account are not citations:
    callers must explicitly select citable targets and known registry revisions.
    No normalization is performed after offsets are calculated.
    """
    texts, citations, offset = [], [], 0
    for segment in segments:
        text = segment["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("each segment needs nonblank text")
        if texts:
            offset += 1
        for citation in segment.get("citations") or []:
            citations.append({"target_id": citation["target_id"],
                              "citation_metadata_revision": citation["citation_metadata_revision"],
                              "start": offset, "end": offset + len(text), "exact_text": text})
        texts.append(text)
        offset += len(text)
    return {"text": " ".join(texts), "citations": citations}


def render_account(document: dict, account_id: str | None = None) -> list[dict]:
    """Return ordered text segments with source references for review.

    Only authored text and explicitly labelled assessment metadata are rendered.
    No hypothesis is silently asserted and no component scores are aggregated.
    """
    nodes = index_document(document)
    problems = check_scientific_content(nodes)
    if problems:
        raise ValueError("; ".join(f"{where}: {problem}" for where, problem in problems))
    accounts = [nid for nid, (cls, _) in nodes.items() if cls == "ScientificAccount"]
    if account_id is None:
        if len(accounts) != 1:
            raise ValueError("select an account id when the document does not contain exactly one account")
        account_id = accounts[0]
    if account_id not in accounts:
        raise ValueError("account id must identify a ScientificAccount")
    account = nodes[account_id][1]
    segments = []
    included_scopes = set()

    def add(role, text, *refs):
        if isinstance(text, str) and text.strip():
            text = " ".join(text.split())
            if text[-1] not in ".?!":
                text += "."
            segments.append({"role": role, "text": text, "references": list(refs)})

    for ref in _refs(account, "framing"):
        cls, framing = nodes[ref]
        if cls == "Hypothesis":
            proposition_ref = framing["proposition"]
            proposition = nodes[proposition_ref][1]
            add("hypothesis", "Hypothesis under investigation: "
                + (framing.get("text") or proposition["statement"]), ref, proposition_ref)
            if framing.get("scope"):
                add("framing_scope", "Hypothesis scope: " + framing["scope"], ref)
            scope = proposition.get("scope")
            if scope:
                add("scope", "Scope: " + scope, proposition_ref)
                included_scopes.add(scope)
        else:
            add("framing", framing["text"], ref)
            add("knowledge_gap", framing.get("gap_description"), ref)
            if framing.get("scope"):
                add("question_scope", "Question scope: " + framing["scope"], ref)
    add("context", account.get("context"), account_id)
    for assumption in account.get("assumptions") or []:
        add("assumption", "Assumption: " + assumption, account_id)

    def claim_segments(cid, role):
        claim = nodes[cid][1]
        proposition = nodes[claim["proposition"]][1]
        # A directional assessment must never fall back to asserting its target.
        text = claim.get("statement") or ("Assessment of the proposition: " + proposition["statement"])
        add(role, text, cid, claim["proposition"])
        scope = proposition.get("scope")
        if scope and scope not in included_scopes:
            add("scope", "Scope: " + scope, claim["proposition"])
            included_scopes.add(scope)
        if claim.get("direction"):
            add("assessment", "Assessment direction: " + claim["direction"].lower(), cid)
        for ref in claim.get("has_score") or []:
            score = nodes[ref][1]
            add("score", f"Reported {score['metric']}: {score['value']} ({score['score_kind'].lower()}). "
                + score["interpretation"], cid, ref)
        for ref in claim.get("has_evidence") or []:
            evidence = nodes[ref][1]
            if evidence.get("direction"):
                add("evidence_direction", "Evidence contribution: " + evidence["direction"].lower(), ref)
            add("interpretation", evidence.get("explanation"), cid, ref, *_refs(evidence, "source_claims"))
            add("evidence_context", evidence.get("context"), ref)
            for assumption in evidence.get("assumptions") or []:
                add("assumption", "Interpretation assumes: " + assumption, ref)

    conclusions = account.get("conclusion_claims") or []
    for cid in account["component_claims"]:
        if cid not in conclusions:
            claim_segments(cid, "claim")
    for cid in conclusions:
        claim_segments(cid, "conclusion")
    add("closing", account.get("closing_remarks"), account_id)
    return segments


def main():
    import json
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--account")
    parser.add_argument("--segments", action="store_true", help="show roles and source references as JSON")
    args = parser.parse_args()
    try:
        segments = render_account(yaml.safe_load(args.document.read_text()), args.account)
    except (ValueError, KeyError) as exc:
        parser.exit(1, f"Cannot render account: {exc}\n")
    print(json.dumps(segments, indent=2) if args.segments else " ".join(s["text"] for s in segments))


if __name__ == "__main__":
    main()
