#!/usr/bin/env python3
"""Extract LinkML declarations and connections into graphify JSON.

Usage: uv run --with pyyaml tools/graphify_schema.py

This supplements graphify's code/document extraction without fetching imports.
Only declared structure and literal mentions of known classes are indexed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MAPPINGS = (
    "class_uri", "slot_uri", "uri", "meaning", "exact_mappings",
    "close_mappings", "broad_mappings", "narrow_mappings", "related_mappings",
)
STRUCTURES = {"attributes", "slot_usage", "slots", "permissible_values"}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def extract(schema_path: Path) -> dict:
    source = schema_path.read_text()
    source_file = Path(os.path.relpath(schema_path, ROOT)).as_posix()
    schema = yaml.safe_load(source)
    marks = {}

    def index_marks(node, path=()):
        marks.setdefault(path, node.start_mark.line + 1)
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                child = (*path, key.value)
                marks[child] = key.start_mark.line + 1
                index_marks(value, child)
        elif isinstance(node, yaml.SequenceNode):
            for index, value in enumerate(node.value):
                index_marks(value, (*path, str(index)))

    index_marks(yaml.compose(source))
    stem = normalize(schema_path.stem)
    # Preserve the agreed schema_dapper IDs even when --schema is elsewhere.
    prefix = f"schema_{stem}"
    classes = schema.get("classes", {})
    slots = schema.get("slots", {})
    enums = schema.get("enums", {})
    types = schema.get("types", {})
    nodes, edges, edge_keys = {}, [], set()

    def ident(kind, name):
        return f"{prefix}_{kind}_{normalize(name)}"

    def slot_id(owner, name):
        return f"{ident('class', owner)}_slot_{normalize(name)}"

    def location(path):
        while path not in marks and path:
            path = path[:-1]
        return marks.get(path, 1)

    def add_node(node_id, label, path, kind, spec=None, **extra):
        if node_id in nodes:
            if nodes[node_id]["label"] != label:
                raise ValueError(f"Normalized node ID collision: {node_id}")
            return node_id
        spec = spec or {}
        metadata = {k: v for k, v in spec.items() if k not in STRUCTURES}
        node = {
            "id": node_id, "label": label, "file_type": "concept",
            "source_file": source_file,
            "source_location": f"line {location(path)}",
            "source_line": location(path),
            "source_url": None, "captured_at": None,
            "author": None, "contributor": None,
            "schema_kind": kind, "schema_path": ".".join(path),
            **metadata, **extra,
        }
        mixins = spec.get("mixins", [])
        if "unhashable" in mixins:
            node["hashability"] = "unhashable"
        elif "hashable" in mixins:
            node["hashability"] = "hashable"
        elif spec.get("identifier"):
            node["hashability"] = "identifier_excluded"
        nodes[node_id] = node
        return node_id

    def edge(start, end, relation, path, **extra):
        if start == end or (start, end, relation) in edge_keys:
            return
        edge_keys.add((start, end, relation))
        edges.append({
            "source": start, "target": end, "relation": relation,
            "confidence": "EXTRACTED", "confidence_score": 1.0,
            "source_file": source_file,
            "source_location": f"line {location(path)}",
            "source_line": location(path), "weight": 1.0, **extra,
        })

    def reference(kind, name, path):
        node_id = ident(kind, name)
        if node_id not in nodes:
            add_node(node_id, name, path, f"referenced_{kind}", declared=False)
        return node_id

    def range_node(name, path):
        if name in classes:
            kind = "class"
        elif name in enums:
            kind = "enum"
        else:
            kind = "type"
        return reference(kind, name, path)

    def term(name, path):
        # RDF IRIs are case-sensitive: dcat:Distribution and dcat:distribution
        # must remain distinct even though graphify node IDs are lowercase.
        suffix = hashlib.sha256(name.encode()).hexdigest()[:10]
        return add_node(f"{ident('term', name)}_{suffix}", name, path,
                        "mapping_target", uri=name)

    document = add_node(
        ident("schema", schema.get("name", stem)),
        schema.get("title", schema.get("name", stem)), (), "schema",
        {"description": schema.get("description", "")}, file_type="document",
    )
    for section, kind in (("classes", "class"), ("slots", "slot"),
                          ("enums", "enum"), ("types", "type")):
        for name, spec in schema.get(section, {}).items():
            path = (section, name)
            node_id = add_node(ident(kind, name), name, path, kind, spec, declared=True)
            edge(document, node_id, f"declares_{kind}", path)

    for owner, cls in classes.items():
        for section in ("attributes", "slot_usage"):
            for name, spec in cls.get(section, {}).items():
                path = ("classes", owner, section, name)
                node_id = slot_id(owner, name)
                if node_id in nodes:
                    raise ValueError(f"Attribute and slot_usage share a node: {owner}.{name}")
                add_node(node_id, f"{owner}.{name}", path,
                         "attribute" if section == "attributes" else "slot_usage",
                         spec, owner=owner, slot_name=name, declared=True)
                edge(ident("class", owner), node_id,
                     "declares_slot" if section == "attributes" else "specializes_slot",
                     path)

    def parents(owner):
        spec = classes[owner]
        return ([spec["is_a"]] if spec.get("is_a") else []) + spec.get("mixins", [])

    def declarations(owner, visiting=()):
        """Resolve original slot declarations, retaining paths through mixins."""
        if owner not in classes:
            return {}
        if owner in visiting:
            raise ValueError(f"Cyclic class inheritance: {' -> '.join((*visiting, owner))}")
        result = {}
        for parent in parents(owner):
            for name, origins in declarations(parent, (*visiting, owner)).items():
                result.setdefault(name, set()).update(origins)
        for name in classes[owner].get("slots", []):
            result[name] = {ident("slot", name)}
        for name in classes[owner].get("attributes", {}):
            result[name] = {slot_id(owner, name)}
        return result

    resolved = {owner: declarations(owner) for owner in classes}

    def slot_effective(spec, visiting=()):
        effective = {}
        for parent in ([spec["is_a"]] if spec.get("is_a") else []) + spec.get("mixins", []):
            if parent in slots and parent not in visiting:
                effective.update(slot_effective(slots[parent], (*visiting, parent)))
        effective.update(spec)
        return effective

    def inherited_spec(owner, name, visiting=()):
        """Merge ancestor refinements for searchable slot_usage metadata."""
        if owner not in classes or owner in visiting:
            return {}
        effective = {}
        for parent in parents(owner):
            effective.update(inherited_spec(parent, name, (*visiting, owner)))
        cls = classes[owner]
        if name in cls.get("slots", []):
            effective.update(slot_effective(slots.get(name, {})))
        if name in cls.get("attributes", {}):
            effective.update(slot_effective(cls["attributes"][name]))
        effective.update(cls.get("slot_usage", {}).get(name, {}))
        return effective

    def properties(node_id, spec, path, owner=None, slot=False):
        for relation in ("is_a", "mixins"):
            values = spec.get(relation, [])
            if isinstance(values, str):
                values = [values]
            for index, name in enumerate(values):
                p = (*path, relation) if relation == "is_a" else (*path, relation, str(index))
                edge(node_id, reference("slot" if slot else "class", name, p), relation, p)
        if "range" in spec:
            p = (*path, "range")
            edge(node_id, range_node(spec["range"], p), "range", p)
        for relation in MAPPINGS:
            values = spec.get(relation, [])
            if isinstance(values, str):
                values = [values]
            for index, value in enumerate(values):
                p = (*path, relation, str(index)) if isinstance(spec[relation], list) else (*path, relation)
                edge(node_id, term(value, p), relation, p)
        if slot and "ifabsent" in spec:
            match = re.fullmatch(r"\w+\((.*)\)", str(spec["ifabsent"]))
            if match and ":" in match[1]:
                p = (*path, "ifabsent")
                target = term(match[1], p)
                edge(node_id, target, "predicate_default" if path[-1] == "predicate" else "default_value", p)
                if owner and path[-1] == "predicate":
                    edge(ident("class", owner), target, "edge_predicate", p)
        # Literal prose mentions expose relationships encoded as uriorcurie
        # ranges without claiming that prose imposes a formal range constraint.
        description = spec.get("description", "")
        for name in classes:
            if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", description):
                edge(node_id, ident("class", name), "mentions_class", (*path, "description"))

    for name, spec in slots.items():
        properties(ident("slot", name), spec, ("slots", name), slot=True)
    for name, spec in types.items():
        properties(ident("type", name), spec or {}, ("types", name))
        if (spec or {}).get("typeof"):
            p = ("types", name, "typeof")
            edge(ident("type", name), range_node(spec["typeof"], p), "typeof", p)
    for owner, cls in classes.items():
        class_id = ident("class", owner)
        path = ("classes", owner)
        properties(class_id, cls, path)
        for index, name in enumerate(cls.get("slots", [])):
            p = (*path, "slots", str(index))
            edge(class_id, reference("slot", name, p), "has_slot", p)
        for name, origins in resolved[owner].items():
            for origin in sorted(origins):
                if origin == slot_id(owner, name) or name in cls.get("slots", []):
                    continue
                edge(class_id, origin, "inherits_slot", path,
                     explanation=f"{owner} inherits {name} through is_a/mixins; target is its original declaration.",
                     declaration_source_location=nodes[origin]["source_location"])
        for section in ("attributes", "slot_usage"):
            for name, spec in cls.get(section, {}).items():
                node_id = slot_id(owner, name)
                p = (*path, section, name)
                properties(node_id, spec, p, owner=owner, slot=True)
                effective = inherited_spec(owner, name)
                nodes[node_id]["effective_properties"] = effective
                if not nodes[node_id].get("description") and effective.get("description"):
                    nodes[node_id]["description"] = effective["description"]
                for marker in ("hashable", "unhashable"):
                    if marker in effective.get("mixins", []):
                        nodes[node_id]["hashability"] = marker
                if section == "slot_usage":
                    for origin in sorted(resolved[owner].get(name, [])):
                        edge(node_id, origin, "specializes", p,
                             explanation="Class-specific slot_usage refines this original slot declaration.",
                             declaration_source_location=nodes[origin]["source_location"])
                if "range" not in spec and effective.get("range"):
                    edge(node_id, range_node(effective["range"], p), "effective_range", p,
                         explanation="Range resolved from inherited slot metadata.")

    for name, spec in enums.items():
        enum_id = ident("enum", name)
        properties(enum_id, spec, ("enums", name))
        for value, value_spec in spec.get("permissible_values", {}).items():
            p = ("enums", name, "permissible_values", str(value))
            value_id = add_node(f"{enum_id}_value_{normalize(value)}", f"{name}.{value}",
                                p, "permissible_value", value_spec, enum=name, value=value)
            edge(enum_id, value_id, "has_permissible_value", p)
            properties(value_id, value_spec or {}, p)
    for index, imported in enumerate(schema.get("imports", [])):
        p = ("imports", str(index))
        import_id = add_node(ident("import", imported), imported, p, "import_reference",
                             declared_reference_only=True)
        edge(document, import_id, "imports", p)

    expected = {
        "class": len(classes), "slot": len(slots), "enum": len(enums),
        "type": len(types),
        "attribute": sum(len(c.get("attributes", {})) for c in classes.values()),
        "slot_usage": sum(len(c.get("slot_usage", {})) for c in classes.values()),
        "permissible_value": sum(len(e.get("permissible_values", {})) for e in enums.values()),
    }
    actual = {kind: sum(n["schema_kind"] == kind for n in nodes.values()) for kind in expected}
    if actual != expected:
        raise AssertionError(f"Incomplete declaration coverage: {actual} != {expected}")
    for item in edges:
        if item["source"] not in nodes or item["target"] not in nodes:
            raise AssertionError(f"Missing edge endpoint: {item}")
    return {
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["source"], e["relation"], e["target"])),
        "hyperedges": [], "input_tokens": 0, "output_tokens": 0,
        "extraction_metadata": {
            "extractor": "deterministic LinkML structure", "coverage": actual,
            "imports_resolved": False, "token_usage": "No model invocation; deterministic extraction.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=ROOT / "schema/dapper.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "graphify-out/linkml-extraction.json")
    args = parser.parse_args()
    result = extract(args.schema.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output.resolve()), "nodes": len(result["nodes"]),
                      "edges": len(result["edges"]), **result["extraction_metadata"]["coverage"]}))


if __name__ == "__main__":
    main()
