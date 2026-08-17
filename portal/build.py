#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Build the NIH-DAPP provenance portal — a single self-contained index.html.

Reads the schema and the example documents next door, and inlines them together
with Cytoscape.js + ELK from `lib/`.

Everything is embedded — data AND libraries — so the result is ONE file that
works off disk, behind any static host, on a plane, and inside a hospital
network that blocks CDNs. A page on file:// also cannot fetch its siblings, so
inlining is what makes `open index.html` work at all.

Usage:
    uv run portal/build.py
    uv run portal/build.py --check   # fail if index.html is stale

Re-run it after editing any example or the schema.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
# `schema/` is the model boundary for this repository (see README), so the
# schema and its examples live under it while the portal sits beside it.
SCHEMA_DIR = REPO_ROOT / "schema"
EXAMPLES = SCHEMA_DIR / "examples"
SCHEMA = SCHEMA_DIR / "dapper.yaml"
LIB = HERE / "lib"   # NB: not "vendor/" — akleao sync silently ignores that name
OUT = HERE / "index.html"

# Load order matters: elkjs defines the global cytoscape-elk binds to.
LIB_FILES = ["cytoscape.min.js", "elk.bundled.js", "cytoscape-elk.js", "js-yaml.min.js"]

# Node-list key -> LinkML class. Parsed out of the identity module rather than
# duplicated here: the portal had drifted to 14 groups while the minter had 27,
# so an uploaded document rendered 1 node instead of 18. Read as source rather
# than imported so the portal keeps its light dependency set (no rdflib).
def _node_groups() -> dict[str, str]:
    src = (Path(__file__).parent.parent / "schema" / "identity" / "dapper_identity.py").read_text()
    block = src[src.index("DOC_GROUPS = {"):]
    block = block[: block.index("}") + 1]
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block))


NODE_GROUPS = _node_groups()

# Edge-list key -> (LinkML class, flow direction).
#
# `flow` is the direction the STORY runs, which is not always the direction the
# predicate points. `prov:used` points activity -> file (backwards through
# time), but data flows file -> activity. "reverse" means draw the arrow from
# object to subject so the graph reads raw data first, claim last.
EDGE_GROUPS = {
    "used_edges": ("Used", "reverse"),
    "was_generated_by_edges": ("WasGeneratedBy", "reverse"),
    "asserted_in_edges": ("AssertedIn", "forward"),
    # has_assertion_edges / has_provenance_edges are deliberately NOT drawn as
    # edges — they are containment, rendered by nesting the graphs inside the
    # nanopublication instead.
    "supported_by_nanopub_edges": ("SupportedByNanopub", "reverse"),
    # workspace -> activity in flow terms: the plan comes before the run
    "has_agentic_workspace_edges": ("HasAgenticWorkspace", "reverse"),
}

# Several links live as INLINE FIELDS rather than reified edges. They carry the
# trace and the nanopub's internal structure; without them the graph-part nodes
# float unconnected. "in" = the field's target flows into this node.
INLINE_LINKS = {
    "generated_by_activity": ("prov:wasGeneratedBy", "in"),
    "asserts": ("hycl:claims", "in"),
    "has_agentic_workspace": ("dapper:hasAgenticWorkspace", "in"),
    "provenance_of": ("np:hasProvenance", "out"),
    # CellState -> GeneProgram: the program is upstream of the state it
    # constitutes, same "in" direction as generated_by_activity.
    "has_program": ("dapper:hasProgram", "in"),
}

# Visual family: the narrative arc data -> process -> claim -> publication.
FAMILY = {
    "C2M2File": "data",
    "GeneSet": "data",
    "GeneProgram": "data",
    "Dataset": "data",
    "Activity": "process",
    "Hypothesis": "claim",
    "CausalStep": "claim",
    "Nanopublication": "publication",
    "NanopubAssertion": "part",
    "NanopubProvenance": "part",
    "NanopubPublicationInfo": "part",
    "NanopubSignature": "part",
    "AgenticWorkspace": "workspace",
}

# Which nodes are transcribed from a real pipeline run vs. drawn to show shape.
# Read from the example's own `_illustrative:` list rather than inferred from the
# id, because ids are now content digests (`dapper:Class.digest`) and carry no
# provenance hint. Honesty about this distinction is the point of the examples,
# so it is declared explicitly rather than guessed.


GRAPH_DOCS = [
    {
        "file": "example_claim_provenance_trace.yaml",
        "key": "trace",
        "title": "Claim to C2M2 dataset",
        "blurb": (
            "A scientific claim followed back to the raw files it rests on. The "
            "nanopublication's provenance graph and the dig.geneset C2M2 graph are the "
            "same graph, so the walk needs no special bridge."
        ),
        "start": "dapper:Hypothesis.6dwuSUM4kkq9mpthBu2Mh6BmCV0P-m8x",
    },
    {
        "file": "example_geneset_graph.yaml",
        "key": "geneset",
        "title": "Gene-set provenance",
        "blurb": (
            "The real two-activity DAG behind HuBMAP gene set 402cf4a1, transcribed from "
            "geneset.provenance.json. Every file, activity and edge is real; the one dashed "
            "node is an illustrative agentic workspace that could re-run both steps."
        ),
        "start": "dapper:GeneSet.0dj0poPIUTC8EFQxG5p52jO554zJB6gZ",
    },
    {
        "file": "example_cell_graph.yaml",
        "key": "cellstate",
        "title": "Gene program to cell state",
        "blurb": (
            "The 4.0 single-cell block's two new node types: three real NMF "
            "gene-loading factors (GeneProgram, with member_weights) all "
            "feeding into one curated pancreatic ductal epithelial identity "
            "state (CellState) with the internal marker-curation schema "
            "fields. The pairing is illustrative, exercising multi-program "
            "has_program rather than asserting a biological claim."
        ),
        "start": "dapper:CellState.ekZJBnmB6N1ebJvz9PFYk5yMP026SSCY",
    },
]

def is_illustrative(node_id: str, illustrative: set[str]) -> bool:
    return node_id in illustrative


def load_schema() -> dict:
    """Pull class docs and the authoritative-slot set out of the LinkML schema."""
    schema = yaml.safe_load(SCHEMA.read_text())
    classes: dict[str, dict] = {}
    for name, body in (schema.get("classes") or {}).items():
        body = body or {}
        attrs = {}
        for slot_name, slot in (body.get("attributes") or {}).items():
            slot = slot or {}
            ann = slot.get("annotations") or {}
            attrs[slot_name] = {
                "description": (slot.get("description") or "").strip(),
                # George's rule: a mirror must never rewrite these.
                "authoritative": ann.get("dapper:mirror_mutable") is False,
            }
        ann = body.get("annotations") or {}
        classes[name] = {
            "description": (body.get("description") or "").strip(),
            "level": str(ann.get("dapper:profile_level") or ""),
            "npGraph": ann.get("dapper:np_graph") or "",
            "mappings": (body.get("exact_mappings") or []) + (body.get("close_mappings") or []),
            "attributes": attrs,
            "family": FAMILY.get(name, "part"),
        }
    return classes


def build_graph(spec: dict) -> dict:
    raw = yaml.safe_load((EXAMPLES / spec["file"]).read_text())
    illustrative = set(raw.get("_illustrative") or [])
    nodes, edges = [], []
    for key, cls in NODE_GROUPS.items():
        for node in raw.get(key) or []:
            nodes.append({
                "id": node["id"],
                "cls": cls,
                "family": FAMILY.get(cls, "part"),
                "illustrative": is_illustrative(node["id"], illustrative),
                "label": node.get("name") or node.get("filename") or node["id"].split(":")[-1],
                "fields": {k: v for k, v in node.items() if k != "id"},
            })
    for key, (cls, flow) in EDGE_GROUPS.items():
        for edge in raw.get(key) or []:
            src, dst = edge["subject"], edge["object"]
            if flow == "reverse":
                src, dst = dst, src
            edges.append({"source": src, "target": dst, "cls": cls,
                          "predicate": edge.get("predicate", "")})

    # A nanopublication IS its four named graphs. Nest them inside it so the
    # document boundary is visible: what is inside the box belongs to the
    # nanopub, and every edge crossing the boundary is a REFERENCE to something
    # that lives elsewhere. That distinction is the whole point of the picture.
    by_id = {n["id"]: n for n in nodes}
    for node in nodes:
        if node["cls"] != "Nanopublication":
            continue
        for field in ("has_assertion", "has_provenance",
                      "has_publication_info", "has_signature_element"):
            child = node["fields"].get(field)
            if isinstance(child, str) and child in by_id:
                by_id[child]["parent"] = node["id"]

    ids = {n["id"] for n in nodes}
    seen = {(e["source"], e["target"]) for e in edges}
    for node in nodes:
        for field, (predicate, direction) in INLINE_LINKS.items():
            value = node["fields"].get(field)
            # some inline links are multivalued (has_agentic_workspace), some
            # are single (asserts) — normalise before walking
            targets = value if isinstance(value, list) else [value]
            for target in targets:
                if not isinstance(target, str) or target not in ids:
                    continue
                src, dst = (target, node["id"]) if direction == "in" else (node["id"], target)
                if src == dst or (src, dst) in seen:
                    continue
                seen.add((src, dst))
                edges.append({"source": src, "target": dst, "cls": "(inline)",
                              "predicate": predicate})

    # drop edges pointing at nodes this document does not define
    edges = [e for e in edges if e["source"] in ids and e["target"] in ids]
    return {**{k: spec[k] for k in ("key", "title", "blurb", "start")},
            "source": spec["file"], "nodes": nodes, "edges": edges}


def read_lib() -> str:
    chunks = []
    for name in LIB_FILES:
        path = LIB / name
        if not path.exists():
            raise SystemExit(
                f"missing {path}\n"
                f"Fetch the bundled libraries, e.g.:\n"
                f"  curl -sL -o {path} https://unpkg.com/{name.split('.')[0]}/dist/{name}")
        js = path.read_text(encoding="utf-8", errors="replace")
        # a literal </script> inside a bundle would close the tag early
        js = js.replace("</script", r"<\/script")
        chunks.append(f"/* ---- bundled: {name} ---- */\n{js}")
    return "\n".join(chunks)


def render(payload: dict, lib_js: str) -> str:
    return (TEMPLATE
            .replace("/*__VENDOR__*/", lib_js)
            .replace("/*__DATA__*/", json.dumps(payload, indent=None)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if index.html is out of date")
    args = ap.parse_args()

    payload = {"schema": load_schema(),
               "graphs": [build_graph(g) for g in GRAPH_DOCS],
               # Emitted so the in-browser uploader can build a graph from an
               # arbitrary DAPPER document using the same rules as this script,
               # rather than a second hand-maintained copy of them.
               "config": {"nodeGroups": NODE_GROUPS,
                          "edgeGroups": {k: list(v) for k, v in EDGE_GROUPS.items()},
                          "inlineLinks": {k: list(v) for k, v in INLINE_LINKS.items()},
                          "family": FAMILY}}
    html = render(payload, read_lib())

    if args.check:
        if (OUT.read_text() if OUT.exists() else "") != html:
            print("index.html is stale — re-run: uv run portal/build.py")
            return 1
        print("index.html is up to date")
        return 0

    OUT.write_text(html)
    n_nodes = sum(len(g["nodes"]) for g in payload["graphs"])
    n_edges = sum(len(g["edges"]) for g in payload["graphs"])
    print(f"wrote {OUT}")
    print(f"  {len(payload['graphs'])} graphs · {n_nodes} nodes · {n_edges} edges · "
          f"{len(payload['schema'])} schema classes")
    print(f"  {OUT.stat().st_size / 1024:.0f} KB, fully self-contained")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NIH-DAPP · provenance inspector</title>
<style>
:root {
  --paper: #F7F8F6;
  --paper-sunk: #EEF0EC;
  --ink: #12161C;
  --ink-soft: #4A5259;
  --muted: #79817D;
  --rule: #D2D7CF;
  --rule-strong: #B4BBB2;

  /* node families: the arc data -> process -> claim -> publication */
  --data: #48566B;
  --process: #1F5C4D;
  --claim: #6B5FA0;
  --publication: #8A6A1F;
  --part: #7E8780;
  --workspace: #2A7A8C;

  --trace: #B4531F;
  --focus: #1F5C4D;
  /* text drawn ON a filled family colour — flips with the theme so it stays legible */
  --on-fill: #FFFFFF;

  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #12161C; --paper-sunk: #171C23; --ink: #E7EBE5; --ink-soft: #AAB2AC;
    --muted: #7E877F; --rule: #2A3138; --rule-strong: #3C444C;
    --data: #8FA3C0; --process: #64B39C; --claim: #A79BDA; --publication: #D0AA55;
    --part: #8C958D; --workspace: #6FBACB; --trace: #E68A4E; --focus: #64B39C;
    --on-fill: #12161C;
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--sans); font-size: 14px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.eyebrow {
  font-family: var(--mono); font-size: 10px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--muted);
}

.shell { display: grid; grid-template-rows: auto 1fr; height: 100vh; }
header {
  display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap;
  padding: 14px 20px; border-bottom: 1px solid var(--rule);
}
h1 { margin: 0; font-size: 15px; font-weight: 620; letter-spacing: -.01em; }
h1 span { color: var(--muted); font-weight: 400; }
.tagline { color: var(--ink-soft); font-size: 13px; margin: 0; flex: 1 1 320px; min-width: 0; }

.body { display: grid; grid-template-columns: 224px minmax(0,1fr) 340px; min-height: 0; }
@media (max-width: 1080px) {
  .body { grid-template-columns: 1fr; grid-template-rows: auto minmax(420px,1fr) auto; }
  .rail, .inspector { border: none; border-bottom: 1px solid var(--rule); }
}
.rail { border-right: 1px solid var(--rule); overflow-y: auto; padding: 16px 14px 28px; }
.inspector { border-left: 1px solid var(--rule); overflow-y: auto; padding: 16px 16px 40px; }
#cy { width: 100%; height: 100%; background: var(--paper-sunk); min-height: 0; }

.rail-group { margin-bottom: 22px; }
.rail-group > .eyebrow { display: block; margin-bottom: 8px; }
.pick {
  display: block; width: 100%; text-align: left; cursor: pointer;
  background: none; border: 1px solid transparent; border-radius: 3px;
  padding: 7px 9px; margin-bottom: 2px; color: var(--ink);
  font-family: inherit; font-size: 13px; line-height: 1.35;
}
.pick:hover { background: var(--paper-sunk); }
.pick[aria-current="true"] { background: var(--paper-sunk); border-color: var(--rule-strong); font-weight: 560; }
.pick { overflow: hidden; }
/* long example filenames were running past the rail edge */
.pick small {
  display: block; font-family: var(--mono); font-size: 10px; color: var(--muted);
  margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

#drop {
  border: 1.5px dashed var(--rule-strong); border-radius: 4px; padding: 14px 10px;
  text-align: center; cursor: pointer; color: var(--ink-soft); background: none;
  transition: border-color .15s, background .15s;
}
#drop:hover, #drop.over { border-color: var(--focus); background: var(--paper-sunk); color: var(--ink); }
#drop strong { display: block; font-size: 12.5px; font-weight: 600; }
#drop span { display: block; font-family: var(--mono); font-size: 10px; margin-top: 3px; }
.note.bad { border-left-color: var(--trace); color: var(--trace); }
.note.good { border-left-color: var(--focus); }

.legend-row { display: flex; align-items: center; gap: 9px; margin-bottom: 7px; font-size: 12px; color: var(--ink-soft); }
.legend-row svg { flex: none; }
.note { font-size: 12px; color: var(--ink-soft); border-left: 2px solid var(--rule-strong); padding-left: 10px; margin: 0; }

button.action {
  width: 100%; cursor: pointer; font-family: var(--mono); font-size: 11px;
  letter-spacing: .1em; text-transform: uppercase; padding: 9px 10px;
  background: var(--ink); color: var(--paper); border: none; border-radius: 3px;
}
button.action:hover { background: var(--focus); }
button.action.ghost { background: none; color: var(--ink-soft); border: 1px solid var(--rule-strong); }
button.action.ghost:hover { background: var(--paper-sunk); color: var(--ink); }
button.action + button.action { margin-top: 6px; }
.btn-row { display: flex; gap: 4px; }
/* flex-basis 0 so both share the row evenly regardless of label length */
.btn-row button.action { margin-top: 0; flex: 1 1 0; width: auto; }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }

.insp-empty { color: var(--muted); font-size: 13px; }
.insp-cls {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  padding: 3px 7px; border-radius: 2px; color: var(--on-fill);
}
.insp-id { font-family: var(--mono); font-size: 11.5px; word-break: break-all; margin: 10px 0 4px; line-height: 1.45; }
.insp-id .pfx { color: var(--muted); }
.insp-desc { font-size: 12.5px; color: var(--ink-soft); margin: 10px 0 0; }
.badge {
  display: inline-block; font-family: var(--mono); font-size: 9px; letter-spacing: .1em;
  text-transform: uppercase; padding: 2px 6px; border-radius: 2px; margin: 8px 6px 0 0;
  border: 1px solid var(--rule-strong); color: var(--ink-soft);
}
.badge.warn { border-color: var(--trace); color: var(--trace); }
.badge.solid { background: var(--focus); border-color: var(--focus); color: var(--on-fill); }

.fields { margin: 18px 0 0; border-top: 1px solid var(--rule); }
.field { border-bottom: 1px solid var(--rule); padding: 9px 0; }
.field dt { font-family: var(--mono); font-size: 10.5px; letter-spacing: .06em; color: var(--ink-soft); display: flex; align-items: center; gap: 6px; }
.field dd { margin: 4px 0 0; font-size: 12.5px; word-break: break-word; }
.field dd.mono { font-family: var(--mono); font-size: 11.5px; }
.list-item:not(:last-child)::after { content: ", "; color: var(--ink-soft); }
.field .why { font-size: 11.5px; color: var(--muted); margin-top: 3px; font-style: italic; }
.lock { color: var(--trace); font-size: 10px; }
.ref {
  display: block; background: none; border: none; padding: 0; cursor: pointer;
  font-family: var(--mono); font-size: 11.5px; color: var(--focus); text-align: left;
  text-decoration: underline; text-underline-offset: 2px; word-break: break-all;
}
.ref:hover { color: var(--trace); }
</style>
</head>
<body>
<div class="shell">
  <header>
    <h1>NIH-DAPP <span>· provenance inspector</span></h1>
    <p class="tagline" id="blurb"></p>
  </header>

  <div class="body">
    <aside class="rail">
      <div class="rail-group">
        <span class="eyebrow">Graphs</span>
        <div id="graph-picker"></div>
      </div>

      <div class="rail-group">
        <span class="eyebrow">Your data</span>
        <div id="drop" tabindex="0" role="button"
             aria-label="Open a DAPPER YAML file to inspect it">
          <strong>Drop a DAPPER YAML</strong>
          <span>or click to choose</span>
        </div>
        <input type="file" id="file" accept=".yaml,.yml" hidden>
        <p class="note" id="upload-note" style="margin-top:8px">
          Nothing is uploaded anywhere — the file is read in your browser.
        </p>
      </div>

      <div class="rail-group">
        <span class="eyebrow">Trace</span>
        <button class="action" id="btn-trace">Follow the claim</button>
        <button class="action ghost" id="btn-clear">Clear</button>
        <p class="note" style="margin-top:10px" id="trace-note"></p>
      </div>

      <div class="rail-group">
        <span class="eyebrow">View</span>
        <div class="btn-row">
          <button class="action ghost" id="btn-fit">Fit</button>
          <button class="action ghost" id="btn-reset">Reset</button>
        </div>
      </div>

      <div class="rail-group">
        <span class="eyebrow">Kind</span>
        <div id="legend-family"></div>
      </div>

      <div class="rail-group">
        <span class="eyebrow">Provenance</span>
        <div id="legend-real"></div>
        <p class="note" style="margin-top:8px">
          Solid nodes are transcribed from a real pipeline run. Dashed nodes show the
          shape of a step that has not been run.
        </p>
      </div>
    </aside>

    <main id="cy"></main>
    <aside class="inspector" id="inspector"></aside>
  </div>
</div>

<script>/*__VENDOR__*/</script>
<script>
const DATA = /*__DATA__*/;

const FAMILY_LABEL = { data: "Data", process: "Analysis", claim: "Claim",
                       publication: "Publication", part: "Nanopub graph",
                       workspace: "Agentic workspace" };
const FAMILY_VAR = { data: "--data", process: "--process", claim: "--claim",
                     publication: "--publication", part: "--part",
                     workspace: "--workspace" };
// shape encodes kind, so the graph is readable before you read a label
const FAMILY_SHAPE = { data: "cut-rectangle", process: "barrel", claim: "hexagon",
                       publication: "octagon", part: "round-rectangle",
                       workspace: "ellipse" };
// SVG stand-ins for the legend swatches
const FAMILY_SWATCH = {
  data: "M4,1 L26,1 L29,5 L29,19 L4,19 Z",
  process: "M3,4 Q3,1 9,1 L23,1 Q29,1 29,4 L29,16 Q29,19 23,19 L9,19 Q3,19 3,16 Z",
  claim: "M9,1 L24,1 L30,10 L24,19 L9,19 L3,10 Z",
  publication: "M9,1 L24,1 L30,6 L30,14 L24,19 L9,19 L3,14 L3,6 Z",
  part: "M4,2 L29,2 L29,18 L4,18 Z",
  workspace: "M2,10 A14,9 0 1,0 30,10 A14,9 0 1,0 2,10 Z",
};

const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const state = { graphKey: DATA.graphs[0].key, selected: null, traced: null };
let cy = null;

cytoscape.use(cytoscapeElk);

function buildElements(graph) {
  const els = [];
  for (const n of graph.nodes) {
    const d = { id: n.id, cls: n.cls, family: n.family, label: n.label,
                illustrative: n.illustrative ? 1 : 0 };
    if (n.parent) d.parent = n.parent;
    els.push({ data: d });
  }
  for (const e of graph.edges) {
    els.push({ data: { id: `${e.source}->${e.target}:${e.predicate}`,
                       source: e.source, target: e.target,
                       label: e.predicate || e.cls } });
  }
  return els;
}

function styleSheet() {
  const sheet = [
    { selector: "node", style: {
        // size to the label: these names vary from 8 to 40 characters, and a
        // fixed box either clips them or wastes half the canvas
        shape: "round-rectangle", width: "label", height: "label", padding: 14,
        label: "data(label)", "text-wrap": "wrap", "text-max-width": 190,
        "text-valign": "center", "text-halign": "center",
        "font-family": css("--sans"), "font-size": 11.5, "font-weight": 600,
        "line-height": 1.25,
        color: css("--on-fill"), "border-width": 1.5,
        "transition-property": "opacity", "transition-duration": "180ms",
    }},
    { selector: "node[illustrative = 1]", style: {
        // drawn but not built — hollow body, dashed outline
        "background-opacity": 0, "border-style": "dashed", color: css("--ink"),
    }},
    { selector: "edge", style: {
        width: 1.4, "line-color": css("--rule-strong"),
        "target-arrow-color": css("--rule-strong"), "target-arrow-shape": "triangle",
        "arrow-scale": .85, "curve-style": "bezier",
        label: "data(label)", "font-family": css("--mono"), "font-size": 8,
        color: css("--muted"), "font-size": 9,
        "text-background-color": css("--paper-sunk"), "text-background-opacity": 1,
        "text-background-padding": 3, "text-margin-y": -2,
    }},
    // Selection must be obvious against ANY family fill, so it is a halo
    // outside the node rather than a border-colour change that vanishes on a
    // node whose fill is already that colour.
    { selector: "node:selected", style: {
        "outline-width": 4, "outline-color": css("--focus"),
        "outline-opacity": 1, "outline-offset": 3,
        "border-width": 2.5, "border-color": css("--focus"),
    }},
    { selector: ".dim", style: { opacity: .16 } },
    { selector: "node.lit", style: { "border-width": 3, "border-color": css("--trace") } },
    { selector: "edge.lit", style: {
        "line-color": css("--trace"), "target-arrow-color": css("--trace"),
        width: 2.4, color: css("--trace"),
    }},
  ];
  for (const [fam, v] of Object.entries(FAMILY_VAR)) {
    sheet.push({ selector: `node[family = "${fam}"]`, style: {
      shape: FAMILY_SHAPE[fam], "background-color": css(v), "border-color": css(v),
    }});
  }
  // A nanopublication with children is drawn as a labelled BOX around them,
  // not as a glyph: it is a container of four named graphs, and seeing the
  // boundary is what tells you the big upstream DAG is outside it.
  sheet.push({ selector: "node:parent", style: {
      shape: "round-rectangle", "background-opacity": 0.06,
      "background-color": css("--publication"), "border-color": css("--publication"),
      "border-width": 1.5, "border-style": "solid", padding: 16,
      "text-valign": "top", "text-halign": "center", "text-margin-y": -6,
      color: css("--publication"), "font-size": 11, "font-weight": 650,
      "text-max-width": 320,
  }},
  { selector: "node:parent[illustrative = 1]", style: { "border-style": "dashed" } });

  // angled silhouettes cut their own corners, so the label needs to sit further
  // inside the bounding box than a rectangle's would
  sheet.push({ selector: 'node[family = "process"]', style: { padding: 18 } });
  sheet.push({ selector: 'node[family = "claim"]', style: { padding: 26 } });
  sheet.push({ selector: 'node[family = "publication"]', style: { padding: 22 } });
  sheet.push({ selector: 'node[family = "workspace"]', style: { padding: 34 } });
  return sheet;
}

function renderGraph() {
  const graph = DATA.graphs.find(g => g.key === state.graphKey);
  document.getElementById("blurb").textContent = graph.blurb;
  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: buildElements(graph),
    style: styleSheet(),
    // ELK layered: same top-to-bottom DAG as dagre, but it understands the
    // nanopublication containers and lays their contents out inside the box.
    layout: {
      name: "elk", padding: 28,
      elk: {
        algorithm: "layered",
        "elk.direction": "DOWN",
        "elk.spacing.nodeNode": 34,
        "elk.layered.spacing.nodeNodeBetweenLayers": 58,
        "elk.hierarchyHandling": "INCLUDE_CHILDREN",
        "elk.padding": "[top=34,left=16,bottom=16,right=16]",
      },
    },
    wheelSensitivity: .2, minZoom: .2, maxZoom: 2.5,
  });
  cy.on("tap", "node", ev => {
    state.selected = ev.target.id();
    renderInspector(); renderRail();
  });
  cy.on("tap", ev => { if (ev.target === cy) clearTrace(); });
  cy.ready(() => {
    cy.zoom(1);
    const bb = cy.elements().boundingBox();
    cy.pan({ x: cy.width() / 2 - (bb.x1 + bb.x2) / 2, y: 36 - bb.y1 });
  });
  if (state.selected && cy.$id(state.selected).length) cy.$id(state.selected).select();
}

/* ---- trace: everything the selected node depends on ---- */
function applyTrace(startId) {
  const start = cy.$id(startId);
  if (!start.length) return;
  // Walk the DAG, but also pull in anything a traced node CONTAINS or is
  // contained by — a nanopub's provenance graph is part of the nanopub, not a
  // separate hop. Repeat until the set stops growing.
  let keep = start.union(start.ancestors()).union(start.descendants());
  for (let i = 0; i < 20; i++) {
    const next = keep.union(keep.predecessors()).union(keep.ancestors()).union(keep.descendants());
    if (next.length === keep.length) break;
    keep = next;
  }
  cy.elements().addClass("dim");
  keep.removeClass("dim").addClass("lit");
  state.traced = startId;
  const roots = keep.nodes().filter(n => n.incomers("edge").length === 0);
  document.getElementById("trace-note").textContent =
    `${keep.nodes().length} nodes upstream, ${roots.length} raw source${roots.length === 1 ? "" : "s"}. ` +
    `Everything else is dimmed.`;
  cy.animate({ fit: { eles: keep, padding: 40 } }, { duration: 320,
    complete: () => { if (cy.zoom() > 1.1) { cy.zoom(1.1); cy.center(keep); } } });
}

function clearTrace() {
  if (!cy) return;
  cy.elements().removeClass("dim").removeClass("lit");
  state.traced = null;
  document.getElementById("trace-note").textContent =
    "Lights the path from a claim back to every raw C2M2 file it rests on. Select any node first to trace from there.";
}

/* ---- inspector ---- */
const inspector = document.getElementById("inspector");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function splitId(id) {
  const i = Math.max(id.lastIndexOf(":"), id.lastIndexOf("/"));
  return i < 0 ? ["", id] : [id.slice(0, i + 1), id.slice(i + 1)];
}

function valueHtml(v, ids) {
  if (Array.isArray(v))
    return `<span class="list-item">${v.map(x => valueHtml(x, ids)).join('</span><span class="list-item">')}</span>`;
  if (v && typeof v === "object") return `<span class="mono">${esc(JSON.stringify(v))}</span>`;
  const s = String(v);
  if (ids.has(s)) return `<button class="ref" data-goto="${esc(s)}">${esc(s)}</button>`;
  if (/^https?:\/\//.test(s))
    return `<a class="ref" href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(s)}</a>`;
  const looksId = /^(dapper:|MONDO:|HGNC:|CL:|GO:|PMID:|orcid:|s3:)/.test(s);
  return `<span class="${looksId ? "mono" : ""}">${esc(s)}</span>`;
}

function fieldsHtml(fields, cls, ids) {
  let html = `<dl class="fields">`;
  for (const [k, v] of Object.entries(fields)) {
    const meta = (cls.attributes || {})[k] || {};
    const lock = meta.authoritative
      ? `<span class="lock" title="Authoritative — a mirror must not rewrite this">&#9679; locked</span>` : "";
    html += `<div class="field"><dt>${esc(k)} ${lock}</dt><dd>${valueHtml(v, ids)}</dd>`;
    if (meta.description) html += `<div class="why">${esc(meta.description)}</div>`;
    html += `</div>`;
  }
  return html + `</dl>`;
}

function renderInspector() {
  if (!state.selected) {
    inspector.innerHTML = `<span class="eyebrow">Inspector</span>
      <p class="insp-empty" style="margin-top:10px">Select a node to see its fields, what its
      class means, and which values a mirror is forbidden to rewrite.</p>`;
    return;
  }
  const graph = DATA.graphs.find(g => g.key === state.graphKey);
  const node = graph.nodes.find(n => n.id === state.selected);
  if (!node) { inspector.innerHTML = ""; return; }
  const cls = DATA.schema[node.cls] || {};
  const color = `var(${FAMILY_VAR[node.family] || "--part"})`;
  const [pfx, tail] = splitId(node.id);

  const badges = [node.illustrative
    ? `<span class="badge warn">Illustrative</span>`
    : `<span class="badge solid">Real run</span>`];
  if (cls.level) badges.push(`<span class="badge">Profile ${cls.level}</span>`);
  if (cls.npGraph) badges.push(`<span class="badge">${cls.npGraph} graph</span>`);

  let html = `<span class="eyebrow">Inspector</span>
    <div style="margin-top:10px"><span class="insp-cls" style="background:${color}">${node.cls}</span></div>
    <p class="insp-id"><span class="pfx">${esc(pfx)}</span>${esc(tail)}</p>
    <div>${badges.join("")}</div>`;
  if (cls.description) html += `<p class="insp-desc">${esc(cls.description)}</p>`;
  if (cls.mappings && cls.mappings.length)
    html += `<p class="insp-desc"><strong>Maps to</strong> ${cls.mappings.map(esc).join(", ")}</p>`;
  html += fieldsHtml(node.fields, cls, new Set(graph.nodes.map(n => n.id)));
  inspector.innerHTML = html;
  wireRefs();
}

function wireRefs() {
  inspector.querySelectorAll(".ref").forEach(b => {
    b.addEventListener("click", () => {
      const id = b.dataset.goto;
      state.selected = id;
      if (cy) {
        cy.$("node:selected").unselect();
        const n = cy.$id(id);
        if (n.length) { n.select(); cy.animate({ center: { eles: n } }, { duration: 300 }); }
      }
      renderInspector();
    });
  });
}

/* ---- rail ---- */
function renderRail() {
  const gp = document.getElementById("graph-picker");
  gp.innerHTML = "";
  for (const g of DATA.graphs) {
    const b = document.createElement("button");
    b.className = "pick";
    b.setAttribute("aria-current", String(g.key === state.graphKey));
    b.innerHTML = `${esc(g.title)}<small>${esc(g.source)}</small>`;
    b.addEventListener("click", () => {
      state.graphKey = g.key; state.selected = null; state.traced = null;
      renderGraph(); clearTrace(); renderRail(); renderInspector();
    });
    gp.appendChild(b);
  }

  const fam = document.getElementById("legend-family");
  fam.innerHTML = "";
  for (const [key, label] of Object.entries(FAMILY_LABEL)) {
    const row = document.createElement("div");
    row.className = "legend-row";
    row.innerHTML = `<svg width="32" height="20" viewBox="0 0 32 20" aria-hidden="true">
      <path d="${FAMILY_SWATCH[key]}" fill="var(${FAMILY_VAR[key]})"/></svg><span>${label}</span>`;
    fam.appendChild(row);
  }

  document.getElementById("legend-real").innerHTML = `
    <div class="legend-row"><svg width="32" height="20" viewBox="0 0 32 20" aria-hidden="true">
      <path d="${FAMILY_SWATCH.data}" fill="var(--data)"/></svg><span>Real run</span></div>
    <div class="legend-row"><svg width="32" height="20" viewBox="0 0 32 20" aria-hidden="true">
      <path d="${FAMILY_SWATCH.data}" fill="none" stroke="var(--data)" stroke-width="1.5"
        stroke-dasharray="4 3"/></svg><span>Illustrative</span></div>`;
}

/* ---- actions ---- */
document.getElementById("btn-trace").addEventListener("click", () => {
  const graph = DATA.graphs.find(g => g.key === state.graphKey);
  const start = state.selected || graph.start;
  state.selected = start;
  cy.$("node:selected").unselect();
  const n = cy.$id(start);
  if (n.length) n.select();
  applyTrace(start);
  renderInspector();
});
document.getElementById("btn-clear").addEventListener("click", clearTrace);
document.getElementById("btn-fit").addEventListener("click",
  () => cy.animate({ fit: { padding: 30 } }, { duration: 260 }));
document.getElementById("btn-reset").addEventListener("click", () => {
  clearTrace();
  cy.$("node:selected").unselect();
  state.selected = null;
  cy.animate({ fit: { padding: 30 } }, { duration: 260 });
  renderInspector(); renderRail();
});

/* ---- open a DAPPER document from disk ------------------------------------
   Builds a graph from an arbitrary DAPPER YAML using DATA.config, which the
   build script emits from the same constants it uses itself, so the browser and
   the build agree by construction instead of by a second hand-kept copy.
   The file is read with FileReader and never leaves the machine.
--------------------------------------------------------------------------- */
function graphFromDoc(raw, filename) {
  const C = DATA.config;
  const illustrative = new Set(raw._illustrative || []);
  const nodes = [], edges = [];

  for (const group in C.nodeGroups) {
    const cls = C.nodeGroups[group];
    for (const n of raw[group] || []) {
      const fields = Object.assign({}, n);
      delete fields.id;
      nodes.push({
        id: n.id, cls: cls, family: C.family[cls] || "part",
        illustrative: illustrative.has(n.id),
        label: n.name || n.filename || String(n.id).split(/[:.]/).pop(),
        fields: fields
      });
    }
  }
  const ids = new Set(nodes.map(n => n.id));

  for (const group in C.edgeGroups) {
    const cls = C.edgeGroups[group][0], flow = C.edgeGroups[group][1];
    for (const e of raw[group] || []) {
      let src = e.subject, dst = e.object;
      if (flow === "reverse") { const t = src; src = dst; dst = t; }
      edges.push({ source: src, target: dst, cls: cls, predicate: e.predicate || "" });
    }
  }

  const byId = {};
  nodes.forEach(n => { byId[n.id] = n; });
  const NESTED = ["has_assertion", "has_provenance",
                  "has_publication_info", "has_signature_element"];
  for (const n of nodes) {
    if (n.cls !== "Nanopublication") continue;
    for (const f of NESTED) {
      const child = n.fields[f];
      if (typeof child === "string" && byId[child]) byId[child].parent = n.id;
    }
  }

  const seen = new Set(edges.map(e => e.source + " " + e.target));
  for (const n of nodes) {
    for (const field in C.inlineLinks) {
      const predicate = C.inlineLinks[field][0], dir = C.inlineLinks[field][1];
      const v = n.fields[field];
      const targets = Array.isArray(v) ? v : [v];
      for (const t of targets) {
        if (typeof t !== "string" || !ids.has(t)) continue;
        const src = dir === "in" ? t : n.id;
        const dst = dir === "in" ? n.id : t;
        const key = src + " " + dst;
        if (src === dst || seen.has(key)) continue;
        seen.add(key);
        edges.push({ source: src, target: dst, cls: "(inline)", predicate: predicate });
      }
    }
  }

  const startNode = nodes.find(n => n.fields.supported_by_nanopub) || nodes[0];
  return {
    key: "__upload__", title: filename, blurb: "", source: filename,
    start: startNode ? startNode.id : null,
    nodes: nodes,
    edges: edges.filter(e => ids.has(e.source) && ids.has(e.target))
  };
}

/* Structural checks only, deliberately. Recomputing a digest here would need
   byte-for-byte parity with rdflib's n-triples output, and a wrong green tick is
   worse than none — `dapper_identity.py verify` is the authority. These checks
   need no such parity and catch what actually breaks a graph. */
function inspectDoc(g) {
  const counts = {};
  g.nodes.forEach(n => { counts[n.id] = (counts[n.id] || 0) + 1; });
  const dupes = Object.keys(counts).filter(k => counts[k] > 1);

  const ids = new Set(g.nodes.map(n => n.id));
  const dangling = new Set();
  const scan = v => {
    if (typeof v === "string") {
      if (v.indexOf("dapper:") === 0 && !ids.has(v)) dangling.add(v);
    } else if (Array.isArray(v)) v.forEach(scan);
    else if (v && typeof v === "object") Object.keys(v).forEach(k => scan(v[k]));
  };
  g.nodes.forEach(n => scan(n.fields));

  const minted = g.nodes.filter(n => String(n.id).indexOf("dapper:") === 0).length;
  const lines = [g.nodes.length + " nodes", g.edges.length + " edges",
                 minted + "/" + g.nodes.length + " ids minted"];
  if (dupes.length) lines.push(dupes.length + " duplicate id(s)");
  if (dangling.size) lines.push(dangling.size + " dangling ref(s)");
  return { lines: lines, ok: !dupes.length && !dangling.size };
}

function loadDoc(text, filename) {
  const note = document.getElementById("upload-note");
  let raw;
  try {
    raw = jsyaml.load(text);
  } catch (err) {
    note.className = "note bad";
    note.textContent = "Could not parse " + filename + ": " + err.message;
    return;
  }
  if (!raw || typeof raw !== "object") {
    note.className = "note bad";
    note.textContent = filename + " is not a DAPPER document.";
    return;
  }
  const g = graphFromDoc(raw, filename);
  if (!g.nodes.length) {
    note.className = "note bad";
    note.textContent = "No DAPPER nodes in " + filename +
      ". Expected keys like c2m2_files, activities, gene_sets — the shape mint.py writes.";
    return;
  }
  const report = inspectDoc(g);
  g.blurb = filename + " — " + report.lines.join(" · ");
  DATA.graphs = DATA.graphs.filter(x => x.key !== "__upload__");
  DATA.graphs.unshift(g);
  state.graphKey = "__upload__";
  state.selected = null;
  state.traced = null;
  renderGraph(); clearTrace(); renderRail(); renderInspector();
  note.className = report.ok ? "note good" : "note bad";
  note.textContent = report.ok
    ? filename + ": " + report.lines.join(", ") + ". Structure checks out."
    : filename + ": " + report.lines.join(", ") + ".";
}

const dropZone = document.getElementById("drop");
const filePicker = document.getElementById("file");
dropZone.addEventListener("click", () => filePicker.click());
dropZone.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); filePicker.click(); }
});
filePicker.addEventListener("change", e => {
  const f = e.target.files[0];
  if (f) f.text().then(t => loadDoc(t, f.name));
});
["dragenter", "dragover"].forEach(ev => dropZone.addEventListener(ev, e => {
  e.preventDefault(); dropZone.classList.add("over");
}));
["dragleave", "drop"].forEach(ev => dropZone.addEventListener(ev, e => {
  e.preventDefault(); dropZone.classList.remove("over");
}));
dropZone.addEventListener("drop", e => {
  const f = e.dataTransfer.files[0];
  if (f) f.text().then(t => loadDoc(t, f.name));
});

renderRail();
renderGraph();
clearTrace();
renderInspector();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
