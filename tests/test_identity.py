"""Unit tests for schema/identity/dapper_identity.py — the minting algorithm.

lint_identity.py already checks the SCHEMA-WIDE invariants (every Node marked,
every class hashable, no dotted terms) and `verify-vectors` replays the frozen
fixtures. Neither exercises the functions directly, so this file covers the
behaviour underneath them, and adds a regression test per bug the docstring in
lint_identity.py records as having actually happened.
"""
from __future__ import annotations

import copy
import json

import pytest

from dapper_identity import (
    CURIE_PREFIX,
    DOC_GROUPS,
    VECTORS_PATH,
    assign_ids,
    compute_digest,
    compute_id,
    digest_of,
    hashable_slot_names,
    sha512t24u,
    verify,
)


# --------------------------------------------------------------------------
# the digest primitive
# --------------------------------------------------------------------------
def test_sha512t24u_matches_the_ga4gh_vrs_spec_vector():
    """Proves our primitive is byte-compatible with GA4GH VRS. Never change this."""
    assert sha512t24u(b"ACGT") == "aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2"


def test_digest_is_32_urlsafe_chars_with_no_padding():
    d = sha512t24u(b"anything at all")
    assert len(d) == 32
    assert "=" not in d and "+" not in d and "/" not in d


# --------------------------------------------------------------------------
# digest_of — the id parser
# --------------------------------------------------------------------------
@pytest.mark.parametrize("identifier,expected", [
    ("dapper:Dataset.UIypYwZSXzkH0bQAutCVyev07HmQZZp8", "UIypYwZSXzkH0bQAutCVyev07HmQZZp8"),
    ("dapper:Dataset.", None),          # dot but no digest
    ("dapper:Dataset", None),           # no dot at all
    ("orcid:0000-0002-1825-0097", None),
    ("MONDO:0005148", None),
    ("s3://bucket/key.json", None),     # a dot, but not our prefix
    ("https://example.org/x.y", None),
    ("", None),
    (None, None),
    (42, None),
])
def test_digest_of_only_unpacks_our_own_identifiers(identifier, expected):
    assert digest_of(identifier) == expected


def test_digest_of_partitions_on_the_FIRST_dot():
    """Why lint rule 9 exists: a self-defined term with a dot would be truncated."""
    assert digest_of("dapper:Foo.v2.bar") == "v2.bar"


# --------------------------------------------------------------------------
# what constitutes identity
# --------------------------------------------------------------------------
def test_id_is_never_an_input_to_its_own_digest(sv):
    assert "id" not in hashable_slot_names(sv, "Dataset")


def test_the_identifier_a_node_already_carries_does_not_affect_its_digest(sv):
    """compute_digest blanks self_id first, so re-minting is stable."""
    instance = {"name": "x", "description": "y"}
    bare = compute_digest(instance, "Dataset", sv)
    with_self = compute_digest(instance, "Dataset", sv, self_id="dapper:Dataset." + "A" * 32)
    assert bare == with_self


def test_compute_id_is_prefix_class_digest(sv):
    got = compute_id({"name": "x"}, "Dataset", sv)
    prefix, _, rest = got.partition(":")
    cls, _, digest = rest.partition(".")
    assert prefix == CURIE_PREFIX
    assert cls == "Dataset"
    assert len(digest) == 32


def test_class_name_is_part_of_the_identity(sv):
    """Identical content under a different class is a different thing."""
    content = {"name": "hypoxia response program"}
    assert compute_digest(content, "GeneSet", sv) != compute_digest(content, "GeneProgram", sv)


def test_unhashable_slots_do_not_move_the_digest(sv):
    """Only `hashable` slots constitute identity; the rest are free to change."""
    from dapper_identity import unmarked_slots
    assert unmarked_slots(sv, "Dataset") == [], "every Dataset slot must declare a marker"


# --------------------------------------------------------------------------
# whole-document assignment
# --------------------------------------------------------------------------
def test_assign_ids_is_idempotent(sv):
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}, {"id": "tmp-2", "name": "two"}]}
    assign_ids(doc, sv)
    first = [n["id"] for n in doc["datasets"]]
    assign_ids(doc, sv)
    assert [n["id"] for n in doc["datasets"]] == first


def test_assign_ids_rewrites_references_to_the_new_ids(sv):
    doc = {
        "activities": [{"id": "old-activity", "name": "run"}],
        "c2m2_files": [{"id": "old-file", "name": "out.tsv"}],
        "used_edges": [{"subject": "old-activity", "predicate": "prov:used", "object": "old-file"}],
    }
    assign_ids(doc, sv)
    edge = doc["used_edges"][0]
    assert edge["subject"] == doc["activities"][0]["id"]
    assert edge["object"] == doc["c2m2_files"][0]["id"]
    assert "old-" not in edge["subject"] + edge["object"]


@pytest.mark.parametrize("external", [
    "orcid:0000-0002-1825-0097",
    "ror:02mtd9m52",
])
def test_minting_never_overwrites_an_external_identifier(sv, external):
    """Regression: broadinstitute/dapper#1 — nodes whose id WAS their ORCID/ROR
    had both the id and the external field rewritten to a DAPPER digest."""
    doc = {"agents": [{"id": external, "name": "someone"}]}
    assign_ids(doc, sv)
    node = doc["agents"][0]
    assert node["id"] == external, "an ORCID/ROR is authoritative — leave it alone"


def test_verify_is_clean_on_a_freshly_minted_document(sv):
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}, {"id": "tmp-2", "name": "two"}]}
    assign_ids(doc, sv)
    assert verify(doc, sv) == []


def test_verify_catches_content_edited_after_minting(sv):
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}]}
    assign_ids(doc, sv)
    tampered = copy.deepcopy(doc)
    tampered["datasets"][0]["name"] = "something else"
    problems = verify(tampered, sv)
    assert len(problems) == 1 and "Dataset" in problems[0]


def test_verify_catches_a_hand_written_identifier(sv):
    doc = {"datasets": [{"id": "dapper:Dataset." + "A" * 32, "name": "one"}]}
    assert verify(doc, sv), "an id that does not match its content must be reported"


# --------------------------------------------------------------------------
# the frozen fixtures
# --------------------------------------------------------------------------
def _vectors():
    return json.loads(VECTORS_PATH.read_text())["vectors"]


@pytest.mark.parametrize("vec", _vectors(), ids=lambda v: v["name"])
def test_every_permanent_vector_still_reproduces(vec, sv):
    """From trusty-identifiers.md: fix the code, never the vectors."""
    assert compute_id(vec["instance"], vec["class"], sv) == vec["expected_id"], vec.get("note", "")


def test_vector_classes_all_exist_in_the_schema(sv):
    for vec in _vectors():
        assert sv.get_class(vec["class"]) is not None, f"{vec['class']} is not in dapper.yaml"


# --------------------------------------------------------------------------
# DOC_GROUPS — the map the portal and the minter share
# --------------------------------------------------------------------------
def test_doc_groups_names_only_real_classes(sv):
    for group, class_name in DOC_GROUPS.items():
        assert sv.get_class(class_name) is not None, f"{group} -> {class_name} does not exist"


def test_doc_groups_covers_every_concrete_hashable_node(sv):
    """Regression: a class present in the schema but absent from DOC_GROUPS is
    invisible to both the minter and the portal — the drift that once rendered
    an 18-node document as 1 node."""
    mapped = set(DOC_GROUPS.values())
    missing = [
        c for c in sv.all_classes()
        if not sv.get_class(c).abstract
        and not sv.get_class(c).mixin
        and "HashableNode" in sv.class_ancestors(c)
        and c not in mapped and c != "HashableNode"
    ]
    assert missing == [], f"add these to DOC_GROUPS: {missing}"


def test_the_portal_reads_the_same_groups_as_the_minter():
    """portal/build.py parses DOC_GROUPS out of the source rather than importing
    it; this asserts that parse still agrees with the real dict."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal"))
    from build import NODE_GROUPS

    assert NODE_GROUPS == DOC_GROUPS
