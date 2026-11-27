"""Tissue, cell-type, cell-line and organism contexts; contexts on evidence;
knowledge gaps an account identifies and the propositions they concern."""
import pytest

from conftest import SCHEMA, set_context
from dapper_identity import compute_id
import lint_provenance as lp
from scientific_claims import check_scientific_content, index_document

KINDS = [
    ("TissueContext", "tissue", "UBERON:0001155", "http://purl.obolibrary.org/obo/UBERON_0001155"),
    ("CellTypeContext", "cell_type", "CL:0011108", "http://purl.obolibrary.org/obo/CL_0011108"),
    ("CellLineContext", "cell_line", "cellosaurus:0025", "https://www.cellosaurus.org/CVCL_0025"),
    ("OrganismContext", "organism", "NCBITaxon:10090", "http://purl.obolibrary.org/obo/NCBITaxon_10090"),
]


@pytest.fixture(scope="module")
def validator():
    return lp.build_validator(SCHEMA)


def proposition(**extra):
    return {"id": "urn:test:p", "statement": "FOSL2 activity increases colonic epithelial migration.", **extra}


@pytest.mark.parametrize("context_type,field,curie,uri", KINDS)
@pytest.mark.parametrize("class_name", ["Proposition", "EvidenceItem"])
def test_context_names_one_ontology_term(context_type, field, curie, uri, class_name, validator, sv):
    node = set_context({"id": "urn:test:x", "statement": "s"} if class_name == "Proposition" else {"id": "urn:test:x"},
                       context_type, field, curie)
    assert not validator.validate(node, class_name).results
    sv.all_classes()  # load the imports first: expand_curie caches the prefixes it has seen
    assert sv.expand_curie(curie) == uri
    for bad in (None, "colon", ["UBERON:0001155"]):
        broken = {**node, "contexts": [{"context_type": context_type, field: bad}]}
        assert validator.validate(broken, class_name).results, bad


@pytest.mark.parametrize("context_type,field,curie,uri", KINDS)
def test_contexts_are_part_of_identity(context_type, field, curie, uri, sv):
    plain = proposition()
    scoped = set_context(proposition(), context_type, field, curie)
    assert compute_id(plain, "Proposition", sv) != compute_id(scoped, "Proposition", sv)


def test_trait_accepts_disease_ontologies(validator):
    for trait in ("KPN.TRAIT:0000505", "MONDO:0005265", "EFO:0003767"):
        node = set_context({"id": "urn:test:x", "statement": "s"}, "TraitContext", "trait", trait)
        assert not validator.validate(node, "Proposition").results


def test_evidence_context_differs_from_its_target_for_an_analogy(validator, sv):
    """Mouse evidence for a human proposition: the difference is in the data."""
    target = set_context(proposition(), "OrganismContext", "organism", "NCBITaxon:9606")
    evidence = set_context({"id": "urn:test:e", "target_proposition": "urn:test:p", "direction": "SUPPORTS",
                            "snippet": "Fosl2 knockout mice healed colonic wounds more slowly."},
                           "OrganismContext", "organism", "NCBITaxon:10090")
    assert not validator.validate(evidence, "EvidenceItem").results
    assert lp.context_value(evidence, "OrganismContext", "organism") != \
        lp.context_value(target, "OrganismContext", "organism")
    human = set_context(dict(evidence), "OrganismContext", "organism", "NCBITaxon:9606")
    assert compute_id(evidence, "EvidenceItem", sv) != compute_id(human, "EvidenceItem", sv)


def account_document(gap_target="urn:test:link", identified="urn:test:gap"):
    return {
        "causal_variables": [{"id": "urn:test:v1", "description": "FOSL2 activity", "aspect": "ACTIVITY"},
                             {"id": "urn:test:v2", "description": "Epithelial migration", "aspect": "RATE"}],
        "causal_links": [{"id": "urn:test:link", "statement": "FOSL2 activity increases epithelial migration.",
                          "relation_kind": "CAUSATION", "cause": "urn:test:v1", "effect": "urn:test:v2"}],
        "propositions": [{"id": "urn:test:p", "statement": "FOSL2 promotes mucosal repair in IBD."}],
        "questions": [{"id": "urn:test:q", "text": "What evidence bears on FOSL2-driven mucosal repair?"}],
        "knowledge_gaps": [{"id": "urn:test:gap", "text": "Does FOSL2 drive colonic epithelial migration?",
                            "gap_description": "No study perturbs FOSL2 in human colonic epithelium.",
                            "concerns": [gap_target]}],
        "claims": [{"id": "urn:test:c", "proposition": "urn:test:p", "direction": "SUPPORTS"}],
        "scientific_accounts": [{"id": "urn:test:a", "framing": ["urn:test:q"], "context": "c",
                                 "component_claims": ["urn:test:c"], "identified_gaps": [identified]}],
    }


def test_an_account_identifies_a_gap_that_concerns_a_causal_link():
    assert check_scientific_content(index_document(account_document())) == []


def test_gap_and_identified_gap_references_are_checked():
    problems = check_scientific_content(index_document(account_document(gap_target="urn:test:v1",
                                                                        identified="urn:test:q")))
    found = " ".join(p for _, p in problems)
    assert "must resolve to Proposition" in found
    assert "must resolve to KnowledgeGap" in found


def test_identified_gaps_change_the_account_identity(sv):
    doc = account_document()
    account = doc["scientific_accounts"][0]
    without = {k: v for k, v in account.items() if k != "identified_gaps"}
    assert compute_id(account, "ScientificAccount", sv) != compute_id(without, "ScientificAccount", sv)
