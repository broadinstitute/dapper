# Scientific Claims design

**Status:** Working proposal for discussion. This document replaces the earlier
claim modeling guide. It describes a proposed design, not the current schema
contract; implementation differences are noted below.

## Purpose and scope

DAPPER should represent a small scientific account that a researcher can inspect,
trace to its sources, and communicate as a results paragraph. The immediate
horizon is a useful demonstration within two months. The aim is to preserve the
most important distinctions with a small representation that can evolve through
community use.

The organizing unit is a **ScientificAccount**: a structured account of what was
asked, how it was addressed, what was found, and what those findings may imply.
A **Paragraph** is a natural-language expression of that account, with its own
textual and publication metadata.

These are separate objects because scientific content can be expressed in
multiple ways and published in multiple places. The initial workflow can use
one ScientificAccount and one Paragraph without implementing a general document
model.

## The paragraph as a design constraint

A results paragraph provides four organizing roles:

1. **Framing:** the question, knowledge gap, or hypothesis motivating the work.
2. **Context:** the approach, relevant scope, models, and assumptions.
3. **Findings:** the claims produced or assessed through that work.
4. **Closing:** an optional conclusion, synthesis, limitation, or implication.

This is a rendering order, not a fixed sentence count. A role may occupy several
sentences, and a sentence may express several claims. Findings can concern
results or biology; their position does not determine their scientific meaning.

The structured account must contain enough information to express these roles
without inventing missing scientific content. Context can be summarized in the
paragraph while remaining accessible through linked records.

## Core definitions

### Proposition

A **Proposition** is content that can be evaluated as true or false within a
specified scope. It identifies what is being considered, independently of who
asserts it or how strongly it is supported.

The minimum representation is self-contained text and any scope essential to
its meaning. Structured entities, predicates, and qualifiers can be added where
useful. Different assessments can refer to the same Proposition. Shared wording
or similar wording alone does not establish semantic equivalence.

### Claim

A **Claim** is an attributed assertion or assessment of a Proposition. It records
what an agent puts forward, together with its evidential and production context.
A Claim can be uncertain, disputed, or later revised; the class name does not
imply established truth.

A Claim links to its Proposition, responsible agent, and generating or recording
activity. It can also link to evidence, source records, and assessments or scores.
Scientific production and later extraction or recording are distinct activities
when both are known.

Scores belong to a specified assessment and retain their metric, meaning, and
scope. Confidence in one claim does not automatically transfer to another claim
or to the whole ScientificAccount.

Use **Claim** as the DAPPER object name. “Assertion” describes putting content
forward and remains useful in ontology mappings and publication terminology;
it does not require a second parallel DAPPER class.

### BiologicalQuestion

A **BiologicalQuestion** expresses an inquiry that the work aims to address.
It identifies what is unknown and the relevant biological scope. It is not
itself an assertion with a truth value or an evidence score.

Its minimum content is question text and necessary scope. A Hypothesis can be
proposed as an answer, and Claims can contribute to answering it. Neither link
means that the question has been resolved. Questions about analytical results
can use the same lightweight structure without requiring a new question taxonomy.

### Hypothesis

A **Hypothesis** is a candidate answer or explanation proposed for investigation.
Its content can be a Proposition or a biological model containing several
Propositions. It may address a BiologicalQuestion.

Hypothesis describes the role of content in an investigation; Claim describes
an attributed assertion or assessment of content. They are not successive stages
on a confidence scale. Claims can assess the propositions making up a Hypothesis,
and a proposed hypothesis can itself be put forward through a Claim.

For the initial design, question and hypothesis framing may be embedded in the
ScientificAccount or reference existing records. Naming these concepts does not
require new standalone, globally identified classes for every occurrence.
DAPPER's existing `Hypothesis` is a mechanistic representation and can supply
hypothesis content; it should not become the required shape of every candidate
answer.

### ScientificAccount

A **ScientificAccount** is an attributed, structured scientific account that brings
Claims together around a shared inquiry and context. It records their
organization and, where supplied, the reasoning connecting them.

It is more than an unordered collection, but membership does not assert a
logical conjunction, causal chain, or support relation. Because framing can
include questions and the conclusion is optional, the whole account need not
have a single truth value or a single assessed Proposition.

**Design recommendation:** model ScientificAccount as an organizing object, rather
than requiring it to be a subclass of Claim. If the account makes an overall
scientific conclusion, represent that conclusion as an explicit Claim within
it. A ScientificAccount needs at least one finding; requiring two claims would add
an arbitrary restriction to the paragraph workflow.

### Paragraph

A **Paragraph** is a particular textual expression of a ScientificAccount. Its
minimum content is the text and a reference to the account it expresses.
Optional metadata identifies its author or generating activity, version,
language, publication, and location within that publication.

A ScientificAccount can have several Paragraph expressions. Editing wording or
publication metadata need not change the underlying scientific account.
Changing scientific meaning requires updating the relevant structured content
and the link to its version. For the demo, a Paragraph expresses one
ScientificAccount; general document assembly is deferred.

## Results and biology are a separate axis

Distinguish the **scope of a Proposition** from its role in the paragraph and
from its assessment:

- **Result:** content about observations, measurements, or outputs of a specified
  analysis, including estimates and fitted model quantities.
- **Biological interpretation:** content about the biological system or process
  that the results are used to understand.
- **Unspecified:** content whose scope has not yet been classified.

This can begin as a small annotation on Proposition, rather than separate Claim
subclasses. Result claims can involve inference; they are not necessarily raw
observations. Biological interpretations can be strongly supported; they are
not necessarily speculative. Both may refer to the same biological entities,
so subject and object identifiers alone cannot determine the distinction.

Paragraph role, proposition scope, method of production, and confidence remain
independent. A hypothesis is not defined by being about biology, and a finding
is not defined by being about data. If one statement combines independently
assessed result and biological content, separate the propositions where practical.

## Context and the connection from results to biology

**Context** records what is needed to understand the work and its interpretation.
For the demo, use a small embedded record with prose and references covering:

- The inquiry's scope and relevant study or data setting.
- The analytical approach and statistical or computational model.
- The biological model being assumed or evaluated, when applicable.
- The assumptions and limitations relevant to interpreting the findings.

The analytical model and biological model need distinct descriptions even when
they are closely connected. The analytical model specifies how data become
estimates or outputs. The biological model describes the system those outputs
are intended to inform. A software version or execution command does not, by
itself, specify the biological interpretation.

An assumption is content being taken as given for an analysis or interpretation.
Recording it does not assert that the study established it. It can be text or a
reference to a Proposition or Hypothesis; assessing it requires a Claim.

Context may be shared within a ScientificAccount. However, scope that changes a
Proposition's meaning must remain explicit on, or explicitly referenced by,
that Proposition. Moving a Claim between accounts must not silently change
what it says.

An **Interpretation** records how specified findings bear on the Proposition
assessed by a target Claim under a stated context. Its minimal content is:

- References to one or more source Claims and one target Claim.
- The direction of the evidential contribution to the target Proposition:
  supports, disputes, or neutral.
- The applicable context, including the model and assumptions used.
- A short rationale explaining the connection.

This can initially be an embedded record owned and attributed through the
ScientificAccount, with separate attribution when the interpreter differs. Multiple
interpretations may address the same target. The relation records an evidential
argument, not guaranteed logical entailment or an automatic probability update.

When an account uses results to justify a biological Claim, this connection must
be explicit. A biological Hypothesis mentioned only as framing need not have
supporting findings. An interpretation may remain unassessed; missing reasoning
must remain visible rather than being inferred from paragraph order.

**Provenance and evidence answer different questions.** Provenance records how
an artifact or assertion was produced. Interpretation records why information
bears on a proposition. Both are needed to trace a biological conclusion back
through result claims, outputs, activities, and inputs. Reuse DAPPER's existing
provenance graph for files, commands, software, and intermediate artifacts;
do not copy that graph into paragraph context.

## Minimum ScientificAccount structure and linkages

The proposed record has six parts:

- **Framing — required:** at least one question, gap description, or proposed
  hypothesis. These may coexist.
- **Context — required:** a concise account of the approach and the relevant
  scope, with model and assumption information where applicable.
- **Component claims — required:** ordered references containing at least one
  finding. Claims can be reused across accounts.
- **Interpretations — optional:** explicit evidential connections between Claims;
  required wherever the account presents one claim as justification for another.
- **Closing — optional:** references to component Claims used as conclusions,
  together with any contextual remarks.
- **Attribution and provenance — required:** who assembled the account and the
  activity that produced or recorded it.

Closing claim references select from the component claims rather than duplicating
their content. A substantive scientific assertion introduced in the closing
must be represented as a Claim. A restatement or editorial remark need not
create a new Claim. Framing and context can reference Claims for scientific
assertions being assessed; assumptions remain explicitly marked as assumed.

Question-to-hypothesis links express proposed answers. Claim-to-proposition
links identify assessed content. Account-to-claim links express membership.
Interpretations express evidential use. Paragraph-to-account links express
textual realization. These relations must not be treated as interchangeable.

## Translating the account into a results paragraph

Rendering follows framing, context, findings, and optional closing. Component
Claims selected for the closing are expressed there; the remaining findings
follow their declared order. Ordering alone conveys no evidential dependency.

The rendering must preserve scope, attribution where relevant, uncertainty,
assessment direction, and the stated distinction between results and biological
interpretation. Transitions that explain evidential support must come from
recorded Interpretations. Rendering must not introduce stronger causal language,
new conclusions, or an aggregate confidence score.

A lightweight mapping from paragraph spans to framing, context, and Claim
references should make the text reviewable. Exact sentence objects and a full
rhetorical annotation ontology are unnecessary for the first demo. The initial
commitment is reliable rendering of authored structured accounts; automatic
recovery of this structure from arbitrary published prose is outside scope.

## Ontology alignments

These are reuse decisions and conceptual alignments. They do not establish OWL
equivalence or guarantee lossless export.

- **SEPIO:** Proposition aligns conceptually with
  [SEPIO Proposition](https://sepio-framework.github.io/sepio-linkml/Proposition/),
  and Claim with
  [SEPIO Statement](https://sepio-framework.github.io/sepio-linkml/Statement/).
  The embedded Interpretation follows the purpose of
  [SEPIO EvidenceLine](https://sepio-framework.github.io/sepio-linkml/EvidenceLine/):
  interpreting evidence with respect to a target proposition. A future export
  would resolve the target Claim to its Proposition and preserve the argument's
  attribution. ScientificAccount is a DAPPER organizing layer, with no asserted
  one-to-one SEPIO equivalent.
- **HYCL:** the
  [Hypotheses and Claims Ontology](https://github.com/peta-pico/ontologies/blob/master/hycl.ttl)
  provides statement representations and relations for claiming, hypothesizing,
  investigating, and comparing meaning. It is useful for discourse alignment;
  its `Statement` should not be assumed identical to SEPIO's attributed
  `Statement`. HYCL does not supply the entire paragraph or provenance model.
- **PROV-O:** reuse DAPPER's existing
  [PROV-O](https://www.w3.org/TR/prov-o/) relationships for entities, activities,
  attribution, usage, and derivation. Derivation tracks production and dependence;
  it does not replace the evidential relation captured by Interpretation.
- **DISMECH:** its
  [MechanisticHypothesis](https://github.com/monarch-initiative/dismech/blob/main/src/dismech/schema/dismech.yaml)
  organizes disease-level causal explanations and is a specialized source of
  hypothesis/model content. Its evidence representation and
  [SEPIO export](https://github.com/monarch-initiative/dismech/blob/main/docs/sepio-export.md)
  inform evidence interoperability. A generic DAPPER Claim or ScientificAccount
  should not be equated with a DISMECH MechanisticHypothesis.
- **Document structure:** Paragraph has a natural conceptual alignment with
  [DoCO Paragraph](https://sparontologies.github.io/doco/current/doco.html),
  a textual discourse unit. The
  [Discourse Elements Ontology](https://sparontologies.github.io/deo/current/deo.html)
  offers optional alignment for rhetorical roles. Its Results concept excludes
  discussion and conclusions, so the entire account proposed here should not
  be declared equivalent to `deo:Results`.

These vocabularies supply complementary building blocks. DAPPER supplies a
small application profile that connects them for a particular research workflow.
Publication packaging and richer domain predicates can be added without making
them prerequisites for authoring a scientific account.

## Demo boundary and later decisions

The first demo should allow a researcher to author and review one structured
account, distinguish its question or hypothesis from its findings, inspect the
reasoning behind a biological interpretation, follow available provenance, and
render a faithful results paragraph. Missing provenance or interpretation details
should be visible; a polished paragraph must not imply that the record is complete.

Reuse existing Proposition, Claim, score, provenance, and mechanistic records.
Keep framing, context, and interpretation records embedded until independent
reuse justifies promoting them to separately identified objects. A saved Paragraph
is needed only when its wording or publication metadata needs to be retained.

Defer comprehensive argumentation, automatic evidence aggregation, semantic
identity across paraphrases, unrestricted nested accounts, exhaustive question
and hypothesis taxonomies, and general paper ingestion. None is necessary to
demonstrate the central workflow.

Before scaling, invite community review of the definitions, the result/biology
distinction, discipline-specific context requirements, and ontology export
mappings. Extensions should be motivated by a concrete use case that cannot be
represented adequately by the core. Version the profile and record unresolved
choices rather than presenting the initial design as a completed scientific
claims standard.

## Relationship to the current implementation

The current claims module calls its organizing object `CompositeClaim`, makes
it a subclass of `Claim`, requires at least two components, and requires a
combined Proposition and composition semantics. This proposal replaces that
concept with `ScientificAccount`: a paragraph-level account that can contain
nonassertive framing and does not require a single overall assertion. The rename
and structural changes are proposed here, not implemented by this document.

The existing `Hypothesis` class also combines mechanistic content with assessment
metadata. Its eventual alignment with the distinctions above needs a separate
migration decision. The immediate design can reference existing records without
requiring that migration or claiming that their semantics are already identical.
