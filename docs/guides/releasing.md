# Releasing a DAPPER version

DAPPER identifiers are computed from content and the schema. Stores such as the claims repository hold records
minted under earlier releases and must be able to carry them forward. So every release ships its own converter
from the release before it, and a release cannot be published without one.

## The rule

**A release that changes any shape ships a converter step.** If a record valid under the previous release
is not valid under the new one, or would mint a different identifier, the release must include a step in
`converter/migrate.py` that converts it. The step must either convert faithfully or refuse.

DAPPER owns these converters, not the stores that use them. A store such as the claims repository vendors
DAPPER and runs its converter. It never writes its own.

A release that changes no shape still adds an entry to `STEPS`, mapping the previous version to the new one
with a step that changes nothing. That records that the move was checked.

## What a step must do

- **Convert faithfully or refuse.** When content cannot move into the new shape without inventing something
  (a DISMECH page nobody recorded, an account with nothing to frame it), the step raises `Refusal` and lists
  every problem. Nothing is written.
- **Never drop content silently.** Content the new release has no place for is returned as a note, which the
  CLI prints.
- **Leave minting to the end.** Steps reshape records and may create new ones with placeholder ids;
  `migrate()` re-mints the whole document once, so references move together. It then runs `verify` and the
  scientific-content checks.
- **Report every id.** `--id-map` writes `{old id: new id}` for every original record, unchanged ones included,
  so a store can record the old id as deprecated by the new one while the object itself stays current.
- **Chain.** `STEPS` maps a release to `(next release, step)`. A document from two releases back runs both
  steps in order.

## What a release must include

1. The schema change, with `version:` raised in every module.
2. The converter step in `converter/migrate.py` and its entry in `STEPS`.
3. **Fixtures of the previous release**, under `tests/fixtures/dapper-<previous version>/`: documents copied
   unchanged from the previous release's tag that use every reshaped class. Do not re-mint them; they are the
   input the step must handle.
4. Tests in `tests/test_migrate.py` showing that each fixture converts, re-mints and verifies, that records
   using no reshaped field keep their ids, and that each refusal fires.
5. The release notes' migration section, naming what the converter does and what it refuses.
6. Frozen identity vectors (`identity/test_vectors.json`) that still reproduce, or an explicit identity
   profile change.

The release is published (tagged) only when all six are in place and the suite passes.

## Using the converter

```bash
uv run converter/migrate.py old.yaml --from 0.2.1-a1 -o new.yaml --id-map ids.json
```

`--to` defaults to this checkout's version. A checkout mints only its own version, so check out the target
release's tag to convert to it. `--dismech-pages pages.json` supplies `{disease CURIE: DISMECH page URL}` for
0.2.1 records whose DISMECH fields name a disease but no page.

## 0.2.1-a1 to 0.3.0-a1

The step converts:

- `mechanistic_model` to `explanatory_model`, on every record;
- `ancestry` and `trait` into sorted, typed `contexts`;
- each `CausalStep` to a `CausalLink` between `CausalVariable`s, one per entity. The step's
  `causal_link_type`, `intermediate_mechanisms` and `via_mechanism` move onto its entry in the model's `links`,
  in `step_index` order. 0.2 did not record which aspect of an entity varies, so the variable's description
  says so;
- a model with no steps but `subject_entity` and `object_entity`: those become its one link (noted);
- `ScientificAccount.question` and `.hypothesis` to `framing`, wrapping the hypothesis Proposition in a
  `hypotheses` record;
- DISMECH fields to a `corresponds_to_dismech_edges` entry, whose object is `dismech_source_url` or the page
  `--dismech-pages` gives for the disease term.

It notes:
- `dismech_disease_term`, which has no place on the edge;
- a model endpoint that is the end of none of its steps, which is kept as a variable of the model, in no link
  (0.3 models have no subject or object);
- a CausalStep in no model, which becomes a standalone link;
- a CausalStep with no `step_subject` or `step_object` (0.2 allowed either to be left out). Every missing end,
  the first step's and the last step's included, becomes a CausalVariable of its own with no entity, described
  from the step. The model's endpoints are not taken to be its first and last steps' ends: a first step need not
  start from the model's subject. Nothing is merged: two unnamed ends are never taken to be the same variable.

It refuses:
- DISMECH fields with no page;
- a model with neither steps nor endpoints;
- an account with neither a question nor a hypothesis.

Single-record illustration files (a bare record with no document groups) are not converted.
