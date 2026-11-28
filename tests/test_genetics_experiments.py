"""Evidence basis on claims, genetic variants and their effect sizes, rival
hypotheses, and discriminating experiments stated with causal estimands."""
from copy import deepcopy

import pytest
import yaml

from conftest import EXAMPLES, SCHEMA
from dapper_identity import compute_id, verify
import lint_provenance as lp
from scientific_claims import check_scientific_content, index_document

EXAMPLE = EXAMPLES / "example_genetic_discriminating_account.yaml"


@pytest.fixture(scope="module")
def validator():
    return lp.build_validator(SCHEMA)


@pytest.fixture
def doc():
    return yaml.safe_load(EXAMPLE.read_text())


def problems(document):
    return [message for _, message in check_scientific_content(index_document(document))]


def by_name(document, group, name):
    return next(n for n in document[group] if n["name"] == name)


def test_new_classes_specialize_the_causal_layer(sv):
    assert "CausalVariable" in sv.class_ancestors("GenotypeVariable")
    assert "Proposition" in sv.class_ancestors("GeneticAssociation")
    assert "ClaimScore" in sv.class_ancestors("GeneticEffectEstimate")
    assert "ProposedExperiment" in sv.class_ancestors("DiscriminatingExperiment")
    assert sv.get_class("ProposedExperiment").abstract
    assert sv.get_class("GenotypeVariable").from_schema.endswith("/genetics.yaml")


def test_example_is_minted_and_lints_clean(doc, sv):
    assert verify(doc, sv) == []
    assert problems(doc) == []
    vocab = lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))
    report = lp.lint(EXAMPLE, vocab, sv, lp.build_validator(SCHEMA))
    assert not report.findings, report.findings


# ---- evidence basis ----------------------------------------------------------

def test_evidence_basis_is_part_of_claim_identity(doc, sv):
    claim = by_name(doc, "claims", "Genotype lowers G expression")
    analogy = {**claim, "evidence_basis": "BY_ANALOGY"}
    assert compute_id(claim, "Claim", sv) != compute_id(analogy, "Claim", sv)


@pytest.mark.parametrize("direction,ok", [(None, True), ("UNKNOWN", True), ("SUPPORTS", False),
                                          ("DISPUTES", False), ("MIXED", False), ("NEUTRAL", False)])
def test_untested_claim_has_no_direction(doc, direction, ok):
    claim = by_name(doc, "claims", "G and the barrier, untested")
    claim.pop("direction", None)
    if direction:
        claim["direction"] = direction
    assert any("UNTESTED" in p for p in problems(doc)) != ok


def test_direct_basis_needs_evidence_on_the_propositions_own_variables(doc):
    """Evidence that measured another variable makes a claim INDIRECT, not IN_CONTEXT."""
    evidence = doc["evidence_items"][0]
    sibling = by_name(doc, "causal_variables", "Barrier integrity")["id"]
    evidence["measured_variables"] = [evidence["measured_variables"][0], sibling]
    assert any("no evidence carrying its direction measured all of" in p for p in problems(doc))
    by_name(doc, "claims", "Genotype lowers G expression")["evidence_basis"] = "INDIRECT"
    assert problems(doc) == []


def test_evidence_without_measured_variables_is_not_checked(doc):
    doc["evidence_items"][0].pop("measured_variables")
    assert problems(doc) == []


def test_measured_variables_must_be_variables(doc):
    doc["evidence_items"][0]["measured_variables"].append(doc["questions"][0]["id"])
    assert any("must resolve to CausalVariable" in p for p in problems(doc))


def test_evidence_basis_rejects_unknown_values(doc, validator):
    claim = {**by_name(doc, "claims", "Genotype lowers G expression"), "evidence_basis": "ANALOGUE"}
    assert validator.validate(claim, "Claim").results


# ---- genetics ----------------------------------------------------------------

def test_genotype_variable_names_a_dbsnp_variant_and_an_allele(doc, validator):
    variable = doc["genotype_variables"][0]
    assert not validator.validate(variable, "GenotypeVariable").results
    for field, bad in [("entity", "HGNC:12345"), ("entity", "dbSNP:12345"), ("aspect", "EXPRESSION"),
                       ("effect_allele", "t"), ("effect_allele", None)]:
        broken = {k: v for k, v in variable.items() if not (k == field and bad is None)}
        if bad is not None:
            broken[field] = bad
        assert validator.validate(broken, "GenotypeVariable").results, (field, bad)


def test_effect_allele_is_part_of_identity(doc, sv):
    variable = doc["genotype_variables"][0]
    assert compute_id(variable, "GenotypeVariable", sv) != \
        compute_id({**variable, "effect_allele": "C", "other_allele": "T"}, "GenotypeVariable", sv)


def test_genetic_effect_estimate_needs_a_scale(doc, validator):
    score = doc["genetic_effect_estimates"][0]
    assert not validator.validate(score, "GeneticEffectEstimate").results
    assert validator.validate({k: v for k, v in score.items() if k != "effect_scale"},
                              "GeneticEffectEstimate").results
    assert validator.validate({**score, "p_value": 2.0}, "GeneticEffectEstimate").results
    assert validator.validate({**score, "score_kind": "PROBABILITY"}, "GeneticEffectEstimate").results


def test_association_kind_and_study_design_are_separate(doc, validator):
    """A candidate-gene meta-analysis of a disease association is expressible."""
    association = doc["genetic_associations"][0]
    assert not validator.validate({**association, "association_kind": "DISEASE_OR_TRAIT"}, "GeneticAssociation").results
    assert validator.validate({**association, "association_kind": "GWAS"}, "GeneticAssociation").results
    score = {**doc["genetic_effect_estimates"][0], "study_scope": "CANDIDATE_GENE", "meta_analysis": True,
             "number_of_studies": 6, "number_of_cases": 8699, "number_of_controls": 13540, "sample_size": 22239}
    assert not validator.validate(score, "GeneticEffectEstimate").results
    assert validator.validate({**score, "study_scope": "GWAS"}, "GeneticEffectEstimate").results


@pytest.mark.parametrize("change,message", [
    ({"number_of_studies": 6}, "set meta_analysis: true"),
    ({"meta_analysis": False, "number_of_studies": 3}, "meta_analysis is false"),
    ({"number_of_cases": 200, "number_of_controls": 200}, "exceed sample_size"),
])
def test_study_counts_agree(doc, change, message):
    doc["genetic_effect_estimates"][0].update(change)
    assert any(message in p for p in problems(doc))


def test_genetic_effect_estimate_needs_a_genotype_proposition(doc):
    """The estimate's sign follows an effect allele, so the claim must be about one."""
    score = doc["genetic_effect_estimates"][0]["id"]
    by_name(doc, "claims", "G and the barrier, untested")["has_score"] = [score]
    assert any("needs a proposition about a GenotypeVariable" in p for p in problems(doc))


def test_genetic_effect_estimate_on_a_link_from_a_genotype(doc):
    score = doc["genetic_effect_estimates"][0]["id"]
    by_name(doc, "claims", "Genotype lowers G expression")["has_score"] = [score]
    assert problems(doc) == []


def test_genetic_association_resolves_its_variables(doc):
    association = doc["genetic_associations"][0]
    association["genotype"] = by_name(doc, "causal_variables", "Barrier integrity")["id"]
    assert any("must resolve to GenotypeVariable" in p for p in problems(doc))


def test_genetic_association_is_an_association(doc, validator):
    association = doc["genetic_associations"][0]
    assert validator.validate({**association, "relation_kind": "CAUSATION"}, "GeneticAssociation").results
    association["subject_entity"] = "dbSNP:rs1000001"
    assert any("not subject_entity" in p for p in problems(doc))


# ---- rival hypotheses ----------------------------------------------------------

def test_alternative_hypothesis_points_at_a_hypothesis(doc):
    rival = by_name(doc, "hypotheses", "Immune hypothesis")
    rival["alternative_to"] = [rival["id"]]
    assert any("not an alternative to itself" in p for p in problems(doc))
    rival["alternative_to"] = [doc["questions"][0]["id"]]
    assert any("must resolve to Hypothesis" in p for p in problems(doc))


def test_alternative_is_part_of_hypothesis_identity(doc, sv):
    rival = by_name(doc, "hypotheses", "Immune hypothesis")
    plain = {k: v for k, v in rival.items() if k != "alternative_to"}
    assert compute_id(rival, "Hypothesis", sv) != compute_id(plain, "Hypothesis", sv)


# ---- discriminating experiments ---------------------------------------------

def test_experiment_must_discriminate(doc):
    experiment = doc["discriminating_experiments"][0]
    for prediction in experiment["predictions"]:
        prediction["predicted_change"] = "DECREASES"
    assert any("does not discriminate" in p for p in problems(doc))


def test_a_proposition_holding_and_failing_discriminates(doc):
    """One hypothesis alone discriminates against its own failure."""
    experiment = doc["discriminating_experiments"][0]
    barrier = by_name(doc, "propositions", "Barrier hypothesis")["id"]
    estimand = experiment["estimands"][0]
    experiment["predictions"] = [
        {"estimand": estimand, "proposition": barrier, "predicted_change": "DECREASES"},
        {"estimand": estimand, "proposition": barrier, "proposition_holds": False, "predicted_change": "NO_CHANGE"},
    ]
    assert problems(doc) == []


def test_predictions_stay_within_the_experiment(doc):
    experiment = doc["discriminating_experiments"][0]
    experiment["predictions"][0]["proposition"] = doc["genetic_associations"][0]["id"]
    experiment["estimands"] = experiment["estimands"][1:]
    found = problems(doc)
    assert any("not one of the propositions the experiment tests" in p for p in found)
    assert any("not one of the experiment's estimands" in p for p in found)


def test_instrument_is_not_a_treatment(doc):
    experiment = doc["discriminating_experiments"][0]
    experiment["instruments"] = [by_name(doc, "causal_variables", "Gene G expression in colon")["id"]]
    assert any("not an instrument" in p for p in problems(doc))
    experiment["instruments"] = [doc["genotype_variables"][0]["id"]]
    assert problems(doc) == []


def test_experiment_needs_two_predictions_and_an_estimand(doc, validator):
    experiment = doc["discriminating_experiments"][0]
    assert not validator.validate(experiment, "DiscriminatingExperiment").results
    assert validator.validate({**experiment, "predictions": experiment["predictions"][:1]},
                              "DiscriminatingExperiment").results
    assert validator.validate({**experiment, "estimands": []}, "DiscriminatingExperiment").results
    bad = deepcopy(experiment)
    bad["predictions"][0]["predicted_change"] = "LOWER"
    assert validator.validate(bad, "DiscriminatingExperiment").results


def test_account_proposes_experiments(doc):
    account = doc["scientific_accounts"][0]
    account["proposed_experiments"] = [doc["causal_estimands"][0]["id"]]
    assert any("must resolve to ProposedExperiment" in p for p in problems(doc))


# ---- an estimand's predicted change -------------------------------------------

def _claim_on_estimand(doc, direction):
    estimand = doc["causal_estimands"][0]
    doc["claims"].append({"id": "urn:test:estimand-claim", "proposition": estimand["id"],
                          "direction": direction})
    return estimand


@pytest.mark.parametrize("direction,needs", [("SUPPORTS", True), ("DISPUTES", True), ("MIXED", True),
                                             ("UNKNOWN", False), ("NEUTRAL", False)])
def test_a_directed_claim_on_an_estimand_needs_its_predicted_change(doc, direction, needs):
    estimand = _claim_on_estimand(doc, direction)
    flagged = any("predicted_change" in m for m in problems(doc))
    assert flagged == needs
    estimand["predicted_change"] = "DECREASES"
    assert not any("predicted_change" in m for m in problems(doc))


def test_predicted_change_is_part_of_estimand_identity(doc, sv):
    estimand = doc["causal_estimands"][0]
    assert compute_id(estimand, "CausalEstimand", sv) != compute_id(
        {**estimand, "predicted_change": "DECREASES"}, "CausalEstimand", sv)


def test_predicted_change_takes_the_prediction_vocabulary(doc, validator):
    estimand = {**doc["causal_estimands"][0], "predicted_change": "DECREASES"}
    assert not validator.validate(estimand, "CausalEstimand").results
    assert validator.validate({**estimand, "predicted_change": "LOWER"}, "CausalEstimand").results
