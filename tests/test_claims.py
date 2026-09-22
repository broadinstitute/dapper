"""Claim validation, compositional identity, and both branches of provenance."""
from copy import deepcopy
import importlib.util
import json

import pytest
import yaml
from jsonschema import Draft202012Validator
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from conftest import REPO_ROOT
from dapper_identity import DOC_GROUPS, assign_ids, compute_id, verify


@pytest.fixture(scope="module")
def claim_schema():
    return json.loads(JsonSchemaGenerator(str(REPO_ROOT / "schema/dapper.yaml")).serialize())


@pytest.fixture
def claim_example():
    return yaml.safe_load((REPO_ROOT / "schema/examples/example_pigean_claims.yaml").read_text())


def errors(schema, cls, node):
    return list(Draft202012Validator({**schema, "$ref": f"#/$defs/{cls}"}).iter_errors(node))


def test_all_worked_records_validate_against_imported_schema(claim_schema, claim_example):
    checked = 0
    for group, cls in DOC_GROUPS.items():
        for node in claim_example.get(group, []):
            assert not errors(claim_schema, cls, node), (cls, errors(claim_schema, cls, node))
            checked += 1
    assert checked == 23


@pytest.mark.parametrize("kind", ["PROBABILITY", "POSTERIOR_PROBABILITY"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_probabilities_reject_out_of_range_values(claim_schema, claim_example, kind, value):
    score = claim_example["claim_scores"][0]
    score.update(score_kind=kind, value=value)
    assert errors(claim_schema, "ClaimScore", score)


@pytest.mark.parametrize("kind,value", [("PROBABILITY", 0.0), ("POSTERIOR_PROBABILITY", 1.0),
                                        ("EFFECT_ESTIMATE", -2.5), ("LOADING", 8.4), ("SCORE", 12.0)])
def test_scores_keep_their_own_scales(claim_schema, claim_example, kind, value):
    score = claim_example["claim_scores"][0]
    score.update(score_kind=kind, value=value)
    assert not errors(claim_schema, "ClaimScore", score)


@pytest.mark.parametrize("field", ["proposition", "was_generated_by", "was_attributed_to"])
def test_claim_cannot_lose_its_target_or_provenance(claim_schema, claim_example, field):
    claim = claim_example["claims"][0]
    del claim[field]
    assert errors(claim_schema, "Claim", claim)


@pytest.mark.parametrize("field", ["subject_entity", "relation", "object_entity"])
def test_partial_structured_proposition_is_rejected(claim_schema, claim_example, field):
    proposition = claim_example["propositions"][0]
    del proposition[field]
    assert errors(claim_schema, "Proposition", proposition)


@pytest.mark.parametrize("change", [{"component_claims": []}, {"component_claims": ["urn:one"]},
                                    {"composition": "CAUSAL_CHAIN"}])
def test_composites_require_multiple_components_and_explicit_semantics(claim_schema, claim_example, change):
    composite = claim_example["composite_claims"][0]
    composite.update(change)
    assert errors(claim_schema, "CompositeClaim", composite)


def test_changed_assessment_preserves_propositions_but_changes_dependent_claims(sv, claim_example):
    before = deepcopy(claim_example)
    claim_example["claim_scores"][0]["value"] = 0.5
    assign_ids(claim_example, sv)
    assert claim_example["propositions"] == before["propositions"]
    assert claim_example["claims"][0]["id"] != before["claims"][0]["id"]
    assert claim_example["claims"][1:] == before["claims"][1:]
    assert claim_example["composite_claims"][0]["id"] != before["composite_claims"][0]["id"]
    assert verify(claim_example, sv) == []
    reminted = deepcopy(claim_example)
    assign_ids(claim_example, sv)
    assert claim_example == reminted


def test_publication_back_reference_does_not_change_claim_identity(sv, claim_example):
    claim = claim_example["claims"][0]
    original = compute_id(claim, "Claim", sv)
    claim["asserted_in"] = ["urn:example:publication"]
    assert compute_id(claim, "Claim", sv) == original


def test_worked_composite_reaches_both_raw_inputs_without_combining_scores(sv, claim_example):
    nodes = {n["id"]: (cls, n) for g, cls in DOC_GROUPS.items() for n in claim_example.get(g, [])}
    composite = claim_example["composite_claims"][0]
    assert len(set(composite["component_claims"])) == 3
    assert "has_score" not in composite
    for claim_id in composite["component_claims"]:
        assert nodes[claim_id][0] == "Claim"
        claim = nodes[claim_id][1]
        assert nodes[claim["proposition"]][0] == "Proposition"
        assert nodes[claim["has_score"][0]][0] == "ClaimScore"

    deps = {nid: set() for nid in nodes}
    for nid, (cls, node) in nodes.items():
        for slot in sv.class_induced_slots(cls):
            if slot.is_a != "relationship":
                continue
            raw = node.get(slot.name)
            for ref in raw if isinstance(raw, list) else [raw]:
                if ref in nodes:
                    deps[nid].add(ref)
                elif isinstance(ref, str) and ref.startswith("dapper:"):
                    pytest.fail(f"Dangling reference: {ref}")
    for group in ("used_edges", "was_generated_by_edges"):
        for edge in claim_example[group]:
            assert edge["subject"] in nodes and edge["object"] in nodes
            deps[edge["subject"]].add(edge["object"])
    reached, pending = set(), [composite["id"]]
    while pending:
        nid = pending.pop()
        if nid not in reached:
            reached.add(nid)
            pending.extend(deps[nid])
    filenames = {nodes[nid][1].get("filename") for nid in reached}
    assert {"expression.tsv", "raw-gwas.tsv", "processed-gwas.tsv", "gene-set-b.gmt"} <= filenames


def test_portal_loads_claim_module_and_renders_composition():
    spec = importlib.util.spec_from_file_location("claims_portal", REPO_ROOT / "portal/build.py")
    portal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portal)
    schema = portal.load_schema()
    assert {"proposition", "component_claims", "was_generated_by"} <= set(schema["CompositeClaim"]["attributes"])
    example = next(g for g in portal.GRAPH_DOCS if g["key"] == "pigean_claims")
    graph = portal.build_graph(example)
    assert example["start"] in {n["id"] for n in graph["nodes"]}
    assert sum(e["predicate"] == "dapper:component_claims" for e in graph["edges"]) == 3
