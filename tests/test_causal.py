"""Interventionist causal content: variables, links as propositions, graphs."""
from copy import deepcopy
import importlib.util
import json

import pytest
import yaml
from jsonschema import Draft202012Validator
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from conftest import EXAMPLES, REPO_ROOT, SCHEMA
from dapper_identity import assign_ids, compute_id, verify
import lint_provenance as lp
from scientific_claims import check_scientific_content, index_document

DENT = EXAMPLES / "example_claim_provenance_trace.yaml"
CAUSAL_CLASSES = ["CausalVariable", "CausalLink", "CausalGraphLink", "CausalGraph"]
CAUSAL_ENUMS = ["RelationKindEnum", "EffectDirectionEnum", "CausalLinkTypeEnum", "EvidenceDesignEnum"]


@pytest.fixture(scope="module")
def json_schema():
    return json.loads(JsonSchemaGenerator(str(SCHEMA)).serialize())


def errors(schema, cls, node):
    return [e.message for e in Draft202012Validator({**schema, "$ref": f"#/$defs/{cls}"}).iter_errors(node)]


def _variable(name):
    return {"id": f"dapper:CausalVariable.{name}", "description": f"{name} level", "aspect": "level"}


def _link(cause, effect, direction="INCREASES"):
    return {"id": f"dapper:CausalLink.{cause}_{effect}",
            "statement": f"{cause} level {direction.lower()} {effect} level.",
            "relation_kind": "CAUSATION",
            "cause": f"dapper:CausalVariable.{cause}", "effect": f"dapper:CausalVariable.{effect}",
            "effect_direction": direction}


def _graph(edges, name="g", **extra):
    names = sorted({n for edge in edges for n in edge})
    return {"id": f"dapper:CausalGraph.{name}", "description": "test graph",
            "variables": [f"dapper:CausalVariable.{n}" for n in names],
            "links": [{"link": f"dapper:CausalLink.{a}_{b}", "link_type": "DIRECT"} for a, b in edges],
            **extra}


def _doc(edges, **extra):
    names = sorted({n for edge in edges for n in edge})
    return {"causal_variables": [_variable(n) for n in names],
            "causal_links": [_link(a, b) for a, b in edges],
            "causal_graphs": [_graph(edges, **extra)]}


def problems(doc):
    return check_scientific_content(index_document(doc))


# ---- schema shape ---------------------------------------------------------

def test_causal_classes_live_in_claims_and_specialize_the_reasoning_layer(sv):
    for name in CAUSAL_CLASSES + CAUSAL_ENUMS:
        element = sv.get_class(name) or sv.get_enum(name)
        assert element.from_schema.endswith("/claims.yaml"), name
    assert "Proposition" in sv.class_ancestors("CausalLink")
    assert "ExplanatoryModel" in sv.class_ancestors("CausalGraph")
    assert "CausalGraph" in sv.class_ancestors("MechanisticModel")
    assert sv.induced_slot("links", "MechanisticModel").range == "MechanisticLink"
    for retired in ("CausalStep", "HasCausalStep"):
        assert retired not in sv.all_classes()
    assert "has_causal_step" not in sv.all_slots()


def test_general_causal_classes_carry_no_dismech_mappings(sv):
    """DISMECH parity lives in mechanisms.yaml and dismech.yaml, not in claims."""
    def mappings(element):
        return [m for kind in ("exact_mappings", "close_mappings", "related_mappings",
                               "broad_mappings", "narrow_mappings")
                for m in (getattr(element, kind, None) or [])]
    for name in CAUSAL_CLASSES:
        cls = sv.get_class(name)
        found = mappings(cls) + [m for a in (cls.attributes or {}).values() for m in mappings(a)]
        assert not [m for m in found if m.startswith("dismech:")], name
    for name in CAUSAL_ENUMS:
        enum = sv.get_enum(name)
        found = mappings(enum) + [m for v in enum.permissible_values.values() for m in mappings(v)]
        assert not [m for m in found if m.startswith("dismech:")], name
    assert "dismech:CausalEdge" in sv.get_class("MechanisticLink").close_mappings
    assert "dismech:MechanisticHypothesis" in sv.get_class("MechanisticModel").close_mappings


def test_a_causal_link_is_always_causation(json_schema):
    """relation_kind is required and fixed, so one link has one spelling and one id."""
    link = _link("a", "b")
    assert not errors(json_schema, "CausalLink", link)
    assert errors(json_schema, "CausalLink", {**link, "relation_kind": "ASSOCIATION"})
    for required in ("cause", "effect", "statement", "relation_kind"):
        assert errors(json_schema, "CausalLink", {k: v for k, v in link.items() if k != required})


def test_mechanisms_only_on_mechanistic_models(json_schema):
    entry = {"link": "dapper:CausalLink.a_b", "link_type": "DIRECT",
             "via_mechanism": ["dapper:Mechanism.m"]}
    graph = {"id": "x", "description": "d", "variables": ["dapper:CausalVariable.a"], "links": [entry]}
    assert not errors(json_schema, "MechanisticModel", graph)
    assert errors(json_schema, "CausalGraph", graph)


def test_relation_kind_and_evidence_design_are_closed_vocabularies(json_schema):
    proposition = {"id": "x", "statement": "A is associated with B.", "relation_kind": "ASSOCIATION"}
    assert not errors(json_schema, "Proposition", proposition)
    assert errors(json_schema, "Proposition", {**proposition, "relation_kind": "CORRELATION"})
    evidence = {"id": "x", "evidence_design": "NATURAL_EXPERIMENT"}
    assert not errors(json_schema, "EvidenceItem", evidence)
    assert errors(json_schema, "EvidenceItem", {**evidence, "evidence_design": "RCT"})


# ---- identity ---------------------------------------------------------------

def test_directness_belongs_to_the_graph_not_the_link(sv):
    """One link, DIRECT in a coarse graph and INDIRECT in a finer one: the link
    keeps one identifier; the two graphs differ."""
    doc = _doc([("a", "b")])
    doc["causal_graphs"].append(deepcopy(doc["causal_graphs"][0]))
    doc["causal_graphs"][1]["id"] = "dapper:CausalGraph.fine"
    doc["causal_graphs"][1]["links"][0]["link_type"] = "INDIRECT_KNOWN_INTERMEDIATES"
    doc["causal_graphs"][1]["links"][0]["intermediates"] = ["c"]
    mapping = assign_ids(doc, sv)
    links = {doc["causal_graphs"][i]["links"][0]["link"] for i in (0, 1)}
    assert len(links) == 1 and links == {mapping["dapper:CausalLink.a_b"]}
    assert doc["causal_graphs"][0]["id"] != doc["causal_graphs"][1]["id"]
    assert verify(doc, sv) == []


def test_minting_rewrites_links_inside_a_graph_and_is_idempotent(sv):
    doc = _doc([("a", "b"), ("b", "c")])
    assign_ids(doc, sv)
    minted = deepcopy(doc)
    assert all(e["link"] in {l["id"] for l in doc["causal_links"]} for e in doc["causal_graphs"][0]["links"])
    assign_ids(doc, sv)
    assert doc == minted


def test_contexts_and_relation_kind_are_part_of_proposition_identity(sv):
    base = {"statement": "A is associated with B."}
    ids = {compute_id(base, "Proposition", sv),
           compute_id({**base, "relation_kind": "ASSOCIATION"}, "Proposition", sv),
           compute_id({**base, "contexts": [{"context_type": "AncestryContext", "ancestry": "AA"}]},
                      "Proposition", sv)}
    assert len(ids) == 3


# ---- graph checks -------------------------------------------------------------

def test_an_acyclic_graph_passes():
    assert problems(_doc([("a", "b"), ("b", "c"), ("a", "c")])) == []


def test_an_undeclared_cycle_is_an_error_and_a_declared_one_passes():
    cyclic = [("a", "b"), ("b", "c"), ("c", "a")]
    found = problems(_doc(cyclic))
    assert any("directed cycle without has_feedback" in p for _, p in found), found
    assert problems(_doc(cyclic, has_feedback=True)) == []


def test_declared_feedback_needs_a_cycle():
    found = problems(_doc([("a", "b")], has_feedback=True))
    assert any("has no directed cycle" in p for _, p in found), found


def test_links_stay_inside_the_variable_set_and_appear_once():
    doc = _doc([("a", "b")])
    graph = doc["causal_graphs"][0]
    graph["variables"].remove("dapper:CausalVariable.b")
    graph["links"].append(dict(graph["links"][0]))
    found = [p for _, p in problems(doc)]
    assert any("not in this graph's variables" in p for p in found), found
    assert any("appears more than once" in p for p in found), found


def test_graph_entries_must_name_causal_links():
    doc = _doc([("a", "b")])
    doc["causal_graphs"][0]["links"][0]["link"] = "dapper:CausalVariable.a"
    assert any("must resolve to CausalLink" in p for _, p in problems(doc))


def test_claims_and_evidence_can_target_a_single_link():
    """Steps are propositions: a Claim assesses one link, with its own evidence."""
    doc = _doc([("a", "b")])
    link = doc["causal_links"][0]["id"]
    doc["evidence_items"] = [{"id": "dapper:EvidenceItem.e", "target_proposition": link,
                              "evidence_design": "EXPERIMENTAL_INTERVENTION",
                              "snippet": "Knockout of A lowered B."}]
    doc["claims"] = [{"id": "dapper:Claim.c", "proposition": link, "direction": "SUPPORTS",
                      "has_evidence": ["dapper:EvidenceItem.e"]}]
    doc["propositions"] = [{"id": "dapper:Proposition.p", "statement": "A raises B via the graph.",
                            "relation_kind": "CAUSATION",
                            "explanatory_model": "dapper:CausalGraph.g"}]
    assert problems(doc) == []


# ---- the Dent example -----------------------------------------------------------

@pytest.fixture(scope="module")
def dent():
    return yaml.safe_load(DENT.read_text())


def test_dent_model_relates_variables_not_bare_entities(dent):
    model = dent["mechanistic_models"][0]
    variables = {v["id"]: v for v in dent["causal_variables"]}
    links = {l["id"]: l for l in dent["causal_links"]}
    assert set(model["variables"]) == set(variables)
    assert all(v.get("aspect") for v in variables.values())
    chain = [links[e["link"]] for e in model["links"]]
    assert variables[chain[0]["cause"]]["entity"] == "HGNC:2023"
    assert [l["effect_direction"] for l in chain] == ["INCREASES", "INCREASES", "DECREASES"]
    # Dent disease defines the dysfunction, so it is not a causal variable.
    assert "MONDO:0015612" not in {v.get("entity") for v in variables.values()}
    assert "has_feedback" not in model
    proposition = next(p for p in dent["propositions"] if p.get("explanatory_model") == model["id"])
    assert proposition["relation_kind"] == "CAUSATION"


def test_dent_example_lints_clean_with_links_reachable(sv):
    vocab = lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))
    report = lp.lint(DENT, vocab, sv, lp.build_validator(SCHEMA))
    assert not report.findings, report.findings
    doc = lp.Document.load(DENT, vocab)
    nested = {r.object for r in doc.relationships(vocab) if r.where.endswith(".link")}
    assert nested == {l["id"] for l in yaml.safe_load(DENT.read_text())["causal_links"]}


def test_portal_draws_graph_link_and_variable_edges(dent):
    spec = importlib.util.spec_from_file_location("causal_portal", REPO_ROOT / "portal/build.py")
    portal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portal)
    graph = portal.build_graph(next(g for g in portal.GRAPH_DOCS
                                    if g["file"] == "example_claim_provenance_trace.yaml"))
    edges = {(e["source"], e["predicate"], e["target"]) for e in graph["edges"]}
    model = dent["mechanistic_models"][0]["id"]
    for link in dent["causal_links"]:
        assert (link["id"], "dapper:link", model) in edges
        assert (link["cause"], "dapper:cause", link["id"]) in edges
        assert (link["id"], "dapper:effect", link["effect"]) in edges


def test_a_link_takes_typed_contexts_end_to_end(json_schema, sv, tmp_path):
    """Contexts on a CausalLink validate, are prefix-checked inside the typed
    context, and fall under the linter's one-per-kind rule."""
    from document_prefixes import transform_identifiers
    link = {**_link("a", "b"), "contexts": [{"context_type": "TraitContext", "trait": "KPN.TRAIT:0000096"}]}
    assert not errors(json_schema, "CausalLink", link)
    assert errors(json_schema, "CausalLink", {**link, "contexts": [{"context_type": "TraitContext"}]})
    bad = {**link, "contexts": [{"context_type": "TraitContext", "trait": "NOPE:1"}]}
    _, problems_found = transform_identifiers({"causal_links": [bad]}, sv, {"causal_links": "CausalLink"})
    assert [where for where, _ in problems_found] == ["causal_links[0].contexts[0].trait"]
    twice = {**link, "contexts": link["contexts"] * 2}
    path = tmp_path / "doc.yaml"
    path.write_text(yaml.safe_dump({"causal_links": [twice]}))
    vocab = lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))
    report = lp.Report(path=path)
    lp.check_contexts(lp.Document.load(path, vocab), report)
    assert [f.check for f in report.errors] == ["contexts"]


def test_a_claim_on_one_link_lints_clean_inside_an_account(sv, tmp_path):
    """Steps are propositions, end to end: a minted Claim with experimental
    evidence assesses one link of the Dent graph inside the account."""
    doc = yaml.safe_load(DENT.read_text())
    link = doc["causal_links"][0]["id"]
    existing = doc["claims"][0]
    doc["evidence_items"].append({
        "id": "dapper:EvidenceItem.link_evidence", "target_proposition": link,
        "evidence_design": "EXPERIMENTAL_INTERVENTION",
        "snippet": "Illustrative: endosomal acidification was reduced in Clcn5-knockout proximal tubule cells.",
        "explanation": "A knockout sets CLCN5 activity low and shows the effect on acidification.",
        "was_attributed_to": existing["was_attributed_to"],
        "was_generated_by": existing["was_generated_by"]})
    doc["claims"].append({
        "id": "dapper:Claim.link_claim", "name": "CLCN5 activity raises endosomal acidification",
        "proposition": link, "direction": "SUPPORTS",
        "has_evidence": ["dapper:EvidenceItem.link_evidence"],
        "was_attributed_to": existing["was_attributed_to"],
        "was_generated_by": existing["was_generated_by"]})
    doc["_illustrative"] += ["dapper:EvidenceItem.link_evidence", "dapper:Claim.link_claim"]
    doc["scientific_accounts"][0]["component_claims"].insert(0, "dapper:Claim.link_claim")
    assign_ids(doc, sv)
    assert verify(doc, sv) == []
    assert problems(doc) == []
    path = tmp_path / "dent_link_claim.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    vocab = lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))
    report = lp.lint(path, vocab, sv, lp.build_validator(SCHEMA))
    assert not report.findings, report.findings
