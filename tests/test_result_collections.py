"""Result collections and value locators (0.2.1-a1).

A ResultCollection version lists Datasets identified by declared dimensions,
each with its files by role, plus the templates that mint claims from them.
Claims never point back at the collection, so a new version does not
re-address claims whose template and file are unchanged. A ValueLocator pins
the bytes of one value in a result file, and those bytes are checkable here
because the example result files are real.
"""
from __future__ import annotations

import copy
import hashlib

import pytest
import yaml

from conftest import EXAMPLES, SCHEMA
from dapper_identity import DOC_GROUPS, assign_ids, compute_id, verify

import lint_provenance as lp

COLLECTION = EXAMPLES / "example_result_collection.yaml"
CLAIMS = EXAMPLES / "example_collection_claims.yaml"


@pytest.fixture(scope="module")
def vocab(sv):
    return lp.Vocabulary.build(sv, yaml.safe_load(lp.PROFILES_PATH.read_text()))


@pytest.fixture(scope="module")
def validator():
    return lp.build_validator(SCHEMA)


@pytest.fixture
def collection_doc() -> dict:
    return yaml.safe_load(COLLECTION.read_text())


@pytest.fixture(scope="module")
def claims_doc() -> dict:
    return yaml.safe_load(CLAIMS.read_text())


def lint_doc(doc, tmp_path, vocab, sv, validator, profile="result-collection"):
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return lp.lint(path, vocab, sv, validator, profile)


def findings(report, check="result-collection", severity="error"):
    return [f for f in report.findings if f.check == check and f.severity == severity]


def remint(doc, sv):
    assign_ids(doc, sv)
    assert verify(doc, sv) == []
    return doc


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------
def test_new_node_classes_mint_and_value_objects_do_not(sv):
    assert DOC_GROUPS["result_collections"] == "ResultCollection"
    assert DOC_GROUPS["value_locators"] == "ValueLocator"
    # DimensionValue and FileRole are inline value objects: they shape the
    # owning Dataset's identity and have no identifiers of their own.
    assert "DimensionValue" not in DOC_GROUPS.values()
    assert "FileRole" not in DOC_GROUPS.values()
    assert sv.get_identifier_slot("DimensionValue") is None
    assert sv.get_identifier_slot("FileRole") is None


def test_both_collections_specialize_the_abstract_collection(sv):
    assert sv.get_class("Collection").abstract
    assert "Collection" not in DOC_GROUPS.values()
    for name in ("GeneSetCollection", "ResultCollection"):
        ancestors = sv.class_ancestors(name)
        assert "Collection" in ancestors and "Set" in ancestors, name
        slots = {s.name for s in sv.class_induced_slots(name)}
        assert {"members", "n_members", "collection_key", "version", "was_revision_of"} <= slots
    assert sv.induced_slot("members", "GeneSetCollection").range == "GeneSet"
    assert sv.induced_slot("members", "ResultCollection").range == "Dataset"
    # Versioning is optional for gene-set libraries and required for releases.
    assert not sv.induced_slot("collection_key", "GeneSetCollection").required
    assert sv.induced_slot("collection_key", "ResultCollection").required


def test_collection_key_is_stable_while_the_version_id_moves(collection_doc, sv):
    collection = collection_doc["result_collections"][0]
    content = {k: v for k, v in collection.items() if k != "id"}
    first = compute_id(content, "ResultCollection", sv)
    second = compute_id({**content, "version": "2026.12.0",
                         "was_revision_of": first}, "ResultCollection", sv)
    assert first == collection["id"]
    assert second != first


def test_dimension_values_and_file_roles_are_part_of_dataset_identity(collection_doc, sv):
    dataset = {k: v for k, v in collection_doc["datasets"][0].items() if k != "id"}
    base = compute_id(dataset, "Dataset", sv)
    moved = copy.deepcopy(dataset)
    moved["dimension_values"][1]["dimension_value"] = "example-library-v2"
    renamed = copy.deepcopy(dataset)
    renamed["file_roles"][0]["role"] = "gene_statistics"
    assert len({base, compute_id(moved, "Dataset", sv), compute_id(renamed, "Dataset", sv)}) == 3


def test_adding_the_new_dataset_slots_leaves_existing_dataset_ids_alone(example_docs):
    """Optional slots hash only when present, so 0.2.0 Dataset ids survive."""
    for name, doc in example_docs.items():
        if name == COLLECTION.name:
            continue
        for dataset in doc.get("datasets") or []:
            assert "dimension_values" not in dataset and "file_roles" not in dataset


def test_claims_never_reference_the_collection(collection_doc, claims_doc):
    """A new collection version must not re-address unchanged claims."""
    collection_ids = {n["id"] for n in collection_doc["result_collections"]}
    collection_ids |= {n["id"] for n in collection_doc["datasets"]}
    assert collection_ids.isdisjoint(yaml.safe_dump(claims_doc).split())
    # ...yet each claim reaches the exact file and template the collection lists.
    result_files = {r["file"] for d in collection_doc["datasets"] for r in d["file_roles"]}
    templates = set(collection_doc["result_collections"][0]["has_claim_template"])
    used = {e["object"] for e in claims_doc["used_edges"]}
    for claim in claims_doc["claims"]:
        assert set(claim["was_derived_from"]) <= result_files
    assert templates <= used and used & result_files


# ---------------------------------------------------------------------------
# value locators
# ---------------------------------------------------------------------------
def test_every_example_value_locator_matches_its_file_bytes(example_docs):
    checked = 0
    for name, doc in example_docs.items():
        files = {f["id"]: f for f in doc.get("files") or []}
        for locator in doc.get("value_locators") or []:
            file = files[locator["file"]]
            data = (EXAMPLES / file["location"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == file["sha256"], name
            assert len(data) == file["size_in_bytes"], name
            span = data[locator["byte_start"]:locator["byte_start"] + locator["byte_length"]]
            assert span.decode("utf-8") == locator["value_text"], (name, locator["id"])
            checked += 1
    assert checked, "no example exercises ValueLocator"


def test_value_grounded_evidence_needs_a_target_and_explanation(claims_doc, tmp_path,
                                                                 vocab, sv, validator):
    doc = copy.deepcopy(claims_doc)
    del doc["evidence_items"][0]["explanation"]
    report = lint_doc(doc, tmp_path, vocab, sv, validator, profile=None)
    assert any(f.check == "nodes" and "explanation" in f.message for f in report.errors), \
        [f.render() for f in report.errors]


def test_value_grounded_evidence_needs_no_source_claim(claims_doc, tmp_path, vocab, sv, validator):
    assert "source_claims" not in claims_doc["evidence_items"][0]
    report = lint_doc(claims_doc, tmp_path, vocab, sv, validator, profile=None)
    assert [f for f in report.errors if f.check != "profile"] == []


# ---------------------------------------------------------------------------
# lint: datasets fit their collection
# ---------------------------------------------------------------------------
def test_example_collection_lints_clean_without_warnings(tmp_path, collection_doc, vocab, sv, validator):
    report = lint_doc(collection_doc, tmp_path, vocab, sv, validator, profile=None)
    assert report.profile == "result-collection"
    assert report.errors == [] and report.warnings == [], [f.render() for f in report.findings]


def test_missing_dimension_is_rejected(collection_doc, tmp_path, vocab, sv, validator):
    collection_doc["datasets"][0]["dimension_values"].pop()
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert findings(report)


def test_two_datasets_with_the_same_dimension_values_are_rejected(collection_doc, tmp_path,
                                                                  vocab, sv, validator):
    first, second = collection_doc["datasets"]
    second["dimension_values"] = copy.deepcopy(first["dimension_values"])
    second["trait"] = first["trait"]
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert any("same dimension values" in f.message for f in findings(report))


def test_trait_dimension_must_agree_with_trait_slot(collection_doc, tmp_path, vocab, sv, validator):
    collection_doc["datasets"][0]["trait"] = "EXTRAIT:T9"
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert any("disagrees" in f.message for f in findings(report))


def test_role_file_must_be_listed_in_has_file(collection_doc, tmp_path, vocab, sv, validator):
    first, second = collection_doc["datasets"]
    first["file_roles"][0]["file"] = second["has_file"][0]
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert any("has_file does not list" in f.message for f in findings(report))


def test_mixed_methods_warn(collection_doc, tmp_path, vocab, sv, validator):
    collection_doc["result_collections"][0]["methods"].append("OtherMethod")
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert report.errors == []
    assert any("anti-pattern" in f.why for f in findings(report, severity="warning"))


def test_file_from_an_unlisted_method_warns(collection_doc, tmp_path, vocab, sv, validator):
    collection_doc["activities"][0]["software_name"] = "OtherMethod"
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert any("does not list" in f.message for f in findings(report, severity="warning"))


def test_n_members_must_match_members(collection_doc, tmp_path, vocab, sv, validator):
    collection_doc["result_collections"][0]["n_members"] = 3
    report = lint_doc(remint(collection_doc, sv), tmp_path, vocab, sv, validator)
    assert any("n_members" in f.where for f in findings(report))


def _add_previous(collection_doc, **changes):
    previous = copy.deepcopy(collection_doc["result_collections"][0])
    previous.update(id="tmp:previous", version="2026.10.0", **changes)
    collection_doc["result_collections"].insert(0, previous)
    collection_doc["result_collections"][1]["was_revision_of"] = "tmp:previous"
    return collection_doc


def test_revision_within_one_collection_is_accepted(collection_doc, tmp_path, vocab, sv, validator):
    doc = remint(_add_previous(collection_doc), sv)
    # Two versions in one document: the older one is upstream of the newer,
    # so the newer is the only end result.
    report = lint_doc(doc, tmp_path, vocab, sv, validator)
    assert report.errors == [], [f.render() for f in report.errors]


def test_revision_of_another_collection_is_rejected(collection_doc, tmp_path, vocab, sv, validator):
    doc = remint(_add_previous(collection_doc, collection_key="some-other-collection"), sv)
    report = lint_doc(doc, tmp_path, vocab, sv, validator)
    assert any("different collection" in f.message
               for f in findings(report, check="collection-version"))


GENE_SET_ROWS = EXAMPLES / "example_geneset_collection_rows.yaml"


def test_gene_set_libraries_can_be_versioned(tmp_path, vocab, sv, validator):
    """GeneSetCollection inherits versioning from Collection; old ids are kept."""
    doc = yaml.safe_load(GENE_SET_ROWS.read_text())
    library = doc["gene_set_collections"][0]
    unversioned = library["id"]
    assert compute_id({k: v for k, v in library.items() if k != "id"},
                      "GeneSetCollection", sv) == unversioned
    library.update(collection_key="example-library", version="v1")
    assert remint(doc, sv)["gene_set_collections"][0]["id"] != unversioned
    report = lint_doc(doc, tmp_path, vocab, sv, validator, profile="geneset")
    assert report.errors == [], [f.render() for f in report.errors]


def test_a_revision_must_keep_its_class(collection_doc, tmp_path, vocab, sv, validator):
    doc = yaml.safe_load(GENE_SET_ROWS.read_text())
    library = doc["gene_set_collections"][0]
    library.update(collection_key="example-gene-associations", version="v1")
    remint(doc, sv)
    merged = {**collection_doc, **{k: v for k, v in doc.items()
                                   if k not in collection_doc and k != "_illustrative"}}
    merged["prefixes"] = {**doc.get("prefixes", {}), **collection_doc.get("prefixes", {})}
    merged["result_collections"][0]["was_revision_of"] = library["id"]
    report = lint_doc(remint(merged, sv), tmp_path, vocab, sv, validator)
    assert any("different collection" in f.message
               for f in findings(report, check="collection-version"))
