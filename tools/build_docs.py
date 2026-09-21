#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["linkml==1.11.1", "mkdocs==1.6.1", "mkdocs-material==9.7.7"]
# ///
"""Build LinkML documentation and the provenance portal into one Pages artifact.

    uv run tools/build_docs.py
    uv run tools/build_docs.py --serve --port 8000

Generated Markdown lives in .build/model-docs; the combined site is in site/.
The schema and hand-written guides remain the sources of truth.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import sys

from mkdocs.commands.build import build
from mkdocs.config import load_config
from model_uris import ModelDocGenerator, write_namespace


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / ".build" / "model-docs"
SITE = ROOT / "site"


def build_site() -> None:
    subprocess.run([sys.executable, str(ROOT / "portal" / "build.py"), "--check"], check=True)
    # Only remove this script's generated Markdown, never the source guides.
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    reference = GENERATED / "reference"
    reference.mkdir(parents=True)
    generator = ModelDocGenerator(
        str(ROOT / "schema" / "dapper.yaml"),
        directory=str(reference),
        dialect="python",
        preserve_names=True,
        hierarchical_class_view=True,
        subfolder_type_separation=True,
        render_imports=True,
    )
    generator.serialize()
    # LinkML 1.11.1 can omit the blank line between a slot table and the
    # following heading, which Python Markdown otherwise treats as another row.
    for page in reference.rglob("*.md"):
        markdown = page.read_text()
        if page.parent.name == "enums":
            markdown = generator.enum_mapping_documentation(
                markdown, generator.schemaview.get_enum(page.stem))
        if page.parent.name in ("classes", "slots", "enums", "types"):
            markdown = re.sub(r"(?m)^URI:", "Documentation URI:", markdown, count=1)
        page.write_text(re.sub(r"(?m)^(\|[^\n]*)\n(?=#{1,6} )", r"\1\n\n", markdown))

    shutil.copy2(ROOT / "docs" / "index.md", GENERATED / "index.md")
    shutil.copytree(ROOT / "docs" / "assets", GENERATED / "assets")
    guides = GENERATED / "guides"
    guides.mkdir()
    guide = (ROOT / "schema" / "docs" / "files-and-drs.md").read_text()
    (guides / "files-and-drs.md").write_text(guide.replace("../identity/README.md", "identity.md"))
    shutil.copy2(ROOT / "schema" / "docs" / "claims.md", guides / "claims.md")
    shutil.copy2(ROOT / "schema" / "docs" / "bottom-line-results.md", guides / "bottom-line-results.md")
    shutil.copy2(ROOT / "schema" / "docs" / "ancestry.md", guides / "ancestry.md")
    shutil.copy2(ROOT / "schema" / "identity" / "README.md", guides / "identity.md")
    shutil.copytree(ROOT / "schema" / "examples", GENERATED / "examples",
                    ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    (GENERATED / "schema").mkdir()
    for module in (ROOT / "schema").glob("*.yaml"):
        shutil.copy2(module, GENERATED / "schema" / module.name)

    navigation = [{"Overview": "index.md"}]
    counts = {}
    for section in ("classes", "slots", "enums", "types"):
        pages = sorted((reference / section).glob("*.md"), key=lambda p: p.stem.lower())
        counts[section] = len(pages)
        lines = [f"# {section.title()}", "",
                 "Select a definition to browse its details and connections.", ""]
        lines.extend(f"- [{page.stem}]({page.name})" for page in pages)
        (reference / section / "index.md").write_text("\n".join(lines) + "\n")
        navigation.append({section.title(): [
            {"Browse all": f"reference/{section}/index.md"},
            *[{page.stem: f"reference/{section}/{page.name}"} for page in pages],
        ]})
    navigation.extend([
        {"Guides": [{"Files and DRS": "guides/files-and-drs.md"},
                    {"Bottom-line results": "guides/bottom-line-results.md"},
                    {"Genetic ancestry": "guides/ancestry.md"},
                    {"Claims and the PIGEAN example": "guides/claims.md"},
                    {"Computed identifiers": "guides/identity.md"}]},
        {"Full schema": "reference/index.md"},
    ])
    config = load_config(config_file=str(ROOT / "docs" / "mkdocs.yml"), nav=navigation)
    build(config)

    # The inspector remains at the existing Pages root, with docs under /model/.
    shutil.copy2(ROOT / "portal" / "index.html", SITE / "index.html")
    (SITE / ".nojekyll").touch()
    write_namespace(generator.schemaview, SITE)
    print("Built model documentation: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    print(f"Pages artifact: {SITE}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Preview the combined site on localhost")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    build_site()
    if args.serve:
        handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
        with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
            print(f"Model browser: http://127.0.0.1:{args.port}/model/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
