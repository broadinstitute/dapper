"""DISMECH pathographs project onto DAPPER causal graphs and back without loss.

The fixture is synthetic but DISMECH-shaped: it exercises a feedback loop
inside one hypothesis group, an edge in two groups, the same edge both in and
out of a group, a Phenotype `sequelae` source, a target naming no node, a
Pathophysiology and a Phenotype that share a name, and edges without a
causal_link_type.
"""
import json

import pytest
from jsonschema import Draft202012Validator
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from conftest import SCHEMA
from dapper_identity import verify
from dismech_pathograph import edge_set, from_dismech, generated_statement, to_dismech
from scientific_claims import check_scientific_content, index_document

PAGE = "https://dismech.monarchinitiative.org/pages/disorders/Synthetic_Disease.html"

DISEASE = {
    "name": "Synthetic Disease",
    "pathophysiology": [
        {"name": "Plaque Formation", "downstream": [
            {"target": "Neuroinflammation", "description": "Plaques activate microglia.",
             "causal_link_type": "DIRECT", "hypothesis_groups": ["cascade_model"]},
            {"target": "Synapse Loss", "causal_link_type": "INDIRECT_KNOWN_INTERMEDIATES",
             "intermediate_mechanisms": ["oligomer toxicity"],
             "hypothesis_groups": ["cascade_model", "synaptic_model"]},
        ]},
        {"name": "Neuroinflammation", "downstream": [
            {"target": "Plaque Formation", "description": "Microglial cytokines promote plaque deposition.",
             "causal_link_type": "DIRECT", "hypothesis_groups": ["cascade_model"]},
            {"target": "Synapse Loss"},
            {"target": "Synapse Loss", "hypothesis_groups": ["synaptic_model"]},
        ]},
        {"name": "Seizures", "downstream": [{"target": "Unnamed Downstream State"}]},
    ],
    "phenotypes": [
        {"name": "Seizures", "sequelae": [{"target": "Cognitive Decline", "causal_link_type": "UNKNOWN"}]},
        {"name": "Cognitive Decline"},
    ],
}


@pytest.fixture(scope="module")
def projected(sv):
    return from_dismech(DISEASE, PAGE, sv)


def test_round_trip_keeps_every_edge(projected):
    assert edge_set(to_dismech(projected)) == edge_set(DISEASE)


def test_projection_is_valid_minted_dapper(projected, sv):
    assert verify(projected, sv) == []
    assert check_scientific_content(index_document(projected)) == []
    schema = json.loads(JsonSchemaGenerator(str(SCHEMA)).serialize())
    for cls, node in index_document(projected).values():
        errs = list(Draft202012Validator({**schema, "$ref": f"#/$defs/{cls}"}).iter_errors(node))
        assert not errs, (cls, errs[0].message)
    for edge in projected["corresponds_to_dismech_edges"]:
        errs = list(Draft202012Validator({**schema, "$ref": "#/$defs/CorrespondsToDismech"}).iter_errors(edge))
        assert not errs, errs[0].message
        assert edge["object"] == PAGE


def _models(projected):
    keys = {c["subject"]: c["entry_key"] for c in projected["corresponds_to_dismech_edges"]}
    return {keys[m["id"]]: m for m in projected["mechanistic_models"]}


def test_one_model_per_group_and_one_for_ungrouped_edges(projected):
    models = _models(projected)
    assert set(models) == {"cascade_model", "synaptic_model", "Synthetic Disease"}
    assert models["cascade_model"]["has_feedback"] is True
    assert "has_feedback" not in models["synaptic_model"]
    assert "has_feedback" not in models["Synthetic Disease"]


def test_an_edge_in_two_groups_is_one_link_in_two_models(projected):
    models = _models(projected)
    def links(model):
        return {e["link"] for e in model["links"]}
    shared = links(models["cascade_model"]) & links(models["synaptic_model"])
    assert len(shared) == 1


def test_projection_says_no_more_than_the_source(projected):
    links = projected["causal_links"]
    assert all("effect_direction" not in link for link in links)
    assert all(link["relation_kind"] == "CAUSATION" for link in links)
    statements = {link["statement"] for link in links}
    assert "Plaques activate microglia." in statements
    assert generated_statement("Seizures", "Cognitive Decline") in statements
    entries = [e for m in projected["mechanistic_models"] for e in m["links"]]
    assert sum("link_type" not in e for e in entries) == 3


def test_node_kinds_and_unresolved_targets(projected):
    variables = projected["causal_variables"]
    seizures = [v for v in variables if v["description"] == "Seizures"]
    assert sorted(v.get("aspect") or "" for v in seizures) == ["", "presence"]
    linked = {c["subject"] for c in projected["corresponds_to_dismech_edges"]}
    unresolved = [v for v in variables if v["description"] == "Unnamed Downstream State"]
    assert len(unresolved) == 1 and unresolved[0]["id"] not in linked
