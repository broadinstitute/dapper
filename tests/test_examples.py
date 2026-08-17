"""Tests over schema/examples/*.yaml — the documents shipped as the model's
worked examples and rendered by the portal.

These are the files a reader is most likely to copy, and the ones the portal
embeds, so a stale identifier in one of them is a published lie rather than a
local mistake. That is exactly the failure this catches: PR #13 carried three
example ids that no longer matched their content.
"""
from __future__ import annotations

import pytest
import yaml

from conftest import EXAMPLES
from dapper_identity import DOC_GROUPS, digest_of, verify

EXAMPLE_FILES = sorted(EXAMPLES.glob("*.yaml"))
# Documents that carry `id`-bearing nodes in DOC_GROUPS buckets, i.e. everything
# minting applies to. Single-class illustrations without an id are skipped.
GRAPH_FILES = [p for p in EXAMPLE_FILES
               if set(yaml.safe_load(p.read_text()) or {}) & set(DOC_GROUPS)]


def test_there_are_examples_to_check():
    assert EXAMPLE_FILES, "schema/examples/*.yaml is empty — did the glob break?"
    assert GRAPH_FILES


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_every_example_is_valid_yaml(path):
    assert yaml.safe_load(path.read_text()) is not None


@pytest.mark.parametrize("path", GRAPH_FILES, ids=lambda p: p.name)
def test_every_example_id_matches_its_content(path, sv):
    doc = yaml.safe_load(path.read_text())
    problems = verify(doc, sv)
    assert problems == [], (
        f"{path.name} has stale identifiers — re-mint with schema/identity/mint.py:\n  "
        + "\n  ".join(problems)
    )


@pytest.mark.parametrize("path", GRAPH_FILES, ids=lambda p: p.name)
def test_every_example_node_id_is_a_well_formed_dapper_id(path):
    doc = yaml.safe_load(path.read_text())
    for group in set(doc) & set(DOC_GROUPS):
        for node in doc[group] or []:
            node_id = node.get("id")
            if node_id is None or not str(node_id).startswith("dapper:"):
                continue   # external identifiers (orcid:, ror:) are left as-is
            assert digest_of(node_id), f"{path.name}: malformed id {node_id!r}"


@pytest.mark.parametrize("path", GRAPH_FILES, ids=lambda p: p.name)
def test_no_duplicate_ids_within_an_example(path):
    doc = yaml.safe_load(path.read_text())
    seen: dict[str, str] = {}
    for group in set(doc) & set(DOC_GROUPS):
        for node in doc[group] or []:
            node_id = node.get("id")
            if node_id is None:
                continue
            assert node_id not in seen, f"{path.name}: {node_id} appears in {seen[node_id]} and {group}"
            seen[node_id] = group


@pytest.mark.parametrize("path", GRAPH_FILES, ids=lambda p: p.name)
def test_illustrative_list_points_at_nodes_that_exist(path):
    """`_illustrative:` is what the portal reads to mark a node as drawn-for-shape
    rather than transcribed from a real run. A dangling entry silently mislabels
    a real node as illustrative."""
    doc = yaml.safe_load(path.read_text())
    declared = doc.get("_illustrative") or []
    present = {n.get("id") for g in set(doc) & set(DOC_GROUPS) for n in doc[g] or []}
    dangling = [i for i in declared if i not in present]
    assert dangling == [], f"{path.name}: _illustrative names absent nodes {dangling}"
