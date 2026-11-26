#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "rdflib", "linkml-runtime"]
# ///
"""Project a DISMECH pathograph onto DAPPER causal graphs, and back.

    uv run tools/dismech_pathograph.py import kb/disorders/Alzheimer_Disease.yaml
    uv run tools/dismech_pathograph.py roundtrip kb/disorders/*.yaml

DISMECH calls a disease's causal graph its pathograph: CausalEdges listed under
`downstream` on Pathophysiology nodes and `sequelae` on Phenotype nodes, each
naming its target node by string. The projection (see schema/dismech.yaml):

  node            -> CausalVariable, with a CorrespondsToDismech edge naming
                     the node; a Phenotype's variable has aspect `presence`
  CausalEdge      -> CausalLink (owning node -> target), placed in a
                     MechanisticModel by a MechanisticLink
  hypothesis group-> one MechanisticModel per group, plus one for edges in no
                     group (corresponding to the dismech:Disease entry)

Nothing is added that the source does not say: effect_direction stays unset,
and a link's statement is the edge description or "<cause> is causally
upstream of <effect>." Edge evidence is not projected yet. A target naming no
node still becomes a variable, without a correspondence.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "identity"))
from dapper_identity import assign_ids, load_schema  # noqa: E402

PAGE = "https://dismech.monarchinitiative.org/pages/disorders/{}.html"
# node list -> (edge list on its nodes, DISMECH class, variable aspect)
KINDS = {
    "pathophysiology": ("downstream", "dismech:Pathophysiology", None),
    "phenotypes": ("sequelae", "dismech:Phenotype", "presence"),
}
CLASS_KIND = {cls: kind for kind, (_, cls, _) in KINDS.items()}


def generated_statement(cause: str, effect: str) -> str:
    return f"{cause} is causally upstream of {effect}."


def page_for(path: Path) -> str:
    return PAGE.format(path.stem)


def from_dismech(disease: dict, page: str, sv=None) -> dict:
    """A DAPPER document fragment for one DISMECH disease file, with minted ids."""
    name = disease.get("name") or page
    variables: dict[tuple, dict] = {}     # (description, aspect) -> record
    node_var: dict[tuple[str, str], str] = {}  # (kind, node name) -> variable id
    corresponds: list[dict] = []

    def variable(description: str, aspect: str | None) -> str:
        key = (description, aspect)
        if key not in variables:
            record = {"id": f"dapper:CausalVariable.v{len(variables)}", "name": description,
                      "description": description}
            if aspect:
                record["aspect"] = aspect
            variables[key] = record
        return variables[key]["id"]

    for kind, (_, dismech_class, aspect) in KINDS.items():
        for node in disease.get(kind) or []:
            if isinstance(node, dict) and isinstance(node.get("name"), str):
                vid = variable(node["name"], aspect)
                if (kind, node["name"]) not in node_var:
                    node_var[(kind, node["name"])] = vid
                    corresponds.append({"subject": vid, "predicate": "skos:closeMatch",
                                        "object": page, "dismech_class": dismech_class,
                                        "entry_key": node["name"]})

    def resolve(target: str) -> str:
        # A name used by both kinds resolves to the Pathophysiology node.
        for kind in KINDS:
            if (kind, target) in node_var:
                return node_var[(kind, target)]
        return variable(target, None)

    links: dict[tuple, dict] = {}          # (cause, effect, statement) -> record
    models: dict[str | None, list[dict]] = {}
    for kind, (edge_list, _, _) in KINDS.items():
        for node in disease.get(kind) or []:
            if not isinstance(node, dict) or not isinstance(node.get("name"), str):
                continue
            cause = node_var[(kind, node["name"])]
            for edge in node.get(edge_list) or []:
                if not isinstance(edge, dict) or not isinstance(edge.get("target"), str):
                    continue
                effect = resolve(edge["target"])
                statement = edge.get("description") or generated_statement(node["name"], edge["target"])
                key = (cause, effect, statement)
                if key not in links:
                    links[key] = {"id": f"dapper:CausalLink.l{len(links)}",
                                  "name": f"{node['name']} -> {edge['target']}",
                                  "statement": statement, "scope": f"In {name}.",
                                  "relation_kind": "CAUSATION", "cause": cause, "effect": effect}
                entry: dict[str, Any] = {"link": links[key]["id"]}
                if edge.get("causal_link_type"):
                    entry["link_type"] = edge["causal_link_type"]
                if edge.get("intermediate_mechanisms"):
                    entry["intermediates"] = list(edge["intermediate_mechanisms"])
                for group in edge.get("hypothesis_groups") or [None]:
                    if entry not in models.setdefault(group, []):
                        models[group].append(dict(entry))

    by_id = {record["id"]: record for record in links.values()}
    mechanistic_models = []
    for i, (group, entries) in enumerate(sorted(models.items(), key=lambda kv: (kv[0] is not None, kv[0] or ""))):
        used = sorted({by_id[e["link"]][end] for e in entries for end in ("cause", "effect")})
        model = {"id": f"dapper:MechanisticModel.m{i}",
                 "name": f"{name}: {group}" if group else f"{name}: pathograph",
                 "description": (f"DISMECH hypothesis group {group} for {name}." if group else
                                 f"DISMECH pathograph edges for {name} that are in no hypothesis group."),
                 "variables": used, "links": entries}
        if _has_cycle(entries, by_id):
            model["has_feedback"] = True
        mechanistic_models.append(model)
        corresponds.append({"subject": model["id"], "predicate": "skos:closeMatch", "object": page,
                            "dismech_class": "dismech:MechanisticHypothesis" if group else "dismech:Disease",
                            "entry_key": group or name})

    doc = {"causal_variables": list(variables.values()), "causal_links": list(links.values()),
           "mechanistic_models": mechanistic_models, "corresponds_to_dismech_edges": corresponds}
    assign_ids(doc, sv or load_schema())
    return doc


def _has_cycle(entries: list[dict], links: dict[str, dict]) -> bool:
    graph: dict[str, set[str]] = {}
    for e in entries:
        graph.setdefault(links[e["link"]]["cause"], set()).add(links[e["link"]]["effect"])
    state: dict[str, int] = {}

    def visit(u: str) -> bool:
        state[u] = 1
        for v in graph.get(u, ()):
            if state.get(v) == 1 or (not state.get(v) and visit(v)):
                return True
        state[u] = 2
        return False

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    return any(not state.get(u) and visit(u) for u in list(graph))


def to_dismech(doc: dict) -> dict:
    """The pathograph edges a projected document says, keyed like DISMECH."""
    variables = {v["id"]: v for v in doc.get("causal_variables") or []}
    links = {l["id"]: l for l in doc.get("causal_links") or []}
    node_of: dict[str, tuple[str, str]] = {}
    group_of: dict[str, str | None] = {}
    for c in doc.get("corresponds_to_dismech_edges") or []:
        if c["subject"] in variables and c.get("dismech_class") in CLASS_KIND:
            node_of[c["subject"]] = (CLASS_KIND[c["dismech_class"]], c["entry_key"])
        elif c.get("dismech_class") == "dismech:MechanisticHypothesis":
            group_of[c["subject"]] = c["entry_key"]
        elif c.get("dismech_class") == "dismech:Disease":
            group_of[c["subject"]] = None

    def node_name(vid: str) -> str:
        return node_of[vid][1] if vid in node_of else variables[vid]["description"]

    edges: dict[tuple, list] = {}          # edge content -> groups
    for model in doc.get("mechanistic_models") or []:
        group = group_of.get(model["id"])
        for entry in model.get("links") or []:
            link = links[entry["link"]]
            kind, source = node_of[link["cause"]]
            target = node_name(link["effect"])
            description = None if link["statement"] == generated_statement(source, target) else link["statement"]
            key = (kind, source, target, description, entry.get("link_type"),
                   tuple(entry.get("intermediates") or ()))
            edges.setdefault(key, []).append(group)

    out: dict[str, dict[str, list]] = {kind: {} for kind in KINDS}
    for (kind, source, target, description, link_type, intermediates), groups in edges.items():
        named = sorted(g for g in groups if g is not None)
        variants = ([[]] if None in groups else []) + ([named] if named else [])
        for hypothesis_groups in variants:
            edge: dict[str, Any] = {"target": target}
            if description:
                edge["description"] = description
            if link_type:
                edge["causal_link_type"] = link_type
            if intermediates:
                edge["intermediate_mechanisms"] = list(intermediates)
            if hypothesis_groups:
                edge["hypothesis_groups"] = hypothesis_groups
            out[kind].setdefault(source, []).append(edge)
    return {kind: [{"name": n, KINDS[kind][0]: e} for n, e in sorted(nodes.items())]
            for kind, nodes in out.items() if nodes}


def edge_set(disease: dict) -> set[tuple]:
    """A pathograph's edges as comparable tuples (order and duplicates ignored)."""
    found = set()
    for kind, (edge_list, _, _) in KINDS.items():
        for node in disease.get(kind) or []:
            if not isinstance(node, dict) or not isinstance(node.get("name"), str):
                continue
            for e in node.get(edge_list) or []:
                if isinstance(e, dict) and isinstance(e.get("target"), str):
                    found.add((kind, node["name"], e["target"], e.get("description") or None,
                               e.get("causal_link_type") or None,
                               tuple(e.get("intermediate_mechanisms") or ()),
                               tuple(sorted(e.get("hypothesis_groups") or ()))))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("import", help="print the DAPPER projection of one disease file")
    one.add_argument("file", type=Path)
    many = sub.add_parser("roundtrip", help="project and export back; report edge-set differences")
    many.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    sv = load_schema()
    if args.command == "import":
        disease = yaml.safe_load(args.file.read_text())
        yaml.safe_dump(from_dismech(disease, page_for(args.file), sv), sys.stdout, sort_keys=False)
        return 0
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    differ = feedback = 0
    for path in args.files:
        disease = yaml.load(path.read_text(), Loader=loader)
        if not isinstance(disease, dict):
            continue
        doc = from_dismech(disease, page_for(path), sv)
        feedback += any(m.get("has_feedback") for m in doc["mechanistic_models"])
        if edge_set(to_dismech(doc)) != edge_set(disease):
            differ += 1
            print(f"differs: {path}")
    print(f"{len(args.files)} file(s); {differ} differ after the round trip; "
          f"{feedback} with a declared feedback loop")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
