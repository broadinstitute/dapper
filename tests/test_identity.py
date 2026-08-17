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
    """Our digest primitive is byte-compatible with GA4GH VRS.

    Taken verbatim from the VRS specification. Interoperability with ga4gh:
    identifiers rests entirely on this one value, so it is a fixture, not an
    expectation: if it ever fails, fix the code, never this line.
    """
    assert sha512t24u(b"ACGT") == "aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2"


def test_digest_is_32_urlsafe_chars_with_no_padding():
    """The digest is safe to paste into a URL or a CURIE without escaping.

    24 bytes is divisible by 3, so base64 emits no `=` padding and needs no
    stripping logic. urlsafe_b64encode also rules out `+` and `/`, which would
    otherwise have to be percent-encoded wherever an id appears in a path.
    """
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
    """Only a well-formed `dapper:Class.digest` yields a digest; everything else is None.

    digest_of is what tells a DAPPER reference apart from an external identifier
    that merely resembles one, and _substitute() calls it on every value it
    hashes. If an ORCID, MONDO term or s3:// URL were misread as one of ours it
    would be replaced by a fragment of itself inside the digest input, silently
    changing the identifier of anything that cites it.
    """
    assert digest_of(identifier) == expected


def test_digest_of_partitions_on_the_FIRST_dot():
    """A dot inside a local name is swallowed — which is why lint rule 9 exists.

    Parsing splits on the first dot, so a self-defined predicate such as
    `dapper:Foo.v2` would be read as class `Foo` with digest `v2` and truncated.
    lint_identity.py rule 9 forbids dotted terms precisely because this parser
    cannot tell the two apart.
    """
    assert digest_of("dapper:Foo.v2.bar") == "v2.bar"


# --------------------------------------------------------------------------
# what constitutes identity
# --------------------------------------------------------------------------
def test_id_is_never_an_input_to_its_own_digest(sv):
    """`id` is the output of the digest, so it can never also be an input.

    Including it would make minting non-idempotent — every re-mint would hash a
    different id and produce a different one again.
    """
    assert "id" not in hashable_slot_names(sv, "Dataset")


def test_the_identifier_a_node_already_carries_does_not_affect_its_digest(sv):
    """An id embedded in a node's own content is blanked before hashing.

    Excluding the `id` slot is not enough on its own: a node can mention its own
    identifier inside a description or a self-reference. compute_digest() blanks
    self_id first, which is what lets the same content mint to the same digest
    whether it arrives bare or already identified.
    """
    instance = {"name": "x", "description": "y"}
    bare = compute_digest(instance, "Dataset", sv)
    with_self = compute_digest(instance, "Dataset", sv, self_id="dapper:Dataset." + "A" * 32)
    assert bare == with_self


def test_compute_id_is_prefix_class_digest(sv):
    """A minted id has exactly the three-part shape the rest of the system parses.

    portal/build.py splits ids for display and digest_of() unpacks them for
    substitution, so the `dapper:{ClassName}.{32 chars}` shape is a contract,
    not just a formatting choice.
    """
    got = compute_id({"name": "x"}, "Dataset", sv)
    prefix, _, rest = got.partition(":")
    cls, _, digest = rest.partition(".")
    assert prefix == CURIE_PREFIX
    assert cls == "Dataset"
    assert len(digest) == 32


def test_class_name_is_part_of_the_identity(sv):
    """Identical content under a different class is a different thing.

    The class name is hashed, not just prefixed onto the result. This is what
    made GeneProgram's id change when PR #4 renamed it from CellProgram even
    though its content had not moved — see the note on the minimal-gene-program
    vector.
    """
    content = {"name": "hypoxia response program"}
    assert compute_digest(content, "GeneSet", sv) != compute_digest(content, "GeneProgram", sv)


def test_unmarked_slots_are_a_schema_error_not_a_default(sv):
    """Every slot must declare `hashable` or `unhashable` — silence is not allowed.

    An unmarked slot would default into one bucket or the other by accident,
    quietly deciding whether editing that field changes the identifier. The
    schema is required to state it, which is why lint rule 1 exists; this checks
    the same property from the function that reports it.
    """
    from dapper_identity import unmarked_slots
    assert unmarked_slots(sv, "Dataset") == [], "every Dataset slot must declare a marker"


# --------------------------------------------------------------------------
# whole-document assignment
# --------------------------------------------------------------------------
def test_assign_ids_is_idempotent(sv):
    """Re-minting an already-minted document changes nothing.

    mint.py's contract is that running it twice on unchanged data reproduces the
    file exactly, so that a changed id is a real signal about changed content
    rather than churn.
    """
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}, {"id": "tmp-2", "name": "two"}]}
    assign_ids(doc, sv)
    first = [n["id"] for n in doc["datasets"]]
    assign_ids(doc, sv)
    assert [n["id"] for n in doc["datasets"]] == first


def test_assign_ids_rewrites_references_to_the_new_ids(sv):
    """Replacing a node's id also updates everything that pointed at it.

    Minting rewrites ids across a whole document, so edges still holding the old
    value would dangle. Nothing downstream catches that — the document still
    parses and still validates class by class — so it is asserted here.
    """
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
    """An ORCID or ROR is authoritative and must survive minting untouched.

    Regression for broadinstitute/dapper#1: nodes whose id WAS their external
    identifier had both the id and the field rewritten to a DAPPER digest,
    destroying the only globally resolvable name the record had. Re-minting a
    person must not sever them from their ORCID.
    """
    doc = {"agents": [{"id": external, "name": "someone"}]}
    assign_ids(doc, sv)
    node = doc["agents"][0]
    assert node["id"] == external, "an ORCID/ROR is authoritative — leave it alone"


def test_verify_is_clean_on_a_freshly_minted_document(sv):
    """The two halves of the system agree: what assign_ids writes, verify accepts.

    Baseline for the two tests below — without it, a `verify` that rejected
    everything would make them pass for the wrong reason.
    """
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}, {"id": "tmp-2", "name": "two"}]}
    assign_ids(doc, sv)
    assert verify(doc, sv) == []


def test_verify_catches_content_edited_after_minting(sv):
    """Editing a hashable field without re-minting is detected.

    This is the drift the whole scheme exists to prevent: an identifier that no
    longer describes its content is a name that lies. It is also the exact bug
    found in example_bottom_line_result.yaml and example_graph.yaml.
    """
    doc = {"datasets": [{"id": "tmp-1", "name": "one"}]}
    assign_ids(doc, sv)
    tampered = copy.deepcopy(doc)
    tampered["datasets"][0]["name"] = "something else"
    problems = verify(tampered, sv)
    assert len(problems) == 1 and "Dataset" in problems[0]


def test_verify_catches_a_hand_written_identifier(sv):
    """A plausible-looking id that was never computed is still rejected.

    From the minter's docstring: you do not write ids by hand, ever. A
    well-formed but invented digest is indistinguishable from a real one by
    shape alone, so only recomputation can tell them apart.
    """
    doc = {"datasets": [{"id": "dapper:Dataset." + "A" * 32, "name": "one"}]}
    assert verify(doc, sv), "an id that does not match its content must be reported"


# --------------------------------------------------------------------------
# the frozen fixtures
# --------------------------------------------------------------------------
def _vectors():
    return json.loads(VECTORS_PATH.read_text())["vectors"]


@pytest.mark.parametrize("vec", _vectors(), ids=lambda v: v["name"])
def test_every_permanent_vector_still_reproduces(vec, sv):
    """Each frozen vector mints to the identifier recorded for it.

    From trusty-identifiers.md: keep test vectors forever, so that a library
    upgrade cannot silently change published ids. If one fails, fix the code —
    never the vector. A genuine algorithm change is DAPPER-ID-2 under a new
    prefix. Parametrized so a failure names the specific vector.
    """
    assert compute_id(vec["instance"], vec["class"], sv) == vec["expected_id"], vec.get("note", "")


def test_vector_classes_all_exist_in_the_schema(sv):
    """No vector is silently orphaned by a class being renamed or removed.

    A vector naming a class that no longer exists would fail confusingly, or
    stop covering anything at all. Renaming a class changes its digest, so this
    should force the rename to be dealt with deliberately.
    """
    for vec in _vectors():
        assert sv.get_class(vec["class"]) is not None, f"{vec['class']} is not in dapper.yaml"


# --------------------------------------------------------------------------
# DOC_GROUPS — the map the portal and the minter share
# --------------------------------------------------------------------------
def test_doc_groups_names_only_real_classes(sv):
    """Every document-list key maps to a class that actually exists.

    DOC_GROUPS is hand-maintained. An entry pointing at a renamed or deleted
    class would make the minter skip that list, leaving its nodes unminted with
    no error raised.
    """
    for group, class_name in DOC_GROUPS.items():
        assert sv.get_class(class_name) is not None, f"{group} -> {class_name} does not exist"


def test_doc_groups_covers_every_concrete_hashable_node(sv):
    """A new Node class must be added to DOC_GROUPS or it is invisible.

    Regression for the drift recorded in portal/build.py: a class in the schema
    but absent from DOC_GROUPS is skipped by both the minter and the portal —
    which once rendered an 18-node document as a single node. Computed from the
    schema rather than listed, so adding a class fails this test until it is
    registered.
    """
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
    """The portal's text-parsed copy of DOC_GROUPS still matches the real dict.

    portal/build.py re-parses DOC_GROUPS out of the source with a regex instead
    of importing it, to keep the portal free of the rdflib/linkml dependency
    chain. That parse is the thing that can silently drift — a formatting change
    to the dict would break it with no error — so it is compared directly.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal"))
    from build import NODE_GROUPS

    assert NODE_GROUPS == DOC_GROUPS
