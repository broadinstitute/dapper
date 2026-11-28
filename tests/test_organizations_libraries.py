"""Organizations that belong to larger ones, and gene-set libraries that let a gene
reach the program its gene set came from: gene -> GeneSet -> GeneSetCollection ->
GeneSetLibrary -> program Organization -> parent Organization."""
from copy import deepcopy

import pytest

from conftest import SCHEMA
from dapper_identity import assign_ids, compute_id, verify
import lint_provenance as lp


@pytest.fixture(scope="module")
def validator():
    return lp.build_validator(SCHEMA)


def document():
    return {
        "prefixes": {"HGNC.SYMBOL": "https://identifiers.org/hgnc.symbol:"},
        "organizations": [
            {"id": "local:nih", "name": "National Institutes of Health", "ror": "ror:01cwqze88"},
            {"id": "local:cfde", "name": "Common Fund Data Ecosystem (CFDE)", "parent_organization": "local:nih",
             "url": "https://commonfund.nih.gov/dataecosystem"},
            {"id": "local:gtex", "name": "The Genotype-Tissue Expression Project (GTEx)",
             "parent_organization": "local:cfde", "url": "https://gtexportal.org/home/"},
        ],
        "datasets": [{"id": "local:gtex-v8", "name": "GTEx Analysis V8", "was_attributed_to": ["local:gtex"]}],
        "gene_sets": [{"id": "local:set", "name": "Illustrative aging set up", "member_type": "gene",
                       "members": ["HGNC.SYMBOL:CD1E", "HGNC.SYMBOL:CYP1A1"], "n_genes": 2,
                       "in_gene_set_collection": ["local:collection"]}],
        "gene_set_collections": [{"id": "local:collection", "name": "Illustrative aging collection",
                                  "members": ["local:set"], "n_members": 1}],
        "gene_set_libraries": [{"id": "local:library", "name": "GTEx", "collection_key": "cfde-gtex",
                                "version": "2026.11", "members": ["local:collection"], "n_members": 1,
                                "n_sets": 1, "was_attributed_to": ["local:gtex"],
                                "was_derived_from": ["local:gtex-v8"]}],
    }


def by_id(doc, group, nid):
    return next(r for r in doc[group] if r["id"] == nid)


def test_classes(sv):
    assert "Collection" in sv.class_ancestors("GeneSetLibrary")
    assert sv.induced_slot("parent_organization", "Organization").range == "Organization"
    assert sv.induced_slot("members", "GeneSetLibrary").range == "GeneSetCollection"


def test_records_validate(validator):
    doc = document()
    for group, cls in (("organizations", "Organization"), ("gene_set_libraries", "GeneSetLibrary")):
        for r in doc[group]:
            assert not validator.validate(r, cls).results, r
    library = doc["gene_set_libraries"][0]
    assert validator.validate({**library, "members": []}, "GeneSetLibrary").results
    assert validator.validate({**library, "member_type": "gene_set"}, "GeneSetLibrary").results


def test_minted_chain_reaches_the_top_organization(sv):
    doc = document()
    mapping = assign_ids(doc, sv)
    assert verify(doc, sv) == []
    orgs = {o["id"]: o for o in doc["organizations"]}
    gene_set = doc["gene_sets"][0]
    collection = gene_set["in_gene_set_collection"][0]
    library = next(l for l in doc["gene_set_libraries"] if collection in l["members"])
    org, chain = library["was_attributed_to"][0], []
    while org:
        chain.append(orgs[org]["name"])
        org = orgs[org].get("parent_organization")
    assert chain == ["The Genotype-Tissue Expression Project (GTEx)", "Common Fund Data Ecosystem (CFDE)",
                     "National Institutes of Health"]
    assert mapping["local:set"].startswith("dapper:GeneSet.")


def test_parent_is_part_of_identity(sv):
    doc = document()
    assign_ids(doc, sv)
    gtex = deepcopy(doc["organizations"][2])
    alone = {k: v for k, v in gtex.items() if k != "parent_organization"}
    assert compute_id(gtex, "Organization", sv) != compute_id(alone, "Organization", sv)


def test_library_membership_leaves_collection_and_set_ids_alone(sv):
    with_library, without = document(), document()
    del without["gene_set_libraries"]
    a, b = assign_ids(with_library, sv), assign_ids(without, sv)
    for local in ("local:set", "local:collection", "local:gtex"):
        assert a[local] == b[local]


def test_parent_cycle_cannot_be_minted(sv):
    doc = document()
    by_id(doc, "organizations", "local:nih")["parent_organization"] = "local:gtex"
    with pytest.raises(Exception):
        assign_ids(doc, sv)
