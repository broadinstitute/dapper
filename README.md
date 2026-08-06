# DAPPER

LinkML models for dataset attribution, provenance, evidence retrieval, and
related biomedical knowledge products. **DAPPER** is the working repository
name; the acronym and public model branding are still being finalized.

## Repository layout

The root `schema/` directory is the model boundary. Keep schema modules,
examples, converters, and model-specific documentation relative to that
directory so the repository can grow without mixing model concerns with
repository tooling.

```text
schema/
  dapper.yaml               # current root model
  trusty-identifiers.md     # Trusty URI and nanopublication design notes
  examples/                 # LinkML instance and graph examples
  converter/                # Source-data to model converters
```

Additional model types should be added as separate YAML modules under
`schema/`, with imports expressed relative to `schema/`. Shared vocabulary,
base classes, and reusable enums should be factored into their own modules
once there is a concrete second consumer.

## Current migration

`schema/dapper.yaml` is the DAPPER model, migrated from the NIH Dataset
Attribution and Provenance Profile. Its NIH-DAPP vocabulary is intentionally
retained where it names the underlying standard. The schema already
covers citation, funding, PROV lineage, file identity, controlled-access terms,
workflow provenance, nanopublications, hypotheses, and agentic replay.

Validate from the repository root with:

```bash
uv run --with linkml linkml-validate \
  -s schema/dapper.yaml -C Dataset schema/examples/example_dataset.yaml
```

## Contribution workflow

Make initial schema changes in this checkout, validate examples and converters,
then commit and push to `broadinstitute/dapper` only after the migration shape
and acronym are agreed.
