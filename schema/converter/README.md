# `geneset_to_dapper.py` — dig.geneset → DAPPER converter

Reads the lab's `dig.geneset` provenance (`geneset.provenance.json` + `geneset.meta.json`, from
`flannick/dig-gene-set-extractors`) and emits **validated NIH-DAPP instances**. It's the
executable form of the crosswalk in
[`../docs/geneset-provenance-nih-dapp-adaptation.md`](../docs/geneset-provenance-nih-dapp-adaptation.md).

The script is self-contained (PEP 723 inline deps — just `pyyaml`); `uv` installs them on first
run. No changes to any project's dependencies.

## Usage

```bash
# a single gene set (sibling geneset.meta.json auto-discovered), validated
uv run schema/converter/geneset_to_dapper.py \
  schema/examples/geneset-hubmap-hz2/ -o out/ --validate

# a local tree — converts every geneset.provenance.json found
uv run schema/converter/geneset_to_dapper.py /path/to/runs/ -o out/

# straight from S3 (batch; reuses your existing AWS auth)
uv run schema/converter/geneset_to_dapper.py \
  s3://dig-gene-set-data/LINCS_L1000/ -o out/ --validate

# inject the NIH attribution dig.geneset doesn't carry
uv run schema/converter/geneset_to_dapper.py <input> -o out/ --overlay attribution.yaml
```

`<input>` is a `geneset.provenance.json` file, a local directory (walked recursively), or an
`s3://` URI/prefix (the `*.provenance.json` + `*.meta.json` sidecars are pulled with `aws s3`,
then converted).

### Output

Per gene set, into `-o OUT_DIR`:

| file | contents |
|------|----------|
| `<id>.dapper.yaml` | the full provenance graph — `c2m2_files`, `activities`, `gene_sets`, `used_edges`, `was_generated_by_edges` (the shape of `examples/example_geneset_graph.yaml`) |
| `<id>.geneset.yaml` | the standalone focus `GeneSet` node (the shape of `examples/example_geneset.yaml`), with `--overlay` attribution applied |

### Options

- `--validate` — `linkml-validate` every emitted node against `../dapper.yaml`; non-zero exit on any failure.
- `--overlay FILE` — YAML of NIH attribution (`has_creator`, `funded_by`, `is_described_by`,
  `has_recommended_citation`, …) merged onto the focus `GeneSet`. Without it those authoritative
  fields are empty and the run logs which are missing (dig.geneset has no NIH attribution).
- `--schema PATH` — schema to validate against (defaults to `../dapper.yaml`).

## Mapping (summary)

| dig.geneset | NIH-DAPP |
|---|---|
| `File` node + `c2m2_properties` | `C2M2File` (+ `sha256` from the metadata sidecar) |
| `AnalysisType` node + `analysis{}` | `Activity` (command / observed_command / script_url / code_version / entrypoint / container_image) |
| `GeneSet` node + `meta.gene_set` / `summary` | `GeneSet` (assay / organism / genome_build / n_genes / n_sets / term_prefix) |
| edge `data input` / `metadata input` | `Used` edge (`prov:used`, `edge_role`) |
| edge `data output` | `WasGeneratedBy` edge (`prov:wasGeneratedBy`) |

The multi-step DAG (multiple `AnalysisType` nodes) is handled generically — the converter
iterates nodes/edges, so an arbitrary provenance graph maps without special-casing.

The full field-by-field crosswalk, worked examples, and open questions are in the
[adaptation report](../docs/geneset-provenance-nih-dapp-adaptation.md).

## Not handled

- **NIH attribution** (creators / awards / publications / citation) — not present in dig.geneset;
  supply via `--overlay`.
- **Rebasing** (the lab's local→public path rewrite, formerly called "mirror") is orthogonal: it
  determines whether a file's identity is a local path or a public URI *before* conversion. The
  converter maps whatever identity it's given (`C2M2File.local_id`).
