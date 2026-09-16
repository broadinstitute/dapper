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
- **[Hypothesis](reference/classes/Hypothesis.md)** — a scientific claim connected to evidence.

## Browse the reference

- [Classes](reference/classes/index.md): entities, reusable mixins, and graph edges.
- [Slots](reference/slots/index.md): fields, ranges, cardinalities, and the classes that use them.
- [Enums](reference/enums/index.md): controlled choices and their meanings.
- [Types](reference/types/index.md): primitive values imported from LinkML.
- [Full schema](reference/index.md): the complete model overview.

## Follow the provenance

Read [files and DRS](guides/files-and-drs.md) to understand how intermediate
files fit into a provenance graph, or [computed identifiers](guides/identity.md)
to see what makes a DAPPER record's identity change.

<a href="../">Open the provenance inspector →</a> to explore worked graphs or
load your own DAPPER YAML.

These reference pages are generated from [the schema](schema/dapper.yaml).
Class pages include direct and inherited slots; shared slot pages show how a
field is used across classes.
