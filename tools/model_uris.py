"""Documentation CURIEs and resolution of DAPPER's stable vocabulary namespace."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from linkml.generators.docgen import DocGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, EnumDefinition, SlotDefinition, TypeDefinition
from linkml_runtime.utils.schemaview import SchemaView


DOCUMENTATION_PREFIXES = {
    ClassDefinition: "dapper_class",
    SlotDefinition: "dapper_slot",
    EnumDefinition: "dapper_enum",
    TypeDefinition: "dapper_type",
}


def documentation_curie(element) -> str | None:
    """Use the same names as DocGenerator(preserve_names=True)'s page paths."""
    prefix = DOCUMENTATION_PREFIXES.get(type(element))
    return f"{prefix}:{element.name}" if prefix else None


class ModelDocGenerator(DocGenerator):
    """Preserve page names without replacing semantic URIs with schema-id URLs."""

    def __post_init__(self):
        super().__post_init__()
        # LinkML 1.11.1's preserve_names patches both self/native mappings to
        # the displayed documentation URI. Retain the schema's actual mappings.
        self.schemaview.get_mappings = SchemaView.get_mappings.__get__(self.schemaview)

    def uri(self, element, expand=True):
        curie = documentation_curie(element) or self.schemaview.get_uri(element)
        return self.schemaview.expand_curie(curie) if expand else curie

    def enum_mapping_documentation(self, markdown, element):
        """Link enum meanings and expose qualified mappings omitted by LinkML."""
        rows = []
        for pv in element.permissible_values.values():
            if pv.meaning:
                markdown = markdown.replace(f"| {pv.meaning} |", f"| {self.uri_link(pv.meaning)} |")
            else:
                markdown = markdown.replace(f"| {pv.text} | None |", f"| {pv.text} | — |")
            for relation in ("exact", "close", "broad", "narrow", "related"):
                for curie in getattr(pv, f"{relation}_mappings"):
                    rows.append(f"| {pv.text} | {relation} | {self.uri_link(curie)} |")
        if rows:
            section = "\n".join([
                "## Permissible value mappings", "",
                "Mapping types retain their declared strength; a close mapping does not assert equivalence.",
                "", "| Value | Mapping | Target |", "| --- | --- | --- |", *rows, "", "",
            ])
            markdown = markdown.replace("## LinkML Source", section + "## LinkML Source", 1)
        return markdown


def namespace_routes(sv: SchemaView) -> dict[str, str]:
    """Map native names and declared DAPPER predicate aliases to model pages."""
    routes = {}

    def add(curie, target):
        if not curie.startswith("dapper:"):
            return
        term = curie.removeprefix("dapper:")
        if term in routes and routes[term] != target:
            raise ValueError(f"Ambiguous DAPPER term {curie}: {routes[term]} and {target}")
        routes[term] = target

    for elements in (sv.all_classes(), sv.all_slots(attributes=True), sv.all_enums(), sv.all_types()):
        for element in elements.values():
            target = sv.expand_curie(documentation_curie(element)) + "/"
            add(sv.get_uri(element, native=True), target)
            add(sv.get_uri(element), target)

    # Some reified predicates are defined only by an Edge's default predicate,
    # with no equivalent slot_uri. Resolve those to the defining Edge page.
    for element in sv.all_classes().values():
        predicate = element.slot_usage.get("predicate")
        default = str(predicate.ifabsent or "") if predicate else ""
        if default.startswith("string(dapper:") and default.endswith(")"):
            curie = default[len("string("):-1]
            if curie.removeprefix("dapper:") not in routes:
                add(curie, sv.expand_curie(documentation_curie(element)) + "/")
    return dict(sorted(routes.items()))


def write_namespace(sv: SchemaView, site: Path) -> None:
    """Build /ns/#Term with a redirect and a usable no-JavaScript term index."""
    routes = namespace_routes(sv)
    namespace_url = urlsplit(sv.expand_curie("dapper:"))
    site_path = PurePosixPath(namespace_url.path).parent
    local_routes = {}
    # Ensure every redirect is part of this Pages artifact, not a stale link.
    for term, target in routes.items():
        url = urlsplit(target)
        if (url.scheme, url.netloc) != (namespace_url.scheme, namespace_url.netloc):
            raise ValueError(f"DAPPER namespace target is outside this site: {target}")
        relative = PurePosixPath(url.path).relative_to(site_path)
        if not (site / relative / "index.html").is_file():
            raise ValueError(f"DAPPER namespace target was not built: {target}")
        local_routes[term] = f"../{relative}/"
    links = "\n".join(
        f'<li id="{escape(term, quote=True)}"><a href="{escape(target, quote=True)}">'
        f'dapper:{escape(term)}</a></li>' for term, target in local_routes.items()
    )
    data = json.dumps(local_routes, sort_keys=True).replace("<", "\\u003c")
    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DAPPER vocabulary</title>
  <style>body {{ max-width: 52rem; margin: 3rem auto; padding: 0 1rem;
    font: 1rem/1.6 system-ui, sans-serif; }} a {{ color: #087f8c; }}</style>
</head>
<body>
  <h1>DAPPER vocabulary</h1>
  <p id="status">Select a vocabulary term to open its model documentation.</p>
  <p><a href="../model/">Browse the model</a> · <a href="../">Provenance portal</a></p>
  <p>Computed record IDs such as <code>dapper:File.&lt;digest&gt;</code> identify
  data records, not vocabulary definitions; this index does not resolve records.</p>
  <ul>{links}</ul>
  <script id="namespace-routes" type="application/json">{data}</script>
  <script>
    const routes = JSON.parse(document.getElementById('namespace-routes').textContent);
    function resolveTerm() {{
      let term;
      try {{ term = decodeURIComponent(location.hash.slice(1)); }}
      catch {{ term = location.hash.slice(1); }}
      if (Object.prototype.hasOwnProperty.call(routes, term)) {{
        location.replace(routes[term]);
      }} else if (term) {{
        document.getElementById('status').textContent =
          'No vocabulary definition for dapper:' + term + '. Browse the terms below.';
      }}
    }}
    window.addEventListener('hashchange', resolveTerm);
    resolveTerm();
  </script>
</body>
</html>
'''
    namespace = site / "ns"
    namespace.mkdir(exist_ok=True)
    (namespace / "index.html").write_text(page)
