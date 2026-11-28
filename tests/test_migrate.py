"""converter/migrate.py: documents written for DAPPER 0.2.1-a1 convert to this release,
re-mint, and verify; what cannot be converted faithfully is refused."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "converter"))
from migrate import Refusal, migrate  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "dapper-0.2.1"
DENT_PAGE = "https://dismech.monarchinitiative.org/pages/disorders/Dent_Disease.html"


def load(name):
    return yaml.safe_load((FIXTURES / f"{name}.yaml").read_text())


def by_id(doc):
    return {r["id"]: r for g, v in doc.items() if isinstance(v, list) and not g.endswith("_edges")
            for r in v if isinstance(r, dict) and "id" in r}


@pytest.mark.parametrize("name", ["example_scientific_account", "example_pigean_claims",
                                  "example_bottom_line_af_aa", "example_geneset_graph"])
def test_previous_release_examples_convert_and_verify(name):
    doc, ids, _ = migrate(load(name), "0.2.1-a1")
    old = by_id(load(name))
    assert set(ids) == set(old), "every original record is in the id map"
    assert set(ids.values()) <= set(by_id(doc)), "every new id is in the converted document"


def test_unchanged_records_keep_their_ids():
    """A gene-set graph uses no reshaped field, so nothing re-mints."""
    _, ids, _ = migrate(load("example_geneset_graph"), "0.2.1-a1")
    assert all(old == new for old, new in ids.items())


def test_account_is_framed_by_its_question_and_hypothesis():
    original = load("example_claim_provenance_trace")
    account = original["scientific_accounts"][0]
    doc, ids, _ = migrate(original, "0.2.1-a1", dismech_pages={"MONDO:0015612": DENT_PAGE})
    new = by_id(doc)[ids[account["id"]]]
    assert "question" not in new and "hypothesis" not in new
    question, hypothesis = new["framing"]
    assert question == ids[account["question"]]
    assert by_id(doc)[hypothesis]["proposition"] == ids[account["hypothesis"]]


def test_model_endpoints_become_a_link_and_dismech_fields_an_edge():
    original = load("example_claim_provenance_trace")
    doc, ids, notes = migrate(original, "0.2.1-a1", dismech_pages={"MONDO:0015612": DENT_PAGE})
    model = by_id(doc)[ids[original["mechanistic_models"][0]["id"]]]
    assert not {"subject_entity", "object_entity", "has_causal_step", "dismech_class"} & set(model)
    (entry,) = model["links"]
    link = by_id(doc)[entry["link"]]
    entities = {by_id(doc)[v]["entity"] for v in (link["cause"], link["effect"])}
    assert entities == {"HGNC:2023", "MONDO:0015612"}
    (edge,) = doc["corresponds_to_dismech_edges"]
    assert edge == {"subject": model["id"], "predicate": "skos:closeMatch", "object": DENT_PAGE,
                    "dismech_class": "dismech:MechanisticHypothesis"}
    assert any("subject_entity -> object_entity" in n for n in notes)
    assert any("dismech_disease_term" in n for n in notes)


def test_dismech_fields_without_a_page_are_refused():
    with pytest.raises(Refusal) as refused:
        migrate(load("example_claim_provenance_trace"), "0.2.1-a1")
    assert any("dismech_source_url" in p for p in refused.value.problems)


def test_causal_steps_become_links_in_order():
    doc = {"mechanistic_models": [{"id": "urn:test:model", "description": "A to B to C.", "has_causal_step": ["urn:test:step-2", "urn:test:step-1"]}],
           "causal_steps": [
               {"id": "urn:test:step-1", "step_index": 1, "step_subject": "HGNC:1", "step_object": "GO:0000001",
                "causal_link_type": "DIRECT", "description": "A raises B."},
               {"id": "urn:test:step-2", "step_index": 2, "step_subject": "GO:0000001", "step_object": "MONDO:0000001",
                "causal_link_type": "INDIRECT_UNKNOWN_INTERMEDIATES"}]}
    out, ids, _ = migrate(doc, "0.2.1-a1")
    model = by_id(out)[ids["urn:test:model"]]
    links = [by_id(out)[e["link"]] for e in model["links"]]
    assert [l["statement"] for l in links] == ["A raises B.", "GO:0000001 is causally upstream of MONDO:0000001."]
    assert [e["link_type"] for e in model["links"]] == ["DIRECT", "INDIRECT_UNKNOWN_INTERMEDIATES"]
    assert links[0]["effect"] == links[1]["cause"], "a shared entity is one variable"
    assert "causal_steps" not in out


def test_trait_and_ancestry_move_into_contexts():
    doc, ids, _ = migrate(load("example_bottom_line_af_aa"), "0.2.1-a1")
    with_contexts = [r for r in by_id(doc).values() if r.get("contexts")]
    assert with_contexts
    for r in with_contexts:
        assert "trait" not in r and "ancestry" not in r
        assert [c["context_type"] for c in r["contexts"]] == sorted(c["context_type"] for c in r["contexts"])


def test_a_step_from_an_unknown_release_is_refused():
    with pytest.raises(Refusal) as refused:
        migrate({}, "0.1.0")
    assert "must ship one" in refused.value.problems[0]


def test_a_step_with_an_unnamed_end_links_an_unnamed_variable():
    """0.2 let a step leave its subject or object unnamed. The model's own endpoints fill the first step's subject
    and the last step's object; any other missing end is a CausalVariable with no entity, one per end."""
    doc = {"mechanistic_models": [{"id": "urn:test:model", "description": "A chain.",
                                   "subject_entity": "HGNC:1", "object_entity": "MONDO:0000001",
                                   "has_causal_step": ["urn:test:s0", "urn:test:s1", "urn:test:s2"]}],
           "causal_steps": [
               {"id": "urn:test:s0", "step_index": 0, "description": "Gene 1 is expressed in stroma.",
                "causal_link_type": "DIRECT"},
               {"id": "urn:test:s1", "step_index": 1, "step_subject": "HGNC:1",
                "description": "Gene 1 maintains a stromal program.", "causal_link_type": "DIRECT"},
               {"id": "urn:test:s2", "step_index": 2, "description": "Losing it drives inflammation.",
                "causal_link_type": "UNKNOWN"}]}
    out, ids, notes = migrate(doc, "0.2.1-a1")
    nodes = by_id(out)
    model = nodes[ids["urn:test:model"]]
    links = [nodes[e["link"]] for e in model["links"]]
    first, middle, last = links
    assert nodes[first["cause"]]["entity"] == "HGNC:1"           # the model's subject
    assert nodes[last["effect"]]["entity"] == "MONDO:0000001"    # the model's object
    unnamed = [nodes[v] for v in (first["effect"], middle["effect"], last["cause"])]
    assert all("entity" not in v and "did not name" in v["description"] for v in unnamed)
    assert len({v["id"] for v in unnamed}) == 3, "each unnamed end is its own variable"
    assert sum("unnamed CausalVariable" in n for n in notes) == 3
    assert any("subject_entity HGNC:1 is its cause" in n for n in notes)
