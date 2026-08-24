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

Validate from the repository root with:

```bash
uv run --with linkml linkml-validate \
  -s schema/dapper.yaml -C Dataset schema/examples/example_dataset.yaml
```

## Contribution workflow

Validate schema changes, examples, and converters locally; push to
`broadinstitute/dapper` only once the migration shape is agreed.

We use prek to validate and check files before committing. Before your
commit, please run

```bash
prek install
```
