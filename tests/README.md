# Tests

```
uv run --with-requirements tests/requirements.txt pytest tests/ -q
```

Nothing to install first. The code under test — `schema/converter/geneset_to_dapper.py`,
`schema/identity/dapper_identity.py`, `portal/build.py` — is a set of standalone PEP-723
scripts that declare their dependencies inline, so there is no package to install in
editable mode. `tests/requirements.txt` exists only so `uv` can assemble one environment
holding pytest *and* those scripts' dependencies at once. `tests/conftest.py` puts the two
script directories on `sys.path`.

| File | Covers |
|---|---|
| `test_converter.py` | the dig.geneset → NIH-DAPP crosswalk: node mapping, the sha256 join across the metadata sidecar, edge direction, overlay precedence, and an end-to-end `convert_one` |
| `test_identity.py` | the minting algorithm: the GA4GH digest primitive, `digest_of` parsing, what constitutes identity, `assign_ids`/`verify`, the frozen vectors, and `DOC_GROUPS` coverage |
| `test_examples.py` | every `schema/examples/*.yaml`: parses, ids match content, no duplicates, `_illustrative` points at real nodes |

## Fixtures

`fixtures/geneset-hubmap-hz2/` is a real `dig.geneset` run — HuBMAP gene set
`402cf4a1f3682a2e5bf1b002`, 9 File / 2 AnalysisType / 1 GeneSet nodes and 11 edges. It
moved here from `schema/examples/`, which is the model's worked examples in DAPPER's own
YAML; this is raw upstream input, and only the converter and its docs ever read it.

## Two things these tests deliberately do differently

**`test_examples.py` globs, it does not list.** `lint_identity.py` checks a hardcoded
`GRAPH_DOCS` of four files out of eleven. A stale `BioComputeObject` id in
`example_graph.yaml` — introduced when `5ff61ad` rewrote the `nih:` prefix without
re-minting — sat outside that list and was invisible. Globbing means a new example is
covered the moment it is added, rather than when someone remembers to extend a list.

**The identity tests assert behaviour, not just outcomes.** `verify-vectors` proves the
frozen fixtures still reproduce; it cannot tell you *why* a digest moved. The unit tests
pin the individual properties — class name is part of the identity, a node's own id never
feeds its digest, external ORCID/ROR ids survive minting — so a regression names itself.

## When a test fails

| Failure | Usually means |
|---|---|
| `has stale identifiers` | content changed without re-minting → `uv run schema/identity/mint.py <file> -o <file>`, or substitute the reported digest |
| `add these to DOC_GROUPS` | a new Node class needs a document-list key in `dapper_identity.py`, or the portal and minter will disagree about it |
| a permanent vector fails | **fix the code, never the vector** — see `schema/identity/README.md`. A changed algorithm is `DAPPER-ID-2` under a new prefix |
