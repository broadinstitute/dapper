# DAPPER

LinkML models for dataset attribution, provenance, evidence retrieval, and
related biomedical knowledge products.

## Repository layout

The root `schema/` directory is the model boundary. Keep schema modules,
examples, converters, and model-specific documentation relative to that
directory so the repository can grow without mixing model concerns with
repository tooling.

```text
schema/
  dapper.yaml               # current root model
  trusty-identifiers.md     # Trusty URI and nanopublication design notes
  identity/                 # computed content identifiers (DAPPER-ID-1)
  examples/                 # LinkML instance and graph examples
  converter/                # Source-data to model converters
```

## Identifiers

Every object carries a computed content address, `dapper:{ClassName}.{digest}` — a GA4GH
`sha512t24u` digest over the fields that constitute what the object *is*. Timestamps, signatures and
mirror observations are excluded, so re-running a pipeline or re-signing a nanopublication does not
change an identifier; changing the analysis does.

**Identifiers are never written by hand.** Leave `id` out of your source data and let the tool mint
it. To turn a pile of gene-set runs into one identified collection:

```bash
uv run schema/identity/mint.py /path/to/your/genesets -o collection.yaml
uv run schema/identity/dapper_identity.py verify collection.yaml
```

`schema/identity/README.md` has the walkthrough, the full `DAPPER-ID-1` profile, and why this is
deliberately *not* a Trusty URI.

Additional model types should be added as separate YAML modules under
`schema/`, with imports expressed relative to `schema/`. Shared vocabulary,
base classes, and reusable enums should be factored into their own modules
once there is a concrete second consumer.

## Current migration

`schema/dapper.yaml` is DAPPER, migrated from the NIH Dataset Attribution and
Provenance Profile it's named after. It covers citation, funding, PROV
lineage, file identity, controlled-access terms, workflow provenance,
nanopublications, hypotheses, and agentic replay.

Use `File` for generic inputs, intermediates, and outputs, and `C2M2File` for
files carrying C2M2 metadata. Optional DRS representations are separate nodes.
See [files and DRS](schema/docs/files-and-drs.md) and the
[intermediate-file example](schema/examples/example_file_graph.yaml).

Validate a single instance from the repository root with:

```bash
uv run --with linkml linkml-validate \
  -s schema/dapper.yaml -C Dataset schema/examples/example_dataset.yaml
```

## End-result documents

An *end modality* is a terminal product of a pipeline — a bottom-line result, a
gene set. Each instantiation is published as one self-contained YAML file: the
end result object plus all the provenance around how it was generated.

`linkml-validate` cannot check such a file. The schema declares no `tree_root`,
so pointing it at a graph document raises rather than validating; it only works
on one node at a time against a named class. Lint a whole document with:

```bash
uv run schema/lint/lint_provenance.py path/to/result.yaml   # modality auto-detected
uv run schema/lint/lint_provenance.py --list-profiles
```

On top of per-node schema conformance, it checks the document shape, typed edge endpoints, referential
integrity, identifier correctness, and that every node is reachable from the end
result. Modalities are declared as data in
[`schema/lint/profiles.yaml`](schema/lint/profiles.yaml) Please see [schema/lint/README.md](schema/lint/README.md) for additional documentation.

## Model documentation

Build the searchable LinkML reference and the provenance inspector together:

```bash
uv run tools/build_docs.py
uv run tools/build_docs.py --serve --port 8000
```

The preview is at `http://127.0.0.1:8000/model/`, with the inspector at `/`.
The reference includes class inheritance diagrams, inherited slots, enums,
ontology mappings, and full-text search. Reference pages come directly from
`schema/dapper.yaml`; the landing page and theme live in `docs/`.

Generated Markdown (`.build/model-docs/`) and HTML (`site/`) are ignored by Git.
CI builds the documentation in strict mode to catch broken links. The existing
Pages workflow publishes the combined site after changes reach `main`, with model
documentation under `/dapper/model/` and the inspector at its existing URL.

## Contribution workflow

Validate schema changes, examples, and converters locally; push to
`broadinstitute/dapper` only once the migration shape is agreed.

We use prek to validate and check files before committing. Before your
commit, please run

```bash
prek install
```
