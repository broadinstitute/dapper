"""Croissant import mapping (schema/docs/croissant.md), checked on real bytes.

The example Croissant record describes the result files of
example_result_collection.yaml. Each FileObject must match a DAPPER File by
sha256, with contentUrl resolved into location and encodingFormat copied into
mime_type. The record itself must be a File the publication Activity used, and
every column a RecordSet declares must exist in its file. mlcroissant is not a
test dependency; these checks need only the standard library.
"""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from conftest import EXAMPLES

DATA = EXAMPLES / "data/result-collection"
RECORD = DATA / "croissant.json"


@pytest.fixture(scope="module")
def record() -> dict:
    return json.loads(RECORD.read_text())


@pytest.fixture(scope="module")
def collection() -> dict:
    return yaml.safe_load((EXAMPLES / "example_result_collection.yaml").read_text())


def file_objects(record):
    return [d for d in record["distribution"] if d["@type"] == "cr:FileObject"]


def test_record_is_croissant_1_0(record):
    assert record["@type"] == "sc:Dataset"
    assert record["conformsTo"] == "http://mlcommons.org/croissant/1.0"
    assert record["@context"]["cr"] == "http://mlcommons.org/croissant/"
    assert file_objects(record) and record["recordSet"]


def test_every_file_object_is_a_dapper_file_with_the_same_bytes(record, collection):
    files = {f["sha256"]: f for f in collection["files"] if "sha256" in f}
    for obj in file_objects(record):
        data = (DATA / obj["contentUrl"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == obj["sha256"], obj["@id"]
        dapper = files.get(obj["sha256"])
        assert dapper, f"{obj['@id']} has no DAPPER File with its sha256"
        assert dapper["location"] == str((DATA / obj["contentUrl"]).relative_to(EXAMPLES))
        assert dapper["mime_type"] == obj["encodingFormat"]
        assert dapper["size_in_bytes"] == len(data)
        assert dapper["filename"] == obj["contentUrl"].rsplit("/", 1)[-1]


def test_every_file_object_lands_in_a_dataset_role(record, collection):
    by_sha = {f["sha256"]: f["id"] for f in collection["files"] if "sha256" in f}
    role_files = {r["file"] for d in collection["datasets"] for r in d["file_roles"]}
    for obj in file_objects(record):
        assert by_sha[obj["sha256"]] in role_files, obj["@id"]


def test_the_record_itself_is_kept_and_used_by_the_publication(collection):
    data = RECORD.read_bytes()
    kept = [f for f in collection["files"] if f.get("sha256") == hashlib.sha256(data).hexdigest()]
    assert len(kept) == 1 and kept[0]["mime_type"] == "application/ld+json"
    publisher = collection["result_collections"][0]["was_generated_by"]
    used = {(e["subject"], e["object"]) for e in collection["used_edges"]}
    assert (publisher, kept[0]["id"]) in used


def test_record_set_columns_exist_in_their_files(record):
    objects = {o["@id"]: o for o in file_objects(record)}
    for record_set in record["recordSet"]:
        for field in record_set["field"]:
            source = field["source"]
            obj = objects[source["fileObject"]["@id"]]
            rows = [json.loads(line) for line in (DATA / obj["contentUrl"]).read_text().splitlines()]
            column = source["extract"]["column"]
            assert rows and all(column in row for row in rows), field["@id"]
