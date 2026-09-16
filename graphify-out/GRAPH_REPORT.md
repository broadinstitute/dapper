# Graph Report - .  (2026-09-15)

## Corpus Check
- Corpus is ~48,111 words - fits in a single context window. You may not need a graph.

## Summary
- 1007 nodes · 2809 edges · 72 communities (60 shown, 12 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.8)
- Token cost: 37,307 input · 47,148 output

## Community Hubs (Navigation)
- Files and activity provenance
- Core graph relationships
- Scalar fields and cell state
- Gene-set conversion
- Resource references and nanopublications
- Hashable metadata and numbers
- Identity regression tests
- Datasets and biological sets
- Data-use modifiers
- Hypotheses and causal mechanisms
- Content identity design
- Node identity and nanopub parts
- Identity minting and lint
- Canonicalization and reference rewriting
- CI and schema validation
- Digest primitives
- Dataset attribution and mirroring
- Collection minting
- Agents and affiliations
- External identifiers
- Identifier schemes
- Nanopublication types
- Gene program quality
- File identity verification
- Example integrity tests
- Creator roles
- Unhashable metadata
- Resource types
- Contributor roles
- Publications and citations
- Test fixtures
- Provenance portal
- Publication relationships
- Evidence direction
- Data-use permissions
- Hypothesis status
- Resource descriptions
- Provenance timestamps
- Resource names
- Digest parsing
- Data-use terms
- Schema graph extraction
- Funder vocabulary
- Cell-state decision flags
- Organisms
- Claim sentences
- Licensing
- Access levels
- Provenance trace traversal
- Software versions
- Lineage membership
- Specification conformance
- Dataset distributions
- Publishers
- Dataset versions
- Labels
- Assays
- Usage terms
- Family names
- Given names
- Software agents
- Intermediate mechanisms
- DRS access methods
- Evidence sources
- Evidence explanations
- Reference titles
- Evidence excerpts
- Disease subtypes
- Signature algorithms
- Public keys
- Signature values
- PubMed identifiers

## God Nodes (most connected - your core abstractions)
1. `hashable` - 244 edges
2. `literal` - 192 edges
3. `string` - 130 edges
4. `uriorcurie` - 119 edges
5. `DAPPER - NIH Dataset Attribution and Provenance Profile` - 89 edges
6. `CellState` - 80 edges
7. `relationship` - 70 edges
8. `Dataset` - 64 edges
9. `predicate` - 56 edges
10. `Activity` - 50 edges

## Surprising Connections (you probably didn't know these)
- `test_file_relocation_and_drs_registration_preserve_identity()` --calls--> `compute_id()`  [INFERRED]
  tests/test_files.py → schema/identity/dapper_identity.py
- `test_converter_accepts_generic_intermediate_and_preserves_provenance()` --calls--> `convert_graph()`  [INFERRED]
  tests/test_files.py → schema/converter/geneset_to_dapper.py
- `test_every_example_node_id_is_a_well_formed_dapper_id()` --calls--> `digest_of()`  [INFERRED]
  tests/test_examples.py → schema/identity/dapper_identity.py
- `test_id_is_never_an_input_to_its_own_digest()` --calls--> `hashable_slot_names()`  [INFERRED]
  tests/test_identity.py → schema/identity/dapper_identity.py
- `test_unmarked_slots_are_a_schema_error_not_a_default()` --calls--> `unmarked_slots()`  [INFERRED]
  tests/test_identity.py → schema/identity/dapper_identity.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Gene-set provenance crosswalk** — schema_docs_geneset_provenance_nih_dapp_adaptation_cfde_provenance_graph, schema_dapper_class_c2m2file, schema_dapper_class_activity, schema_dapper_class_geneset, schema_dapper_class_used, schema_dapper_class_wasgeneratedby [EXTRACTED 1.00]
- **Manifest-backed analysis output** — schema_dapper_class_dataset, schema_dapper_class_activity, schema_dapper_class_drsobject [EXTRACTED 1.00]
- **Signed evidence provenance** — schema_dapper_class_hypothesis, schema_dapper_class_nanopublication, schema_dapper_class_nanopubassertion, schema_dapper_class_nanopubprovenance, schema_dapper_class_nanopubpublicationinfo, schema_dapper_class_nanopubsignature [EXTRACTED 1.00]
- **Intermediate file links two activities through usage and generation** — schema_examples_example_geneset_graph_hubmap_two_activity_provenance_dag, schema_dapper_class_c2m2file, schema_dapper_class_activity, schema_dapper_class_used, schema_dapper_class_wasgeneratedby [EXTRACTED 1.00]
- **Nanopublication requires exactly one assertion, provenance, and publication-info graph** — schema_dapper_class_nanopublication, schema_dapper_class_nanopubassertion, schema_dapper_class_nanopubprovenance, schema_dapper_class_nanopubpublicationinfo [EXTRACTED 1.00]
- **Nanopublication back-reference cycle excluded from hashing** — schema_dapper_class_hypothesis, schema_dapper_class_nanopublication, schema_dapper_class_nanopubassertion, schema_identity_readme_acyclic_hash_dependency_graph [EXTRACTED 1.00]
- **Intermediate provenance with optional DRS access** — schema_examples_example_file_graph_intermediate_file, schema_dapper_class_file, schema_dapper_class_activity, schema_dapper_class_drsobject, schema_dapper_class_used, schema_dapper_class_wasgeneratedby, schema_dapper_class_file_slot_drs_representation [EXTRACTED 1.00]

## Communities (72 total, 12 thin omitted)

### Community 0 - "Files and activity provenance"
Cohesion: 0.07
Nodes (84): DAPPER repository guide, Schema model boundary, dig.geneset converter guide, File converter classification, geneset_to_dapper.py converter, NIH attribution overlay, Activity, Activity.command (+76 more)

### Community 1 - "Core graph relationships"
Cohesion: 0.07
Nodes (81): AssertedIn, AssertedIn.predicate, CorrespondsToDismech, CorrespondsToDismech.object, CorrespondsToDismech.predicate, CorrespondsToDismech.subject, Edge, FundedBy (+73 more)

### Community 2 - "Scalar fields and cell state"
Cohesion: 0.07
Nodes (72): Activity.container_image, Activity.entrypoint, Activity.observed_command, AgenticWorkspace.agent_model, AgenticWorkspace.platform, AgenticWorkspace.regeneration_prompt, AgenticWorkspace.workspace_key, Award.grant_administering_institute (+64 more)

### Community 3 - "Gene-set conversion"
Cohesion: 0.05
Nodes (64): _activity(), apply_overlay(), _c2m2_file(), _clean(), convert_graph(), convert_one(), _dump(), _file() (+56 more)

### Community 4 - "Resource references and nanopublications"
Cohesion: 0.08
Nodes (51): AgenticWorkspace.agent_role, BioComputeObject, BioComputeObject.description_domain, BioComputeObject.error_domain, BioComputeObject.execution_domain, BioComputeObject.io_domain, BioComputeObject.parametric_domain, BioComputeObject.provenance_domain (+43 more)

### Community 5 - "Hashable metadata and numbers"
Cohesion: 0.07
Nodes (38): Activity.activity_type, Activity.repo_url, Activity.script_url, BioComputeObject.usability_domain, C2M2File.c2m2_uuid, CausalStep.step_index, CellState.display_order, CellState.n_markers (+30 more)

### Community 6 - "Identity regression tests"
Cohesion: 0.06
Nodes (37): Unit tests for schema/identity/dapper_identity.py — the minting algorithm.  lint, A minted id has exactly the three-part shape the rest of the system parses., Every slot must declare `hashable` or `unhashable` — silence is not allowed., Re-minting an already-minted document changes nothing.      mint.py's contract i, Replacing a node's id also updates everything that pointed at it.      Minting r, An ORCID or ROR is authoritative and must survive minting untouched.      Regres, The file on disk gets the same protection assign_ids gives in memory.      The t, Comments survive the write — the requirement the text rewriter existed for. (+29 more)

### Community 7 - "Datasets and biological sets"
Cohesion: 0.16
Nodes (36): Dataset, Dataset.has_data_use_term, GeneProgram, GeneSet, NanopubProvenance.derived_from, ProvenancedResource, ProvenancedResource.access_level, ProvenancedResource.alternate_identifier (+28 more)

### Community 8 - "Data-use modifiers"
Cohesion: 0.06
Nodes (33): DataUseModifierEnum, DataUseModifierEnum.clinical_care_use, DataUseModifierEnum.collaboration_required, DataUseModifierEnum.ethics_approval_required, DataUseModifierEnum.genetic_studies_only, DataUseModifierEnum.geographical_restriction, DataUseModifierEnum.institution_specific_restriction, DataUseModifierEnum.no_general_methods_research (+25 more)

### Community 9 - "Hypotheses and causal mechanisms"
Cohesion: 0.11
Nodes (27): CausalStep, CausalStep.has_evidence, CausalStep.step_subject, CausalStep.via_mechanism, DismechLinked, DismechLinked.dismech_class, DismechLinked.dismech_disease_term, DismechLinked.dismech_entry_key (+19 more)

### Community 10 - "Content identity design"
Cohesion: 0.12
Nodes (23): has_creator, Acyclic hash dependency graph, Canonical RDF digest input, DAPPER-ID-1, DAPPER computed identifier guide, GA4GH sha512t24u, Ordered list identity, Out-of-band profile version (+15 more)

### Community 11 - "Node identity and nanopub parts"
Cohesion: 0.18
Nodes (21): HashableNode, LineageStep, NanopubAssertion, NanopubProvenance, NanopubPublicationInfo, NanopubSignature, Node, RoCratePackage (+13 more)

### Community 12 - "Identity minting and lint"
Cohesion: 0.22
Nodes (18): _apply(), assign_ids(), compute_id(), hashable_slot_names(), _iter_nodes(), _load(), load_schema(), main() (+10 more)

### Community 13 - "Canonicalization and reference rewriting"
Cohesion: 0.15
Nodes (18): _blank_self(), _graph_for(), _is_reference_slot(), _literal(), _looks_like_prose(), Any, Replace a reference to another DAPPER node with that node's bare digest.      VR, Neutralise a node's own identifier inside its own content.      MUST mirror the (+10 more)

### Community 14 - "CI and schema validation"
Cohesion: 0.13
Nodes (17): Portal freshness invariant, Provenance portal Pages deployment, DAPPER pull-request test workflow, DAPPER pre-commit checks, DAPPER pytest suite, LinkML schema lint, DAPPER, DAPPER-ID-1 (+9 more)

### Community 15 - "Digest primitives"
Cohesion: 0.12
Nodes (17): Graph, canonical_bytes(), compute_digest(), GA4GH VRS truncated digest: SHA-512, leftmost 24 bytes, base64url.      24 bytes, Canonicalize and serialize deterministically.      THE SORT ON THE NEXT-TO-LAST, The 32-character digest for one instance.      `self_id` is the identifier this, sha512t24u(), An id embedded in a node's own content is blanked before hashing.      Excluding (+9 more)

### Community 16 - "Dataset attribution and mirroring"
Cohesion: 0.12
Nodes (17): Award, MirrorProvenance, has_data_use_term, has_drs_object, has_mirror_provenance, has_workflow_provenance, packaged_as, FRAPO:Grant (+9 more)

### Community 17 - "Collection minting"
Cohesion: 0.15
Nodes (16): Keys holding node lists that DOC_GROUPS does not know, with node counts.      An, unknown_node_groups(), _collect_inputs(), _dedupe(), main(), _merge(), Any, Path (+8 more)

### Community 18 - "Agents and affiliations"
Cohesion: 0.14
Nodes (16): Agent, HasCreator.object, Organization, Person, Person.affiliation, dcterms:Agent, foaf:Agent, foaf:member (+8 more)

### Community 19 - "External identifiers"
Cohesion: 0.13
Nodes (16): Award.award_number, Award.funder_identifier, BioComputeObject.bco_id, C2M2File.persistent_id, DataUseTerm.duo_id, DrsObject.drs_id, Organization.ror, Person.orcid (+8 more)

### Community 20 - "Identifier schemes"
Cohesion: 0.13
Nodes (15): Award.funder_identifier_type, Dataset.identifier_type, FunderIdentifierTypeEnum, FunderIdentifierTypeEnum.crossref_funder_id, FunderIdentifierTypeEnum.grid, FunderIdentifierTypeEnum.isni, FunderIdentifierTypeEnum.other, FunderIdentifierTypeEnum.ror (+7 more)

### Community 21 - "Nanopublication types"
Cohesion: 0.13
Nodes (15): Nanopublication.nanopub_type, NanopubTypeEnum, NanopubTypeEnum.draft_nanopub, NanopubTypeEnum.example_nanopub, NanopubTypeEnum.intro_nanopub, NanopubTypeEnum.meta_nanopub, NanopubTypeEnum.protected_nanopub, NanopubTypeEnum.retraction_nanopub (+7 more)

### Community 22 - "Gene program quality"
Cohesion: 0.20
Nodes (14): GeneProgram.member_weights, GeneProgram.quality_score, GeneProgramQualityComponents, GeneProgramQualityScore, GeneProgramQualityScore.components, Cell program and curated state provenance example, Human-curated provenance, NMF gene programs (+6 more)

### Community 23 - "File identity verification"
Cohesion: 0.15
Nodes (12): Recompute every node's id; return human-readable mismatches., verify(), File provenance, DRS registration, and compatibility of inherited metadata., test_converter_accepts_generic_intermediate_and_preserves_provenance(), test_file_graph_mints_access_refs_without_changing_file_id(), test_file_relocation_and_drs_registration_preserve_identity(), The two halves of the system agree: what assign_ids writes, verify accepts., Editing a hashable field without re-minting is detected.      This is the drift (+4 more)

### Community 24 - "Example integrity tests"
Cohesion: 0.14
Nodes (13): Tests over schema/examples/*.yaml — the documents shipped as the model's worked, `_illustrative:` names only nodes that are actually in the document.      The po, The globs actually matched something.      Every other test in this file is para, Each example parses at all.      The cheapest possible check, run over every exa, Every node's identifier still hashes to the content beneath it.      The most va, Any id claiming our prefix is actually parseable as one.      Complements the te, No identifier appears twice in one document.      Two nodes sharing an id means, test_every_example_id_matches_its_content() (+5 more)

### Community 25 - "Creator roles"
Cohesion: 0.17
Nodes (13): Organization.creator_role, Person.creator_role, CreatorRoleEnum, CreatorRoleEnum.consortium, CreatorRoleEnum.curator, CreatorRoleEnum.data_manager, CreatorRoleEnum.division, CreatorRoleEnum.group (+5 more)

### Community 26 - "Unhashable metadata"
Cohesion: 0.17
Nodes (12): AgenticWorkspace.workspace_url, Award.award_uri, License.url, Nanopublication.created, NanopubProvenance.provenance_of, NanopubPublicationInfo.pubinfo_of, NanopubSignature.has_signature_target, unhashable (+4 more)

### Community 27 - "Resource types"
Cohesion: 0.17
Nodes (12): ResourceTypeEnum, ResourceTypeEnum.collection, ResourceTypeEnum.dataset, ResourceTypeEnum.gene_set, ResourceTypeEnum.model, ResourceTypeEnum.service, ResourceTypeEnum.software, ResourceTypeEnum.workflow (+4 more)

### Community 28 - "Contributor roles"
Cohesion: 0.20
Nodes (11): Organization.contributor_role, Person.contributor_role, ContributorRoleEnum, ContributorRoleEnum.data_curator, ContributorRoleEnum.data_manager, ContributorRoleEnum.hosting_institution, ContributorRoleEnum.other, ContributorRoleEnum.producer (+3 more)

### Community 29 - "Publications and citations"
Cohesion: 0.22
Nodes (11): Publication, Publication.citation, RecommendedCitation, RecommendedCitation.citation_text, dcterms:bibliographicCitation, dctypes:Text, dismech:PublicationReference, fabio:ResearchPaper (+3 more)

### Community 30 - "Test fixtures"
Cohesion: 0.18
Nodes (9): example_docs(), hz2_graph(), hz2_payload(), Shared fixtures.  `schema/converter/` and `schema/identity/` are standalone PEP-, SchemaView over schema/dapper.yaml., The real dig.geneset provenance payload for HuBMAP gene set HZ2., The single {nodes, edges} ProvenanceGraph inside that payload., Every schema/examples/*.yaml, parsed, keyed by filename. (+1 more)

### Community 31 - "Provenance portal"
Cohesion: 0.36
Nodes (7): build_graph(), is_illustrative(), load_schema(), main(), Pull class docs and the authoritative-slot set out of the LinkML schema., read_lib(), render()

### Community 32 - "Publication relationships"
Cohesion: 0.25
Nodes (8): Publication.relationship_type, PublicationRelationshipEnum, PublicationRelationshipEnum.cites, PublicationRelationshipEnum.is_cited_by, PublicationRelationshipEnum.is_described_by, PublicationRelationshipEnum.is_referenced_by, PublicationRelationshipEnum.is_supplement_to, dcterms:relation

### Community 33 - "Evidence direction"
Cohesion: 0.33
Nodes (7): EvidenceItem, EvidenceDirectionEnum, EvidenceDirectionEnum.mixed, EvidenceDirectionEnum.refutes, EvidenceDirectionEnum.supports, EvidenceDirectionEnum.unknown, dismech:EvidenceItem

### Community 34 - "Data-use permissions"
Cohesion: 0.29
Nodes (7): DataUsePermissionEnum, DataUsePermissionEnum.general_research_use, DataUsePermissionEnum.no_restriction, DataUsePermissionEnum.population_origins_ancestry_research_only, DUO:0000004, DUO:0000011, DUO:0000042

### Community 35 - "Hypothesis status"
Cohesion: 0.29
Nodes (7): HypothesisStatusEnum, HypothesisStatusEnum.alternative, HypothesisStatusEnum.canonical, HypothesisStatusEnum.contested, HypothesisStatusEnum.proposed, HypothesisStatusEnum.refuted, HypothesisStatusEnum.retracted

### Community 36 - "Resource descriptions"
Cohesion: 0.53
Nodes (6): Activity.description, Dataset.description, File.description, Set.description, dcterms:description, schema:description

### Community 37 - "Provenance timestamps"
Cohesion: 0.40
Nodes (6): Activity.generated_at_time, AgenticWorkspace.last_run, MirrorProvenance.sync_time, prov:generatedAtTime, schema:dateCreated, datetime

### Community 38 - "Resource names"
Cohesion: 0.33
Nodes (6): Award.award_title, C2M2File.filename, File.filename, Publication.title, dcterms:title, schema:name

### Community 39 - "Digest parsing"
Cohesion: 0.33
Nodes (6): digest_of(), Extract the bare digest from a `dapper:Class.digest` identifier., Only a well-formed `dapper:Class.digest` yields a digest; everything else is Non, A dot inside a local name is swallowed — which is why lint rule 9 exists.      P, test_digest_of_only_unpacks_our_own_identifiers(), test_digest_of_partitions_on_the_FIRST_dot()

### Community 40 - "Data-use terms"
Cohesion: 0.60
Nodes (5): DataUseTerm, DataUseTerm.modifier, DataUseTerm.permission, DUO:0000001, DUO:0000017

### Community 41 - "Schema graph extraction"
Cohesion: 0.60
Nodes (4): extract(), main(), normalize(), Path

### Community 42 - "Funder vocabulary"
Cohesion: 0.50
Nodes (4): Award.funder_name, FRAPO:FundingAgency, FRAPO:hasFundingAgency, schema:funder

### Community 43 - "Cell-state decision flags"
Cohesion: 0.50
Nodes (4): CellState.allow_hard_call, CellState.is_composite_required, CellState.is_qc, boolean

### Community 44 - "Organisms"
Cohesion: 0.50
Nodes (4): CellState.organism, GeneProgram.organism, GeneSet.organism, schema:taxonomicRange

### Community 45 - "Claim sentences"
Cohesion: 0.67
Nodes (4): Hypothesis.statement, NanopubAssertion.as_sentence, hycl:AIDA-Sentence, npx:asSentence

### Community 46 - "Licensing"
Cohesion: 0.50
Nodes (4): License, dcterms:LicenseDocument, schema:license, spdx:License

### Community 47 - "Access levels"
Cohesion: 0.50
Nodes (4): AccessLevelEnum, AccessLevelEnum.controlled, AccessLevelEnum.mixed, AccessLevelEnum.public

### Community 48 - "Provenance trace traversal"
Cohesion: 0.67
Nodes (3): find_start(), main(), The composite hypothesis at the top of the trace.      Derived, not hardcoded: i

### Community 49 - "Software versions"
Cohesion: 0.67
Nodes (3): Activity.code_version, Activity.software_version, schema:softwareVersion

### Community 50 - "Lineage membership"
Cohesion: 0.67
Nodes (3): Activity.has_lineage_step, dcterms:hasPart, prov:hadMember

### Community 51 - "Specification conformance"
Cohesion: 0.67
Nodes (3): BioComputeObject.bco_spec_version, RoCratePackage.conforms_to, dcterms:conformsTo

### Community 52 - "Dataset distributions"
Cohesion: 0.67
Nodes (3): Dataset.has_drs_object, dcat:distribution, schema:distribution

### Community 53 - "Publishers"
Cohesion: 0.67
Nodes (3): Dataset.publisher, dcterms:publisher, schema:publisher

### Community 54 - "Dataset versions"
Cohesion: 0.67
Nodes (3): Dataset.version, dcterms:hasVersion, schema:version

### Community 55 - "Labels"
Cohesion: 0.67
Nodes (3): DataUseTerm.duo_label, Nanopublication.label, rdfs:label

### Community 56 - "Assays"
Cohesion: 0.67
Nodes (3): GeneProgram.assay, GeneSet.assay, obo:OBI_0000070

### Community 57 - "Usage terms"
Cohesion: 0.67
Nodes (3): License.usage_terms, dcterms:rights, schema:usageInfo

### Community 58 - "Family names"
Cohesion: 0.67
Nodes (3): Person.family_name, foaf:familyName, schema:familyName

### Community 59 - "Given names"
Cohesion: 0.67
Nodes (3): Person.given_name, foaf:givenName, schema:givenName

## Knowledge Gaps
- **194 isolated node(s):** `AccessLevelEnum.controlled`, `AccessLevelEnum.mixed`, `AccessLevelEnum.public`, `CausalLinkTypeEnum.DIRECT`, `CausalLinkTypeEnum.INDIRECT_KNOWN_INTERMEDIATES` (+189 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DAPPER - NIH Dataset Attribution and Provenance Profile` connect `Core graph relationships` to `Files and activity provenance`, `Scalar fields and cell state`, `Resource references and nanopublications`, `Hashable metadata and numbers`, `Datasets and biological sets`, `Data-use modifiers`, `Hypotheses and causal mechanisms`, `Node identity and nanopub parts`, `CI and schema validation`, `Dataset attribution and mirroring`, `Agents and affiliations`, `Identifier schemes`, `Nanopublication types`, `Gene program quality`, `Creator roles`, `Unhashable metadata`, `Resource types`, `Contributor roles`, `Publications and citations`, `Publication relationships`, `Evidence direction`, `Data-use permissions`, `Hypothesis status`, `Data-use terms`, `Licensing`, `Access levels`?**
  _High betweenness centrality (0.197) - this node is a cross-community bridge._
- **Why does `hashable` connect `Hashable metadata and numbers` to `Files and activity provenance`, `Core graph relationships`, `Scalar fields and cell state`, `Resource references and nanopublications`, `Datasets and biological sets`, `Hypotheses and causal mechanisms`, `Content identity design`, `Node identity and nanopub parts`, `CI and schema validation`, `Agents and affiliations`, `External identifiers`, `Identifier schemes`, `Nanopublication types`, `Gene program quality`, `Creator roles`, `Unhashable metadata`, `Contributor roles`, `Publications and citations`, `Publication relationships`, `Resource descriptions`, `Resource names`, `Data-use terms`, `Funder vocabulary`, `Cell-state decision flags`, `Organisms`, `Claim sentences`, `Software versions`, `Lineage membership`, `Specification conformance`, `Dataset distributions`, `Publishers`, `Dataset versions`, `Labels`, `Assays`, `Usage terms`, `Family names`, `Given names`, `Software agents`, `Intermediate mechanisms`, `DRS access methods`, `Evidence sources`, `Evidence explanations`, `Reference titles`, `Evidence excerpts`, `Disease subtypes`, `Signature algorithms`, `Public keys`, `Signature values`, `PubMed identifiers`?**
  _High betweenness centrality (0.157) - this node is a cross-community bridge._
- **Why does `literal` connect `Scalar fields and cell state` to `Files and activity provenance`, `Core graph relationships`, `Hashable metadata and numbers`, `Datasets and biological sets`, `Hypotheses and causal mechanisms`, `Node identity and nanopub parts`, `CI and schema validation`, `External identifiers`, `Identifier schemes`, `Nanopublication types`, `Gene program quality`, `Creator roles`, `Unhashable metadata`, `Contributor roles`, `Publications and citations`, `Publication relationships`, `Resource descriptions`, `Provenance timestamps`, `Resource names`, `Data-use terms`, `Funder vocabulary`, `Cell-state decision flags`, `Organisms`, `Claim sentences`, `Software versions`, `Specification conformance`, `Dataset versions`, `Labels`, `Assays`, `Usage terms`, `Family names`, `Given names`, `Software agents`, `Intermediate mechanisms`, `DRS access methods`, `Evidence sources`, `Evidence explanations`, `Reference titles`, `Evidence excerpts`, `Disease subtypes`, `Signature algorithms`, `Public keys`, `Signature values`, `PubMed identifiers`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **What connects `AccessLevelEnum.controlled`, `AccessLevelEnum.mixed`, `AccessLevelEnum.public` to the rest of the system?**
  _194 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Files and activity provenance` be split into smaller, more focused modules?**
  _Cohesion score 0.06569133677567413 - nodes in this community are weakly interconnected._
- **Should `Core graph relationships` be split into smaller, more focused modules?**
  _Cohesion score 0.06882716049382716 - nodes in this community are weakly interconnected._
- **Should `Scalar fields and cell state` be split into smaller, more focused modules?**
  _Cohesion score 0.07198748043818466 - nodes in this community are weakly interconnected._
## Extraction scope and accounting

- LinkML schema declarations are parsed deterministically; see `linkml-extraction.json` for coverage.
- Documentation token counts are estimates from extraction agents, not metered session usage.
- JSON fixture contents are not extracted by the code parser; test/document references still appear.
- 69 unresolved code references (typically external modules) are retained in `unresolved-code-references.json` and excluded from the navigable graph.
- Parallel statements are preserved in each edge’s `evidence` and `relations`; `extraction.json` retains every original statement and direction.
