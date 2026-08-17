"""Unit tests for schema/converter/geneset_to_dapper.py.

The converter implements the crosswalk in
schema/docs/geneset-provenance-nih-dapp-adaptation.md. The parts worth pinning
down are the ones where dig.geneset and NIH-DAPP disagree in shape:

  * edge DIRECTION — dig.geneset draws file --(data input)--> analysis, PROV
    says activity prov:used entity. Getting this backwards produces a graph
    that still validates and still renders, and is wrong.
  * sha256 — dig.geneset File nodes carry MD5 only; SHA-256 lives in the
    metadata sidecar and has to be joined across on local_id/path.
  * overlay — NIH attribution is not in dig.geneset at all, and must never
    overwrite a value the source data did supply.

Fixture: the real HuBMAP HZ2 run (9 File / 2 AnalysisType / 1 GeneSet nodes,
3 data-input and 8 data-output edges), not a hand-written miniature.
"""
from __future__ import annotations

import yaml

from geneset_to_dapper import (
    _activity,
    _c2m2_file,
    _clean,
    _find_pairs,
    _gene_set,
    apply_overlay,
    convert_graph,
    convert_one,
)
from conftest import HZ2


# --------------------------------------------------------------------------
# _clean
# --------------------------------------------------------------------------
def test_clean_drops_empty_values_but_keeps_falsy_data():
    out = _clean({"a": None, "b": "", "c": [], "d": {}, "e": 0, "f": False, "g": "x"})
    assert out == {"e": 0, "f": False, "g": "x"}, (
        "0 and False are real values — only None/''/[]/{} are absent"
    )


# --------------------------------------------------------------------------
# node mapping
# --------------------------------------------------------------------------
def test_c2m2_file_joins_sha256_from_the_metadata_sidecar():
    node = {
        "id": "n1",
        "name": "geneset.tsv",
        "c2m2_properties": {"local_id": "s3://bucket/geneset.tsv", "md5": "abc", "filename": "geneset.tsv"},
    }
    sha = {"s3://bucket/geneset.tsv": "deadbeef"}
    out = _c2m2_file(node, sha)
    assert out["md5"] == "abc"
    assert out["sha256"] == "deadbeef"


def test_c2m2_file_without_a_sidecar_entry_simply_omits_sha256():
    node = {"id": "n1", "c2m2_properties": {"local_id": "s3://bucket/other.tsv"}}
    assert "sha256" not in _c2m2_file(node, {})


def test_activity_lifts_environment_fields_and_synonyms_to_aliases():
    node = {
        "id": "a1",
        "analysis": {
            "command": "run.py --x",
            "version": "1.2.3",
            "environment": {"repo_url": "https://example/repo", "container_image": "img:1"},
        },
        "c2m2_properties": {"synonyms": ["alt-name"]},
    }
    out = _activity(node)
    assert out["command"] == "run.py --x"
    assert out["code_version"] == "1.2.3", "analysis.version -> code_version"
    assert out["repo_url"] == "https://example/repo"
    assert out["container_image"] == "img:1"
    assert out["aliases"] == ["alt-name"]


def test_gene_set_merges_the_three_metadata_sections(hz2_meta):
    node = {"id": "gs1", "name": "unsigned_term_gene:402cf4a1"}
    out = _gene_set(node, hz2_meta)
    assert out["member_type"] == "gene"
    assert out["assay"] == "bulk"                 # meta.gene_set
    assert out["organism"] == "human"             # meta.gene_set
    assert out["n_genes"] == 1747                 # meta.gene_set
    assert out["n_sets"] == 487                   # meta.summary.n_sets_emitted
    assert out["term_prefix"] == "HuBMAP"         # meta.converter.parameters


def test_gene_set_prefers_the_nodes_own_description_over_the_sidecars():
    node = {"id": "gs1", "description": "from the node"}
    out = _gene_set(node, {"gene_set": {"description": "from the sidecar"}})
    assert out["description"] == "from the node"


# --------------------------------------------------------------------------
# convert_graph — the whole HZ2 graph
# --------------------------------------------------------------------------
def test_convert_graph_routes_every_node_type_to_its_bucket(hz2_graph, hz2_meta):
    doc = convert_graph(hz2_graph, hz2_meta)
    assert len(doc["c2m2_files"]) == 9
    assert len(doc["activities"]) == 2
    assert len(doc["gene_sets"]) == 1


def test_used_edges_reverse_direction_relative_to_dig_geneset(hz2_graph, hz2_meta):
    """dig: file --(data input)--> analysis.  PROV: activity prov:used entity."""
    doc = convert_graph(hz2_graph, hz2_meta)
    dig_inputs = [e for e in hz2_graph["edges"] if e["label"] in ("data input", "metadata input")]
    assert len(doc["used_edges"]) == len(dig_inputs) == 3

    for dig, dapper in zip(dig_inputs, doc["used_edges"]):
        assert dapper["predicate"] == "prov:used"
        assert dapper["subject"] == dig["target"], "subject is the ANALYSIS, dig's target"
        assert dapper["object"] == dig["source"], "object is the FILE, dig's source"


def test_was_generated_by_edges_also_reverse(hz2_graph, hz2_meta):
    """dig: analysis --(data output)--> file.  PROV: file prov:wasGeneratedBy activity."""
    doc = convert_graph(hz2_graph, hz2_meta)
    dig_outputs = [e for e in hz2_graph["edges"] if e["label"] == "data output"]
    assert len(doc["was_generated_by_edges"]) == len(dig_outputs) == 8

    for dig, dapper in zip(dig_outputs, doc["was_generated_by_edges"]):
        assert dapper["predicate"] == "prov:wasGeneratedBy"
        assert dapper["subject"] == dig["target"], "subject is the FILE, dig's target"
        assert dapper["object"] == dig["source"], "object is the ACTIVITY, dig's source"


def test_edge_role_records_which_kind_of_input_it_was(hz2_graph, hz2_meta):
    doc = convert_graph(hz2_graph, hz2_meta)
    roles = {e.get("edge_role") for e in doc["used_edges"]}
    assert roles <= {"data_input", "metadata_input"}
    assert roles, "the data/metadata input distinction must survive the conversion"


def test_unknown_node_and_edge_kinds_are_skipped_not_crashed(capsys):
    graph = {
        "nodes": [{"id": "x", "type": "Sasquatch"}],
        "edges": [{"source": "a", "target": "b", "label": "vibes"}],
    }
    doc = convert_graph(graph, {})
    assert doc == {}, "nothing recognised, so nothing emitted"
    err = capsys.readouterr().err
    assert "Sasquatch" in err and "vibes" in err, "but both are reported, not silent"


def test_empty_buckets_are_dropped_from_the_output(hz2_graph, hz2_meta):
    doc = convert_graph({"nodes": [], "edges": []}, hz2_meta)
    assert doc == {}


# --------------------------------------------------------------------------
# overlay
# --------------------------------------------------------------------------
def test_overlay_fills_missing_attribution():
    gs = {"id": "gs1"}
    apply_overlay(gs, {"has_creator": ["orcid:0000-0002-1825-0097"]})
    assert gs["has_creator"] == ["orcid:0000-0002-1825-0097"]


def test_overlay_never_overwrites_a_value_the_source_data_supplied():
    gs = {"id": "gs1", "has_creator": ["orcid:REAL"]}
    apply_overlay(gs, {"has_creator": ["orcid:OVERLAY"]})
    assert gs["has_creator"] == ["orcid:REAL"], "setdefault, not update"


def test_overlay_of_none_is_a_no_op():
    gs = {"id": "gs1"}
    apply_overlay(gs, None)
    assert gs == {"id": "gs1"}


# --------------------------------------------------------------------------
# input discovery
# --------------------------------------------------------------------------
def test_find_pairs_discovers_the_sibling_sidecar():
    pairs = _find_pairs(HZ2)
    assert len(pairs) == 1
    prov, meta = pairs[0]
    assert prov.name == "geneset.provenance.json"
    assert meta is not None and meta.name == "geneset.meta.json"


def test_find_pairs_reports_a_missing_sidecar_as_none(tmp_path):
    (tmp_path / "geneset.provenance.json").write_text("{}")
    (prov, meta), = _find_pairs(tmp_path)
    assert meta is None, "a sparse run is allowed, not an error"


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------
def test_convert_one_writes_a_minted_graph_and_focus_node(tmp_path, sv):
    from dapper_identity import verify

    written = convert_one(HZ2 / "geneset.provenance.json", HZ2 / "geneset.meta.json",
                          tmp_path, overlay={})
    names = sorted(p.name for p in written)
    assert names == ["402cf4a1f3682a2e5bf1b002.dapper.yaml",
                     "402cf4a1f3682a2e5bf1b002.geneset.yaml"]

    doc = yaml.safe_load((tmp_path / "402cf4a1f3682a2e5bf1b002.dapper.yaml").read_text())

    # dig.geneset's UUIDv5 / 24-hex ids are gone, replaced by content digests.
    ids = [n["id"] for bucket in ("c2m2_files", "activities", "gene_sets") for n in doc[bucket]]
    assert ids and all(i.startswith("dapper:") for i in ids)

    # and the ids actually match the content they name
    assert verify(doc, sv) == []


def test_convert_one_is_deterministic(tmp_path, sv):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    convert_one(HZ2 / "geneset.provenance.json", HZ2 / "geneset.meta.json", a, overlay={})
    convert_one(HZ2 / "geneset.provenance.json", HZ2 / "geneset.meta.json", b, overlay={})
    for f in sorted(p.name for p in a.iterdir()):
        assert (a / f).read_text() == (b / f).read_text(), f"{f} is not reproducible"


def test_edges_point_at_ids_that_exist_after_minting(tmp_path):
    """Re-minting rewrites node ids; the edges have to be rewritten with them."""
    convert_one(HZ2 / "geneset.provenance.json", HZ2 / "geneset.meta.json", tmp_path, overlay={})
    doc = yaml.safe_load((tmp_path / "402cf4a1f3682a2e5bf1b002.dapper.yaml").read_text())

    known = {n["id"] for b in ("c2m2_files", "activities", "gene_sets") for n in doc[b]}
    for bucket in ("used_edges", "was_generated_by_edges"):
        for e in doc.get(bucket, []):
            assert e["subject"] in known, f"dangling subject {e['subject']} in {bucket}"
            assert e["object"] in known, f"dangling object {e['object']} in {bucket}"
