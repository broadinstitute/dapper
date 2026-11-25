# DAPPER

LinkML models for dataset attribution, provenance, evidence retrieval, and
related biomedical knowledge products.

## Release

Use [0.3.0-a1](https://github.com/broadinstitute/dapper/releases/tag/0.3.0-a1)
to pin the model described here. It splits the schema into concept modules
(`core.yaml`, `claims.yaml` and one per domain) that `dapper.yaml` imports,
flattens the repository layout, and adds value locators and result collections to
[0.2.0](docs/releases/0.2.0.md) without changing any identifier. See the
[release and migration notes](docs/releases/0.3.0-a1.md). Pull the tag when
generating or validating its identifiers; the 0.2.0 alphas and 0.1.0 use
different gene-set and claims models.

## Repository layout

`schema/` holds only the LinkML modules. Everything else sits beside it at the
root.

```text
schema/
  dapper.yaml               # root model: imports every module below, defines nothing
  core.yaml                 # what is tracked: identity, attribution, provenance, files, collections
  claims.yaml               # scientific reasoning: propositions, claims, evidence, accounts
  genesets.yaml             # GeneSet, GeneSetCollection
  cell_programs.yaml        # GeneProgram, CellState
  mechanisms.yaml           # MechanisticModel, CausalStep, Mechanism
  nanopub.yaml              # nanopublications
  dismech.yaml              # DISMECH cross-walk edge
  replay.yaml               # AgenticWorkspace
  cfde.yaml                 # C2M2File
examples/                   # LinkML instance and graph examples
identity/                   # computed content identifiers (DAPPER-ID-1)
lint/                       # provenance-graph linter and modality profiles
converter/                  # source-data to model converters
citations/                  # JSON Schema and example for external citation records
docs/                       # site landing page, release notes, and guides/
tools/                      # docs build, prefix expansion, claims and citation checks
portal/                     # provenance inspector
tests/
```

## Identifiers

Every object carries a computed content address, `dapper:{ClassName}.{digest}` — a GA4GH
`sha512t24u` digest over the fields that constitute what the object *is*. Timestamps, signatures and
mirror observations are excluded, so re-running a pipeline or re-signing a nanopublication does not
change an identifier; changing the analysis does.

**Identifiers are never written by hand.** Leave `id` out of your source data and let the tool mint
it. To turn a pile of gene-set runs into one identified collection:

```bash
uv run identity/mint.py /path/to/your/genesets -o collection.yaml
uv run identity/dapper_identity.py verify collection.yaml
```

`identity/README.md` has the walkthrough, the full `DAPPER-ID-1` profile, and why this is
deliberately *not* a Trusty URI.

Additional model types should be added as separate YAML modules under
`schema/`, with imports expressed relative to `schema/`. Shared vocabulary,
base classes, and reusable enums should be factored into their own modules
once there is a concrete second consumer.

## Current migration

`schema/dapper.yaml` is DAPPER, migrated from the NIH Dataset Attribution and
Provenance Profile it's named after. It covers citation, funding, PROV
lineage, file identity, controlled-access terms, workflow provenance,
nanopublications, scientific accounts, and agentic replay.

The model is split into modules. `schema/core.yaml` holds what is tracked
(the graph skeleton, identity, attribution, provenance, files, DRS, DUO,
embeddings, collections) and can be imported on its own. `schema/claims.yaml`
is the scientific reasoning layer. Each domain (gene sets, gene programs and
cell states, mechanistic models, nanopublications, the DISMECH cross-walk,
agentic replay, CFDE files) has its own module. `schema/dapper.yaml` only
imports them. Tools and validation always start from `dapper.yaml`, and every
module is linted on its own.

Scientific assessments use `Claim`, reusable `Proposition` records, and typed
`ClaimScore` values. `ScientificAccount` organizes a question, hypothesis role,
context, claims, and optional conclusions. Its question references `Question`
or the `KnowledgeGap` subclass. `EvidenceItem` records how source
claims bear on a target proposition; `MechanisticModel` supplies optional
biological structure. `Paragraph` saves a textual expression of an account.
See the [Scientific Claims design](docs/guides/claims.md) and the
[fictional account example](examples/example_scientific_account.yaml).
Questions and gaps can carry entity context; gaps can specify `gap_kind`.
Paragraph citations pin exact scientific objects and citation metadata revisions.
The separate [citation metadata contract](docs/guides/citations.md) records ordered
credit, dates, repository metadata, and publication state without changing the
scientific object's digest.

```bash
uv run lint/lint_provenance.py examples/example_scientific_account.yaml
uv run tools/scientific_claims.py examples/example_scientific_account.yaml
```

Use `File` for generic inputs, intermediates, and outputs, and `C2M2File` for
files carrying C2M2 metadata. Optional DRS representations are separate nodes.
See [files and DRS](docs/guides/files-and-drs.md) and the
[intermediate-file example](examples/example_file_graph.yaml).

`GeneSetCollection` represents a library of named `GeneSet` records and links
its GMT serialization through `has_gmt_file`. A single set selects its row
with `in_gmt_file` plus `gmt_entry`. Direct membership uses collection `members`
and the set's inverse `in_gene_set_collection` list. Collection `n_sets` counts sets and
`n_genes` counts their distinct gene union. Locations and checksums belong on
the referenced `File` or `C2M2File`. See the
[gene-set authoring guide](docs/guides/geneset-authoring.md) and
[two-row example](examples/example_geneset_collection_rows.yaml).

`Embedding` records a vector that a model computed from text derived from
any node (`embedding_of`; the node's inverse `has_embedding` list is
unhashable, so embedding a node never changes its identifier). The vector
bytes live as one row of a shared matrix `File`, located by `has_vector_file`
plus `vector_row`; model, provider, dimensions, dtype, normalization, the
embedded text, its template and `vector_sha256` make up the identity. See the
[embeddings guide](docs/guides/embeddings.md) and
[example](examples/example_embedding_graph.yaml).

`ResultCollection` is one immutable version of a method's results: member
`Dataset`s placed by `dimension_values` and `file_roles`, plus the claim and
query template files. It and `GeneSetCollection` both specialize the abstract
`Collection`, a versioned `Set` of DAPPER records. `ValueLocator` pins the
exact bytes of a value in a result file so evidence can ground there. See the
[result collections guide](docs/guides/result-collections.md) and
[example](examples/example_result_collection.yaml). Results that a
repository already describes with Croissant map onto these classes directly;
see [Croissant and DAPPER](docs/guides/croissant.md).

Validate a single instance from the repository root with:

```bash
uv run --with linkml linkml-validate \
  -s schema/dapper.yaml -C Dataset examples/example_dataset.yaml
```

## End-result documents

An *end modality* is a terminal product of a pipeline — a bottom-line result, a
gene set. Each instantiation is published as one self-contained YAML file: the
end result object plus all the provenance around how it was generated.

`linkml-validate` cannot check such a file. The schema declares no `tree_root`,
so pointing it at a graph document raises rather than validating; it only works
on one node at a time against a named class. Lint a whole document with:

```bash
uv run lint/lint_provenance.py path/to/result.yaml   # modality auto-detected
uv run lint/lint_provenance.py --list-profiles
```

On top of per-node schema conformance, it checks the document shape, typed edge endpoints, referential
integrity, identifier correctness, and that every node is reachable from the end
result. Modalities are declared as data in
[`lint/profiles.yaml`](lint/profiles.yaml) Please see [lint/README.md](lint/README.md) for additional documentation.

## Model documentation

The [gene-set authoring guide](docs/guides/geneset-authoring.md) shows document-local
`prefixes`, digest-based GMT file references, and a corrected HuBMAP export.
Use `uv run tools/expand_prefixes.py input.yaml --output expanded.yaml` to
resolve identifier/URI fields and re-mint affected records. The provenance
linter rejects undeclared prefixes in these fields.

The [AF / AA bottom-line mapping](docs/guides/bottom-line-results.md) shows how
to represent S3 prefix collections, pipeline activities, and a published File
distribution without inventing C2M2 or DRS registrations. Its
[complete YAML example](examples/example_bottom_line_af_aa.yaml) passes
the provenance linter and is included in the portal.

The [ancestry guide](docs/guides/ancestry.md) describes `AncestryEnum`, its
HANCESTRO mappings, and the optional `ancestry` field on Dataset and Activity.
The AF / AA example includes explicit ancestry scope. Use
`uv run lint/lint_dig_ancestry.py path/to/result.yaml` to also check
declared ancestry against DIG's public/staging export folder conventions.
The example also uses `trait: KPN.TRAIT:0000096` for atrial fibrillation;
the portal links this CURIE to the renamed KPN trait catalog.

Build the searchable LinkML reference and the provenance inspector together:

```bash
uv run tools/build_docs.py
uv run tools/build_docs.py --serve --port 8000
```

The preview is at `http://127.0.0.1:8000/model/`, with the inspector at `/`.
The reference includes class inheritance diagrams, inherited slots, enums,
ontology mappings, and full-text search. Reference pages come directly from
`schema/dapper.yaml` and the modules it imports; the landing page and theme live in `docs/`.

The inspector orders inputs before outputs in both arrow views. **Stored predicates**
points each arrow from its statement's subject to its object; `prov:wasGeneratedBy`
therefore points from a result back to the producing activity. **Forward flow** keeps
arrows flowing toward outputs and uses inverse labels, such as `prov:generated`
and the reading aid “was used by.” Graph connections always shows the original
subject → predicate → object statement. Switching views changes neither the layout
nor upstream tracing, and does not rewrite the document or its identifiers.
The selected result's files and DRS access records stay visible as context during
tracing; unrelated downstream analyses remain dimmed. File nodes use their
filename as the display label when available.

Generated Markdown (`.build/model-docs/`) and HTML (`site/`) are ignored by Git.
CI builds the documentation in strict mode to catch broken links. The existing
Pages workflow publishes the combined site after changes reach `main`, with model
documentation under `/dapper/model/` and the inspector at its existing URL.

The schema declares `dapper_class:`, `dapper_slot:`, `dapper_enum:`, and `dapper_type:` prefixes
for links to definitions in the model reference. Existing vocabulary CURIEs
such as `dapper:Edge` resolve through `/dapper/ns/#Edge` to those pages.
External semantic mappings and `dapper:{ClassName}.{digest}` record IDs retain
their existing meanings. The build checks that every namespace redirect has a
generated destination page.

## Contribution workflow

Validate schema changes, examples, and converters locally; push to
`broadinstitute/dapper` only once the migration shape is agreed.

We use prek to validate and check files before committing. Before your
commit, please run

```bash
prek install
```
