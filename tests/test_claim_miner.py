"""Claim Miner model integration and provenance-shape tests."""

from __future__ import annotations


def test_claim_miner_classes_extend_existing_dapper_types(sv):
    expected_parents = {
        "MechanisticHypothesis": "Hypothesis",
        "EffectModificationHypothesis": "Hypothesis",
        "PublicationPassage": "HashableNode",
        "MiningActivity": "Activity",
        "TextEvidenceItem": "EvidenceItem",
        "ExtractionAssessment": "HashableNode",
        "MechanismAssessment": "HashableNode",
        "ResearchGap": "HashableNode",
    }
    for class_name, parent in expected_parents.items():
        assert sv.get_class(class_name).is_a == parent


def test_hypothesis_separates_proposition_type_polarity_and_status(sv):
    assert sv.induced_slot("hypothesis_type", "Hypothesis").range == "HypothesisTypeEnum"
    assert sv.induced_slot("polarity", "Hypothesis").range == "HypothesisPolarityEnum"
    assert sv.induced_slot("status", "Hypothesis").range == "HypothesisStatusEnum"


def test_effect_modification_shape_preserves_claim_miner_fields(sv):
    required = {
        "exposure_entity",
        "exposure_label",
        "exposure_type",
        "outcome_entity",
        "outcome_label",
        "modifier_type",
        "modifier_value",
        "direction_pattern",
        "stronger_in",
        "outcome_axis",
        "has_evidence",
        "was_generated_by",
    }
    slots = {slot.name for slot in sv.class_induced_slots("EffectModificationHypothesis")}
    assert required <= slots


def test_claim_miner_example_is_connected(example_docs):
    doc = example_docs["example_claim_miner_trace.yaml"]
    groups = (
        "publications",
        "publication_passages",
        "mining_activities",
        "text_evidence_items",
        "effect_modification_hypotheses",
        "mechanism_assessments",
        "research_gaps",
        "mechanisms",
        "causal_steps",
        "mechanistic_hypotheses",
    )
    nodes = {node["id"]: node for group in groups for node in doc.get(group, [])}

    internal_refs: set[str] = set()

    def collect(value, *, in_id: bool = False):
        if isinstance(value, dict):
            for key, child in value.items():
                collect(child, in_id=key == "id")
        elif isinstance(value, list):
            for child in value:
                collect(child)
        elif isinstance(value, str) and not in_id and value.startswith("dapper:"):
            internal_refs.add(value)

    collect(doc)
    assert internal_refs <= set(nodes)

    effect = doc["effect_modification_hypotheses"][0]
    assessment = doc["mechanism_assessments"][0]
    gap = doc["research_gaps"][0]
    mechanism_hypothesis = doc["mechanistic_hypotheses"][0]

    assert effect["was_generated_by"] in nodes
    assert assessment["about_hypothesis"] == effect["id"]
    assert assessment["id"] in gap["based_on_assessment"]
    assert gap["id"] in mechanism_hypothesis["was_derived_from"]
