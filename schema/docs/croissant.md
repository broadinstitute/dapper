# Croissant and DAPPER

Added in 0.2.1-a1.

[Croissant](https://mlcommons.org/working-groups/data/croissant/) is the
MLCommons metadata format for datasets: JSON-LD built on schema.org `Dataset`.
It says which files make up a dataset, where to download them, and how to read
their rows and columns. Machine-learning tools then load the dataset from that
record alone. Hugging Face, Kaggle and OpenML publish Croissant records, and
the `mlcroissant` library reads them.

DAPPER answers different questions about the same data: where it came from,
who to credit, and which claims it supports, down to the exact bytes behind a
number. The two meet at the file. Both describe each file by its checksum, so
a Croissant `FileObject` and a DAPPER `File` with the same sha256 are the same
bytes.

Use them together. Croissant makes results loadable. DAPPER makes them
traceable and citable, and turns rows into claims. Neither replaces the other,
and this alpha adds no new class to connect them. The mapping below uses
existing classes only.

## Who covers what

| Question | Croissant | DAPPER |
| --- | --- | --- |
| Which files, and where to download them | `distribution`: `FileObject`, `FileSet`, `contentUrl` | `File` (`sha256`, `size_in_bytes`, `location`); `Dataset.has_file` |
| How to read rows and columns | `RecordSet`, `Field`, `source.extract` | Not modeled. A collection's manifest declares row kinds and metrics. |
| What a value means | `dataType` (text, float, ...) | `ClaimScore`: `score_kind`, `metric`, `interpretation` |
| How the data was produced | Not modeled (the RAI extension has free-text collection notes) | `Activity`, `Used`, `WasGeneratedBy`, lineage steps |
| Who to credit, under what terms | `creator`, `license`, `citeAs` | `has_creator`, `funded_by`, `has_license`, `RecommendedCitation`, DUO data-use terms |
| What the data says | Not modeled | `Proposition`, `Claim`, `EvidenceItem` |
| The exact bytes behind a reported number | Not modeled | `ValueLocator` |
| Identity | `@id` local to the record, plus any `url` or DOI it carries | DAPPER-ID-1 content addresses, computed from content |

## Importing a Croissant record into DAPPER

A repository's Croissant record is a good way to bring existing results into
a `ResultCollection` (see [result collections](result-collections.md)). To
import one:

1. **Keep the record.** Fetch it and record its bytes as a `File`
   (`application/ld+json`, with the sha256 of the bytes as fetched). The
   Activity that publishes the collection version `used` it. A record can
   change at the same URL, so the File pins the version that was read.
2. **Resolve the distribution.** Each `FileObject` is one file. A `FileSet`
   (`containedIn` plus `includes` globs) expands to the files that match when
   you fetch. Record that expanded list. The set may grow later, and the
   version must not.
3. **Download and verify every file.** Check the record's checksum against
   the bytes received. Then record one DAPPER `File` per file:

   | Croissant `FileObject` | DAPPER `File` |
   | --- | --- |
   | `sha256` | `sha256`, after checking it against the bytes |
   | `md5` (when there is no sha256) | Check it, then record the sha256 you compute. `File.md5` is base64, so check the record's encoding and convert rather than copy. |
   | `contentUrl` | `location` (mutable, outside identity, so re-hosting keeps the id) |
   | `encodingFormat` | `mime_type`, copied as given |
   | `name`, `description` | `filename` (the file's own name), `description` |
   | `contentSize` | `size_in_bytes`, measured from the bytes |

   `FileSet` members carry no checksums in Croissant, so their sha256 always
   comes from the download.
4. **Group files into Datasets.** The collection manifest says which files
   form which Dataset and in what role, for example "files matching
   `*/gene_stats.ndjson` are `gene_stats`, with the trait from the first path
   segment". The result becomes each Dataset's `dimension_values` and
   `file_roles`.
5. **Copy attribution.** The record's `license`, `creator` and `citeAs` go to
   `has_license`, `has_creator` and a `RecommendedCitation`. Its DOI or other
   persistent `identifier` goes to `alternate_identifier`, and `url` goes to
   `location`. Put these on the Dataset, or on the `ResultCollection` when one
   record covers the whole collection.
6. **Describe columns from the record sets.** A `Field` with
   `source.extract.column` or `jsonPath` names a column. The manifest can take
   its row-kind and metric columns from these. Croissant's `dataType` gives
   only the type, so the manifest still has to say what each score means and
   on what scale. That meaning becomes the `ClaimScore` `interpretation`.

Only after this do claims get minted, and they are minted from the downloaded
bytes. Evidence therefore never depends on the repository staying online or
unchanged.

### Worked example

[`data/result-collection/croissant.json`](../examples/data/result-collection/croissant.json)
is a synthetic Croissant 1.0 record for two JSON Lines result files. It
declares a `FileObject` and a `RecordSet` for each file, and `mlcroissant` loads
every row. [`example_result_collection.yaml`](../examples/example_result_collection.yaml)
is the DAPPER side of the import:

- **Same bytes.** Each `FileObject` has a DAPPER `File` with the same sha256,
  its `contentUrl` resolved into `location`, and its `encodingFormat`
  (`application/jsonlines`) as `mime_type`.
- **The record is kept.** The record itself is a `File`, and the publication
  Activity `used` it.
- **Datasets come from the manifest.** The two files become two Datasets,
  `trait` T1 and T2 in library `example-library-v1`, each with a
  `gene_stats` role.

`tests/test_croissant.py` checks this mapping against the bytes on every run.

## Publishing DAPPER results as Croissant

Going the other way gives an ML user a loadable dataset with a path back to
provenance. Generate one record per `ResultCollection` version. Never edit it
by hand: a version is immutable, so a new version gets a new record.

| DAPPER | Croissant |
| --- | --- |
| `ResultCollection` `name`, `description`, `version` | Dataset `name`, `description`, `version` |
| `ResultCollection` id | Dataset `identifier`, as the full URI `https://broadinstitute.github.io/dapper/ns#ResultCollection.<digest>` |
| Member Datasets' `File`s | One `FileObject` each: `location` becomes `contentUrl`, `sha256` becomes `sha256`, `mime_type` becomes `encodingFormat` |
| `file_roles` plus the manifest's row kinds | One `RecordSet` per role, with a `Field` per column and `source.extract.column` (or `jsonPath`) |
| `has_license`, `has_creator`, `has_recommended_citation` | `license`, `creator`, `citeAs` |

Abridged, for the example collection:

```json
{
  "@type": "sc:Dataset",
  "conformsTo": "http://mlcommons.org/croissant/1.0",
  "name": "example-gene-associations",
  "version": "2026.11.0",
  "identifier": "https://broadinstitute.github.io/dapper/ns#ResultCollection.<digest>",
  "distribution": [
    { "@type": "cr:FileObject", "@id": "gene-stats-t1",
      "contentUrl": "trait-t1/gene_stats.ndjson",
      "encodingFormat": "application/jsonlines", "sha256": "<same as the DAPPER File>" }
  ],
  "recordSet": [
    { "@type": "cr:RecordSet", "@id": "gene_stats_t1",
      "field": [ { "@type": "cr:Field", "@id": "gene_stats_t1/combined", "dataType": "sc:Float",
                   "source": { "fileObject": { "@id": "gene-stats-t1" },
                               "extract": { "column": "combined" } } } ] }
  ]
}
```

Claims stay DAPPER objects; Croissant has no place for them. To ship
provenance with the data, add the DAPPER collection document to the export's
`distribution` as one more `FileObject` (`application/yaml`). Do this only
for exports. A DAPPER document that lists a Croissant record cannot be listed
by that same record, because each would need the other's checksum first.

## Value locators and Croissant fields

They work at different levels. A Croissant `Field` describes a whole column:
which file it comes from and how to extract it. A `ValueLocator` pins one
value's bytes in one file. A locator's advisory `selector` can name the field
it was read through, for example `field=gene_stats_t1/combined; gene=GENE_A`.
A reader can then go from a claim's evidence to the column definition, and
from there to the Croissant record. The byte span stays the contract.

## Notes

- **Identifiers do not cross over.** A Croissant `@id` is local to its record,
  and a DAPPER id is computed from content. Never reuse one as the other. Use
  `identifier` (Croissant) and `alternate_identifier` (DAPPER) to point
  between them.
- **Live datasets.** A record marked `isLiveDataset` changes under the same
  URL. Snapshot it before minting anything from it.
- **Re-hosting is free.** Moving files changes `contentUrl` and DAPPER
  `location`, and neither is part of identity. File, Dataset and claim ids
  stay the same.
- **Not in this alpha:** a converter script in either direction. The mapping
  is mechanical. A converter can follow the pattern of
  `schema/converter/geneset_to_dapper.py`.
