"""Tests over schema/lint/lint_provenance.py — the end-modality linter.

Two jobs here, and the second matters more than the first.

  1. The canonical examples lint clean. They are what counterparts are told to
     copy, so a defect in one of them propagates into every document produced
     from it. This is how the invalid `generated_at_time` in
     example_bottom_line_result.yaml was found: it had never been validated,
     because until this linter existed nothing could validate a whole graph
     document.

  2. EVERY CHECK ACTUALLY FIRES. A linter that reports nothing looks identical
     to a clean corpus, and both make CI green. Each check below gets a document
     with exactly one planted defect, so a check that silently stops working
     fails a test instead of quietly passing everything. The `closed=True`
     guard is the sharpest case: flipping it to the library default disables the
     hallucinated-field check completely while leaving every other test green.
"""
from __future__ import annotations

import copy

import pytest
import yaml

from conftest import EXAMPLES, REPO_ROOT, SCHEMA

import lint_provenance as lp


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def profiles_doc() -> dict:
    return yaml.safe_load(lp.PROFILES_PATH.read_text())


@pytest.fixture(scope="session")
def vocab(sv, profiles_doc):
    return lp.Vocabulary.build(sv, profiles_doc)


@pytest.fixture(scope="session")
def validator():
    """Built once — compiling the schema to JSON Schema dominates the runtime."""
    return lp.build_validator(SCHEMA)


@pytest.fixture
def bottom_line() -> dict:
    """The canonical bottom-line document, as a mutable copy to plant defects in."""
    return yaml.safe_load((EXAMPLES / "example_bottom_line_result.yaml").read_text())


def lint_doc(doc: dict, tmp_path, vocab, sv, validator, profile=None) -> lp.Report:
    """Lint an in-memory document by round-tripping it through a temp file."""
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return lp.lint(path, vocab, sv, validator, profile)


def checks_firing(report: lp.Report, severity: str | None = None) -> set[str]:
    return {f.check for f in report.findings
            if severity is None or f.severity == severity}


# ---------------------------------------------------------------------------
# 1. the canonical examples are clean
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile_name", ["bottom-line-result", "geneset"])
def test_canonical_example_lints_clean(profile_name, vocab, sv, validator):
    """Each profile's canonical example passes its own linter.

    The example IS the specification handed to counterparts. If it does not
    pass, every document copied from it inherits the same defect.
    """
    profile = vocab.profiles[profile_name]
    path = REPO_ROOT / profile["canonical_example"]
    report = lp.lint(path, vocab, sv, validator, profile_name)
    assert report.errors == [], (
        f"{path.name} does not lint clean:\n"
        + "\n".join(f.render() for f in report.errors)
    )


def test_every_profile_has_a_canonical_example(vocab):
    """No profile ships without the example it tells people to copy."""
    for name, profile in vocab.profiles.items():
        example = profile.get("canonical_example")
        assert example, f"profile {name} declares no canonical_example"
        assert (REPO_ROOT / example).exists(), f"{name}: {example} does not exist"


def test_profile_autodetection_picks_the_right_modality(vocab, sv, validator):
    """A document is matched to its modality without --profile.

    Auto-detection keys off the terminal class, so this also guards the
    invariant that two profiles never share one.
    """
    for name, profile in vocab.profiles.items():
        path = REPO_ROOT / profile["canonical_example"]
        report = lp.lint(path, vocab, sv, validator, None)
        assert report.profile == name, f"{path.name} detected as {report.profile}, want {name}"


# ---------------------------------------------------------------------------
# 2. every check fires on a planted defect
# ---------------------------------------------------------------------------
def test_hallucinated_node_field_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """An invented field on a node is an error.

    The single most important check: it is the failure mode of a document
    written by hand or by a language model.
    """
    bottom_line["datasets"][0]["p_value_threshold"] = 5e-8
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "nodes" in checks_firing(report, "error")
    assert any("p_value_threshold" in f.message for f in report.errors)


def test_validator_is_built_in_closed_mode(validator):
    """The hallucinated-field check is actually armed.

    REGRESSION GUARD, and the reason it is a standalone test: the in-process
    validator API defaults to `closed=False`, and in that mode invented fields
    are ACCEPTED. A document that the CLI rejects passes clean. If someone
    drops the explicit `closed=True` from build_validator, this is the only
    test that fails — every other test in the suite stays green while the
    linter's primary check quietly does nothing.
    """
    instance = {"id": "dapper:Dataset.x", "name": "probe", "not_a_real_field": 1}
    messages = [r.message for r in validator.validate(instance, "Dataset").results]
    assert any("not_a_real_field" in m for m in messages), (
        "closed mode is off — invented fields are being accepted"
    )


def test_hallucinated_edge_field_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """An invented field on an edge is an error."""
    bottom_line["was_generated_by_edges"][0]["confidence"] = 0.9
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "edges" in checks_firing(report, "error")


def test_unknown_top_level_key_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """An invented container is an error, and says how many nodes it orphans.

    Worse than a hallucinated field, because nothing downstream looks at it: the
    nodes are never validated, never minted and never rendered, while the
    document still parses and still looks complete.
    """
    bottom_line["bottom_line_results"] = [{"id": "dapper:Nope.aaa", "name": "x"}]
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "shape" in checks_firing(report, "error")


def test_mistyped_edge_endpoint_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """An edge pointing at the wrong class of node is an error.

    The schema types both ends as bare `uriorcurie`, so nothing else in the
    stack notices that an Award did not generate anything.
    """
    bottom_line["awards"] = [{"id": "dapper:Award.aLM7MULGQaMPRi38j2clFfvlmJv_JDhG",
                              "name": "Some NIH award"}]
    dataset_id = bottom_line["datasets"][0]["id"]
    bottom_line["was_generated_by_edges"].append({
        "subject": dataset_id,
        "predicate": "prov:wasGeneratedBy",
        "object": "dapper:Award.aLM7MULGQaMPRi38j2clFfvlmJv_JDhG",
    })
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "endpoints" in checks_firing(report, "error")


def test_edge_endpoint_with_a_fabricated_prefix_is_rejected(bottom_line, tmp_path,
                                                            vocab, sv, validator):
    """An edge endpoint that resolves to nothing is an error, whatever its prefix.

    This escaped BOTH checks that should have caught it: `check_endpoints` skipped
    any endpoint it could not resolve, on the assumption that `check_refs` would
    report it, but `check_refs` only chases `dapper:{Class}.{digest}` strings.
    So an endpoint with any other prefix — a plausible but fabricated `MONDO:` or
    `orcid:` term — was silently accepted, and nothing else in the stack objects
    because `uriorcurie` compiles to a bare string that accepts even `''`.
    """
    bottom_line["was_generated_by_edges"].append({
        "subject": bottom_line["datasets"][0]["id"],
        "predicate": "prov:wasGeneratedBy",
        "object": "totallyMadeUpPrefix:whatever",
    })
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "endpoints" in checks_firing(report, "error")


@pytest.mark.parametrize("end", ["subject", "object"])
def test_edge_missing_an_end_is_rejected(end, bottom_line, tmp_path, vocab, sv, validator):
    """An edge with only one end is an error.

    Invisible before this check, and hard to spot: such an edge connects nothing
    to nothing, so it contributes no provenance and trips nothing else. The
    schema marks neither `subject` nor `object` as required, so a half-written
    edge is schema-valid. It first looked caught only because the test document
    happened to put it on a REQUIRED edge, where `required-edges` fired for an
    unrelated reason; in any other group it passed clean.

    Uses `used_edges` with the Dataset as the surviving end, since `Used` permits
    a Dataset on either side — so the only defect is the missing end.
    """
    edge = {"predicate": "prov:used", "edge_role": "data_input",
            "subject": bottom_line["datasets"][0]["id"],
            "object": bottom_line["datasets"][0]["id"]}
    del edge[end]
    bottom_line["used_edges"] = [edge]
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "endpoints" in checks_firing(report, "error")
    assert any(f"no {end}" in f.message for f in report.errors)


def test_edge_with_an_empty_end_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """An end present but blank counts as missing, not as an unresolvable id.

    `uriorcurie` compiles to a bare string in the generated JSON Schema, which
    accepts `''`, so nothing upstream objects.
    """
    bottom_line["was_generated_by_edges"][0]["object"] = "   "
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "endpoints" in checks_firing(report, "error")


def test_external_inline_reference_is_still_allowed(vocab, sv, validator):
    """An inline slot may name something outside the document; an edge may not.

    The other side of the rule above, and the reason it is scoped to edges. A
    curated CellState names its curator as `was_attributed_to: [orcid:...]` with
    no Person node in the file, which is correct and must not be flagged.
    """
    path = REPO_ROOT / "schema/examples/example_cell_graph.yaml"
    doc = yaml.safe_load(path.read_text())
    assert any("orcid:" in str(v) for n in doc["cell_states"]
               for v in [n.get("was_attributed_to")]), "fixture no longer covers this"
    report = lp.lint(path, vocab, sv, validator, None)
    assert "endpoints" not in checks_firing(report, "error")


def test_made_up_predicate_is_reported(bottom_line, tmp_path, vocab, sv, validator):
    """A predicate disagreeing with its edge class is a warning.

    Warning rather than error because the schema states the predicate only as an
    `ifabsent` DEFAULT. Reported regardless, since `linkml-validate` accepts a
    fabricated predicate without complaint — this is the only thing between a
    hallucinated relationship type and a document that looks entirely valid.
    """
    bottom_line["has_drs_object_edges"][0]["predicate"] = "dapper:totallyMadeUpRelation"
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "predicates" in checks_firing(report, "warning")


def test_dangling_reference_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """A reference to an absent node is an error.

    One typo and the result no longer reaches its own provenance, while every
    individual node still validates.
    """
    bottom_line["used_edges"] = [{
        "subject": bottom_line["activities"][0]["id"],
        "predicate": "prov:used",
        "object": "dapper:C2M2File.doesNotExistAnywhereInThisDoc00",
        "edge_role": "data_input",
    }]
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "refs" in checks_firing(report, "error")


def test_schema_term_predicate_is_not_read_as_a_reference(bottom_line, tmp_path,
                                                          vocab, sv, validator):
    """`predicate: dapper:hasDrsObject` is a vocabulary term, not a dangling node.

    The `dapper:` prefix is shared between minted ids and the schema's own term
    namespace. Matching on the prefix alone reported every reified edge in the
    corpus as a dangling reference, so this pins the distinction: a node id
    always carries a `.` digest, a term never does.
    """
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "refs" not in checks_firing(report), (
        "a schema term is being chased as a node reference:\n"
        + "\n".join(f.render() for f in report.findings if f.check == "refs")
    )


def test_duplicate_id_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """Two nodes sharing an id is an error — every reference becomes ambiguous."""
    bottom_line["datasets"].append(copy.deepcopy(bottom_line["datasets"][0]))
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "duplicate-ids" in checks_firing(report, "error")


def test_id_naming_the_wrong_class_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """A node whose id names a different class than its group is an error.

    The id carries an independent claim about what the node is. Filed under
    `datasets:` with a `dapper:GeneSet.…` id, the node validates fine against
    Dataset while every consumer that parses the class out of the id disagrees.
    """
    digest = bottom_line["datasets"][0]["id"].split(".", 1)[1]
    bottom_line["datasets"][0]["id"] = f"dapper:GeneSet.{digest}"
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "id-class" in checks_firing(report, "error")


def test_edited_node_failing_its_own_digest_is_rejected(bottom_line, tmp_path,
                                                        vocab, sv, validator):
    """Editing hashable content without re-minting is an error.

    An id that addresses different content is worse than a missing one: the
    document still parses, still validates and still renders.
    """
    bottom_line["datasets"][0]["name"] = "Renamed without re-minting"
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "identity" in checks_firing(report, "error")


def test_unhashable_edit_does_not_trip_the_digest_check(bottom_line, tmp_path,
                                                        vocab, sv, validator):
    """Changing a timestamp does NOT change identity.

    The other half of the rule above, and the schema's whole point in marking
    timestamps `unhashable`: re-running a pipeline must not change what the
    result IS. This is why fixing the malformed `generated_at_time` in the
    canonical example needed no re-mint.
    """
    bottom_line["activities"][0]["generated_at_time"] = "2027-01-01T00:00:00Z"
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "identity" not in checks_firing(report, "error")


def test_disconnected_node_is_rejected(bottom_line, tmp_path, vocab, sv, validator):
    """A node the end result cannot reach is an error.

    This is the check that catches a plausible-looking hallucinated object: it
    validates, it reads sensibly, and it is attached to nothing.
    """
    bottom_line["persons"] = [{"id": "orcid:0000-0002-1825-0097", "name": "Unconnected"}]
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "reachability" in checks_firing(report, "error")


def test_activity_outputs_are_not_reported_as_disconnected(vocab, sv, validator):
    """A run's other outputs are reachable, not orphans.

    `was_generated_by` points output -> activity, so the six materialised C2M2
    files in the geneset graph are SIBLINGS of the gene set rather than its
    descendants. A subject -> object walk alone called all six disconnected —
    six false errors on a document that is entirely correct. Reachability
    therefore also follows `was_generated_by` in reverse from any activity it
    reaches.
    """
    path = REPO_ROOT / vocab.profiles["geneset"]["canonical_example"]
    report = lp.lint(path, vocab, sv, validator, "geneset")
    assert "reachability" not in checks_firing(report), (
        "sibling outputs reported as disconnected:\n"
        + "\n".join(f.render() for f in report.findings if f.check == "reachability")
    )


def test_missing_required_provenance_edge_is_rejected(bottom_line, tmp_path,
                                                      vocab, sv, validator):
    """A result with no generating Activity is an error.

    The schema has to make this edge optional, since the same classes are
    reused across modalities — so a bottom-line result carrying no provenance
    at all validates perfectly. That is exactly the gap a profile closes.
    """
    bottom_line["was_generated_by_edges"] = []
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "required-edges" in checks_firing(report, "error")


def test_second_end_result_in_one_file_is_rejected(bottom_line, tmp_path,
                                                   vocab, sv, validator):
    """Two bottom-line results in one document is an error.

    One file per instantiation. With two, the provenance below can no longer be
    attributed to either result unambiguously.
    """
    second = copy.deepcopy(bottom_line["datasets"][0])
    second["id"] = "dapper:Dataset.0000000000000000000000000000000a"
    bottom_line["datasets"].append(second)
    report = lint_doc(bottom_line, tmp_path, vocab, sv, validator)
    assert "terminal" in checks_firing(report, "error")


def test_many_gene_sets_in_one_file_are_allowed(vocab):
    """A geneset document has no terminal cap, unlike a bottom-line result.

    One converter run legitimately emits many gene sets over a single shared
    provenance subgraph, so capping this would reject correct output.
    """
    assert vocab.profiles["geneset"]["terminal"].get("max") is None
    assert vocab.profiles["bottom-line-result"]["terminal"]["max"] == 1


# ---------------------------------------------------------------------------
# 3. profiles.yaml and the derived vocabulary stay consistent with the schema
# ---------------------------------------------------------------------------
def test_terminal_classes_are_real_node_classes(vocab, sv):
    """Every profile's terminal class exists and is a node that can carry an id.

    A terminal class must be a Node descendant. An inline struct like
    `GeneProgramQualityScore` has no `id`, so a profile built on one could never
    have a reachable end result.
    """
    for name, profile in vocab.profiles.items():
        class_name = profile["terminal"]["class"]
        assert class_name in sv.all_classes(), f"{name}: unknown class {class_name}"
        assert "Node" in sv.class_ancestors(class_name), (
            f"{name}: {class_name} is not a Node, so it cannot carry an id"
        )


def test_terminal_classes_are_unique_across_profiles(vocab):
    """No two profiles share a terminal class.

    The terminal class IS the auto-detection key, so a collision makes both
    modalities undetectable rather than raising anywhere obvious.
    """
    seen: dict[str, str] = {}
    for name, profile in vocab.profiles.items():
        class_name = profile["terminal"]["class"]
        assert class_name not in seen, (
            f"{name} and {seen[class_name]} both claim terminal class {class_name}"
        )
        seen[class_name] = name


def test_edge_endpoint_classes_all_exist(vocab, sv):
    """profiles.yaml names no class the schema does not define.

    These lists are transcribed by hand from prose descriptions on the edge
    classes, which is exactly the kind of thing that goes stale when a class is
    renamed.
    """
    for edge_class, spec in vocab.edge_endpoints.items():
        assert edge_class in sv.all_classes(), f"unknown edge class {edge_class}"
        for end in ("subject", "object"):
            for class_name in spec.get(end) or []:
                assert class_name in sv.all_classes(), (
                    f"{edge_class}.{end} names unknown class {class_name}"
                )


def test_required_edge_groups_are_real_edge_groups(vocab):
    """Every profile's required edges use a group key the engine recognises.

    A typo here fails open: the linter would look for edges under a key no
    document ever uses, find none, and report the requirement as unmet forever.
    """
    for name, profile in vocab.profiles.items():
        for spec in profile.get("required_edges") or []:
            assert spec["group"] in vocab.edge_groups, (
                f"{name}: {spec['group']} is not a known edge group"
            )


def test_derived_edge_group_keys_match_what_the_examples_use(vocab):
    """Group keys derived from class names agree with the committed examples.

    Edge group keys are derived (`Used` -> `used_edges`) rather than listed, so
    that a new edge class is understood immediately. The risk is the derivation
    disagreeing with a key already in use — `HasProvenanceGraph` does, which is
    why it is the one override. This catches the next such case.
    """
    used_in_examples: set[str] = set()
    for path in EXAMPLES.glob("*.yaml"):
        doc = yaml.safe_load(path.read_text()) or {}
        used_in_examples |= {k for k in doc if k.endswith("_edges")}

    unknown = sorted(used_in_examples - set(vocab.edge_groups))
    assert unknown == [], (
        f"edge group key(s) in the examples that the engine does not derive: {unknown}. "
        f"Add an entry to `edge_group_overrides` in profiles.yaml."
    )


def test_edge_group_overrides_name_real_edge_classes(vocab, sv, profiles_doc):
    """An override keyed on a class that no longer exists is dead config."""
    for class_name in (profiles_doc.get("edge_group_overrides") or {}):
        assert class_name in sv.all_classes(), f"override for unknown class {class_name}"
        assert "Edge" in sv.class_ancestors(class_name), f"{class_name} is not an Edge"


def test_expected_predicates_come_from_the_schema(vocab):
    """Predicates are read out of the schema, not restated in profiles.yaml.

    Guards the no-duplication property: if this map ever comes up empty the
    predicate check silently passes everything, and nothing else would show it.
    """
    assert vocab.edge_predicates.get("Used") == "prov:used"
    assert vocab.edge_predicates.get("WasGeneratedBy") == "prov:wasGeneratedBy"
    assert vocab.edge_predicates.get("HasDrsObject") == "dapper:hasDrsObject"
