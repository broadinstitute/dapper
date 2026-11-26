"""Structural causal models and causal estimands."""
from copy import deepcopy
import json

import pytest
import yaml
from jsonschema import Draft202012Validator
from linkml.generators.jsonschemagen import JsonSchemaGenerator

from conftest import EXAMPLES, SCHEMA
from dapper_identity import assign_ids, verify
import lint_provenance as lp
from scientific_claims import check_scientific_content, index_document

EXAMPLE = EXAMPLES / "example_structural_causal_model.yaml"


@pytest.fixture(scope="module")
def json_schema():
    return json.loads(JsonSchemaGenerator(str(SCHEMA)).serialize())


@pytest.fixture
def doc():
    return yaml.safe_load(EXAMPLE.read_text())


def errors(schema, cls, node):
    return [e.message for e in Draft202012Validator({**schema, "$ref": f"#/$defs/{cls}"}).iter_errors(node)]


def problems(document):
    return check_scientific_content(index_document(document))


def by_name(document, group, name):
    return next(n for n in document[group] if n["name"] == name)


def test_scm_specializes_the_causal_layer(sv):
    assert "CausalGraph" in sv.class_ancestors("StructuralCausalModel")
    assert "ExplanatoryModel" in sv.class_ancestors("StructuralCausalModel")
    assert "Proposition" in sv.class_ancestors("CausalEstimand")
    assert sv.get_class("StructuralCausalModel").from_schema.endswith("/scm.yaml")


def test_example_is_minted_and_lints_clean(doc, sv):
    assert verify(doc, sv) == []
    assert problems(doc) == []
    vocab = lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))
    report = lp.lint(EXAMPLE, vocab, sv, lp.build_validator(SCHEMA))
    assert not report.findings, report.findings


def test_example_records_validate(doc, json_schema):
    for cls, node in index_document(doc).values():
        assert not errors(json_schema, cls, node), (cls, errors(json_schema, cls, node))


def test_unmeasured_confounder_is_an_explicit_latent_variable(doc):
    scm = doc["structural_causal_models"][0]
    u = by_name(doc, "causal_variables", "U")["id"]
    spec = next(s for s in scm["variable_specifications"] if s["variable"] == u)
    assert spec["observed"] is False and spec["distribution"]["family"] == "NORMAL"
    effects = {l["effect"] for l in doc["causal_links"] if l["cause"] == u}
    assert effects == {by_name(doc, "causal_variables", n)["id"] for n in ("X", "Y")}


def test_domains_live_on_the_model_entry_not_the_variable(doc, sv):
    """The same variable, binary in one model and continuous in another, keeps one id."""
    scm = doc["structural_causal_models"][0]
    other = deepcopy(scm)
    other["id"] = "dapper:StructuralCausalModel.other"
    m = by_name(doc, "causal_variables", "M")["id"]
    for spec in other["variable_specifications"]:
        if spec["variable"] == m:
            spec.update(domain="BINARY", levels=["low", "high"])
    doc["structural_causal_models"].append(other)
    assign_ids(doc, sv)
    first, second = doc["structural_causal_models"]
    assert first["id"] != second["id"]
    assert m in first["variables"] and m in second["variables"]


def test_scm_must_be_acyclic(doc):
    doc["structural_causal_models"][0]["has_feedback"] = True
    assert any("must be acyclic" in p for _, p in problems(doc))


def test_equation_inputs_must_match_the_graph(doc):
    scm = doc["structural_causal_models"][0]
    y = by_name(doc, "causal_variables", "Y")["id"]
    equation = next(e for e in scm["equations"] if e["outcome"] == y)
    equation["inputs"] = equation["inputs"][:1]
    assert any("must be exactly" in p for _, p in problems(doc))


def test_specifications_and_equations_are_one_per_variable(doc):
    scm = doc["structural_causal_models"][0]
    scm["equations"].append(deepcopy(scm["equations"][0]))
    scm["variable_specifications"].append(deepcopy(scm["variable_specifications"][0]))
    found = [p for _, p in problems(doc)]
    assert any("more than one equation" in p for p in found)
    assert any("specified more than once" in p for p in found)


def test_only_uncaused_variables_get_a_distribution(doc):
    scm = doc["structural_causal_models"][0]
    x = by_name(doc, "causal_variables", "X")["id"]
    spec = next(s for s in scm["variable_specifications"] if s["variable"] == x)
    spec["distribution"] = {"family": "NORMAL"}
    assert any("give it an equation" in p for _, p in problems(doc))


def test_estimand_variables_belong_to_the_model(doc):
    estimand = doc["causal_estimands"][0]
    estimand["treatment"] = "dapper:CausalVariable.elsewhere"
    assert any("not in the model's variables" in p for _, p in problems(doc))


def test_mediated_estimands_need_a_mediator(doc, json_schema):
    estimand = doc["causal_estimands"][0]
    del estimand["mediator"]
    assert any("needs a mediator" in p for _, p in problems(doc))
    estimand["estimand_kind"] = "AVERAGE_EFFECT"
    assert problems(doc) == []
    for required in ("estimand_kind", "treatment", "outcome", "relation_kind"):
        assert errors(json_schema, "CausalEstimand", {k: v for k, v in estimand.items() if k != required})


def test_estimates_are_claims_with_effect_scores(doc):
    claim = doc["claims"][0]
    assert claim["proposition"] == doc["causal_estimands"][0]["id"]
    score = next(s for s in doc["claim_scores"] if s["id"] in claim["has_score"])
    assert score["score_kind"] == "EFFECT_ESTIMATE"
