# Result collections

Added in 0.2.1-a1.

A result collection groups one method's results so they can be cited, turned
into claims and queried as a unit. For example, a PIGEAN collection holds the
gene and gene-set statistics for every trait and gene-set library PIGEAN was
run on, the templates that mint claims from those rows, and the queries that
read them.

Worked examples (synthetic):
[`example_result_collection.yaml`](../examples/example_result_collection.yaml)
and [`example_collection_claims.yaml`](../examples/example_collection_claims.yaml).

## Collections

`Collection` is abstract: a `Set` whose members are other DAPPER records, with
optional versioning. Two classes specialize it:

```
Set                      prov:Collection; members, member_type, n_members
 └─ Collection           abstract; adds collection_key, version, was_revision_of
     ├─ GeneSetCollection   members: GeneSet   (a gene-set library, e.g. one GMT)
     └─ ResultCollection    members: Dataset   (one release of a method's results)
```

Both get the same membership fields, attribution and provenance fields
(`ProvenancedResource`) and version chain. A versioned gene-set library sets
`collection_key` (`cfde-inc`) and `version` (`v2`). Versioning is optional for
gene-set libraries, so existing `GeneSetCollection` ids are unchanged. A
`ResultCollection` must set both fields.

## Result collection model

```
ResultCollection  pigean 2026.11.0             collection_key, version, methods, dataset_dimensions
 ├─ members ──────────> Dataset                {trait: KPN.TRAIT:0000505, library: cfde-inc-v2}
 │                       ├─ dimension_values
 │                       ├─ has_file ──> File  sha256, size_in_bytes, location
 │                       └─ file_roles   gene_stats → File, gene_set_stats → File
 ├─ has_claim_template ─> File                 template bytes
 ├─ has_query_template ─> File
 ├─ has_manifest_file ──> File                 row kinds, metrics, parsing rules
 ├─ was_revision_of ────> ResultCollection     the previous version
 └─ was_generated_by ───> Activity             publication; used the manifest
```

| Field | Meaning |
| --- | --- |
| `collection_key` | Short name shared by every version, e.g. `pigean`. Required. |
| `version` | This version's label, e.g. `2026.11.0`. Required. |
| `members` | The member Datasets (`prov:hadMember`), at least one. `n_members` must match when given. |
| `methods` | Methods whose results this version holds, as the `software_name` of the Activities that wrote the files. Usually one; see below. |
| `dataset_dimensions` | Ordered names that identify each Dataset, e.g. `[trait, library]`. |
| `has_claim_template`, `has_query_template` | Template Files. DAPPER pins their bytes; the template format belongs to the tool that renders them. |
| `has_manifest_file` | The manifest the version was built from. |
| `was_revision_of` | The previous version of the same collection. |

## Versions and claim identity

A version is immutable and content-addressed. Adding a dataset, replacing a
file or editing a template makes a new version with a new id.
`collection_key` names the collection across versions, and
`was_revision_of` chains them. Because that link is hashed, the history
cannot be rewritten. The linter rejects a revision that crosses classes or
keys, such as a result release "revising" a gene-set library. An older version
in the same document counts as upstream, not as a second end result.

**Claims never reference the collection.** A claim traces to its inputs
through two links:

- `was_generated_by`: the minting Activity, which `used` the template File
  and the result File.
- `was_derived_from`: the result File.

A claim's id therefore depends on its template and file bytes, not on which
versions list them. A new version that only adds a trait leaves every existing
claim id unchanged. A template edit re-addresses only the claims minted with
that template. If claims hashed the version instead, every release would
re-address every claim, which would break citations and deduplication.

To list a version's claims, walk forward from the collection. Take its
Datasets' files and its claim templates, then find the minting Activities that
used both, and the Claims those Activities generated.

## Dimensions

Each member Dataset lists one `dimension_value` per collection dimension, in
the collection's order. No two Datasets may share every value. When a
dimension also has its own slot (`trait`, `ancestry`), the two must agree.

A value is whatever the data uses: a CURIE when one exists, otherwise the
source's own label (`cfde-inc-v2`). DAPPER does not normalize identifiers. For
example, whether genes are symbols or HGNC IDs is decided by the result files,
not this profile.

## File roles

`file_roles` says which role each of a Dataset's files plays, e.g.
`gene_stats` or `membership`. Each role's file must also be listed in
`has_file`. DAPPER does not model file formats, row kinds or metrics. The
manifest declares them, and `has_manifest_file` pins the manifest by checksum.

## Value locators

A `ValueLocator` pins one value in a result file:

| Field | Meaning |
| --- | --- |
| `file` | The File whose bytes are addressed. |
| `byte_start`, `byte_length` | The span, as a 0-based offset and a length. |
| `value_text` | The span's bytes decoded as UTF-8, exactly as serialized (`10.5`, not `10.50`). |
| `selector` | A readable address such as `gene=GENE_A; key=combined`. Advisory only. |
| `media_type` | The format the selector assumes, e.g. `application/x-ndjson`. |

To verify one, read the file and check its sha256 against the File record.
Then compare `file[byte_start : byte_start + byte_length]` with `value_text`.
The comparison is on bytes, not numbers. Any Claim whose evidence names the
locator can be re-checked this way without trusting the service that served
it.

An `EvidenceItem` grounds in a file through `value_locators`. When it does,
`target_proposition` and `explanation` are required. `direction` stays
optional: a raw measurement has no direction, and DAPPER does not infer one
by thresholding. An interpretation, such as an evidence tier assigned under a
declared rule, can use both `value_locators` and `source_claims`. The usual
`source_claims` rule then also applies: `direction` and `context` are
required.

Locators are content-addressed. The same span always gets the same id, so
measurement evidence and interpretation evidence about one value share a
single locator.

## Bringing data from a repository (Croissant)

A collection can import results that a repository already describes with a
[Croissant](https://mlcommons.org/working-groups/data/croissant/) record. Each
`FileObject` becomes a `File` with the same sha256. The record itself becomes a
`File` that the publication Activity `used`. The manifest then groups the
files into Datasets and roles. No new class is needed. The
[Croissant guide](croissant.md) gives the full mapping in both directions,
with a worked example that `mlcroissant` loads.

## One method per collection

A collection may list more than one method. **Doing so is usually an
anti-pattern:**

- **Scores stop being comparable.** Each method's scores have their own
  meaning and scale. One query surface across methods invites "top genes in
  the collection", which quietly ranks one method's log odds against another's
  effect estimates. DAPPER forbids comparing scores across metrics, and a
  shared collection makes that rule easier to break.
- **Releases get coupled.** A fix to one method forces a new version of the
  other's results, and two methods rarely release on the same schedule.
- **Dimensions rarely match.** Each method has its own natural slicing. One
  method may vary by trait and gene-set library, while another also varies by
  factor fit. Forcing one set of dimensions on both loses information.

Prefer one collection per method. Combine claims from several collections in
a `ScientificAccount`, which organizes claims without merging their scores.

Mixing is reasonable when one pipeline run produces both methods' outputs
together, they share dimensions, and consumers always need them as a unit.
For example, a method and its own post-processing step. Even then, keep their
row kinds and metrics separate, and never compute across them.

The linter warns when a version lists more than one method. It also warns
when a member file was generated by an Activity whose `software_name` is not
in `methods`.

## Publishing a version

1. Update the manifest and commit it.
2. For each Dataset, record each result File with `sha256`, `size_in_bytes`,
   `mime_type` and `location`. Then record the Dataset's `dimension_values`
   and `file_roles`.
3. Record the template and query Files.
4. Record the publication Activity. It `used` the manifest, and its
   `code_version` is the commit.
5. Mint ids and lint the document:

```sh
uv run schema/identity/dapper_identity.py assign collection.yaml
uv run schema/lint/lint_provenance.py collection.yaml --profile result-collection --strict
```

The `result-collection` profile requires exactly one ResultCollection and its
generating Activity. Member Datasets are `prov:hadMember` members, not
separate end results. The profile also checks dimensions, duplicate dimension
values, `trait` agreement, role files, and that `was_revision_of` stays within
one `collection_key`. The linter does not download files. Repository tests
verify the example locators against their bytes.
