# Explore the DAPPER model

DAPPER describes datasets, files, analyses, and the evidence and attribution that
connect them. Browse a class to see its inheritance, fields, relationships, and
ontology mappings. Search by a class or field name to jump straight to its definition.

## Start with a resource

- **[File](reference/classes/File.md)** — an input, intermediate, or output of an analysis.
- **[C2M2File](reference/classes/C2M2File.md)** — a file with C2M2 metadata and portal links.
- **[DrsObject](reference/classes/DrsObject.md)** — a DRS description of accessible content.
- **[Dataset](reference/classes/Dataset.md)** — a citable data resource with attribution and provenance.
- **[Activity](reference/classes/Activity.md)** — the computation or process that uses and generates resources.
- **[GeneSet](reference/classes/GeneSet.md)** and **[GeneProgram](reference/classes/GeneProgram.md)** — biological collections and coordinated gene activity.
- **[Claim](reference/classes/Claim.md)** — an attributed assessment of a proposition, with scores and provenance.
- **[CompositeClaim](reference/classes/CompositeClaim.md)** — component claims assembled into an explicit explanation or conjunction.
- **[Hypothesis](reference/classes/Hypothesis.md)** — the existing DISMECH-oriented mechanistic hypothesis.

## Browse the reference

- [Classes](reference/classes/index.md): entities, reusable mixins, and graph edges.
- [Slots](reference/slots/index.md): fields, ranges, cardinalities, and the classes that use them.
- [Enums](reference/enums/index.md): controlled choices and their meanings.
- [Types](reference/types/index.md): primitive values imported from LinkML.
- [Full schema](reference/index.md): the complete model overview.

## Link to a definition

The schema declares separate CURIE prefixes for the model reference:

- `dapper_class:Edge` expands to the [Edge class](reference/classes/Edge.md).
- `dapper_slot:subject` expands to the [subject slot](reference/slots/subject.md).
- `dapper_enum:ResourceTypeEnum` expands to the [resource type enum](reference/enums/ResourceTypeEnum.md).
- `dapper_type:string` expands to the [string type](reference/types/string.md).

Each definition displays its documentation CURIE. Its mappings retain the
semantic URIs from RDF, PROV, schema.org, and other vocabularies; for example,
the Edge class still uses `rdf:Statement`.

Existing vocabulary CURIEs such as `dapper:Edge` resolve through the
<a href="../ns/#Edge">DAPPER namespace</a> to the corresponding reference page.
Computed record IDs such as `dapper:File.<digest>` identify individual data
records and are not documentation links.

## Follow the provenance

Read the [bottom-line mapping](guides/bottom-line-results.md) for a complete
AF / AA example using datasets, stages, and an ordinary file distribution.
The [genetic ancestry guide](guides/ancestry.md) explains the
[AncestryEnum](reference/enums/AncestryEnum.md), its HANCESTRO mappings, and
ancestry scope on datasets and activities.
The example's [trait](reference/slots/trait.md) references
[atrial fibrillation in KPN](https://broadinstitute.github.io/kpn-data-models/kpn.trait/0000096/)
using `KPN.TRAIT:0000096`.
Read [files and DRS](guides/files-and-drs.md) to understand how intermediate
files fit into a provenance graph, or [computed identifiers](guides/identity.md)
to see what makes a DAPPER record's identity change.

The [Scientific Claims design](guides/claims.md) proposes a minimal representation
of questions, hypotheses, findings, and interpretation grounded in a results
paragraph.

<a href="../">Open the provenance inspector →</a> to explore worked graphs or
load your own DAPPER YAML.

These reference pages are generated from [the schema](schema/dapper.yaml).
Class pages include direct and inherited slots; shared slot pages show how a
field is used across classes.
