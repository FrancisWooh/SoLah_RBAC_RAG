"""Database -> knowledge base sync: row ACLs, attach role, normal vs partitioned
records, change/removal handling and the fail-closed rules. apply_rows() takes the
rows directly, so no external database is needed."""

import uuid

import pytest

from app.models.data_source import DataSource
from app.models.document import Document
from app.services import db_sync
from app.services.embeddings.mock_embedder import MockEmbedder


class FakeStore:
    def __init__(self):
        self.chunks: dict[str, list] = {}

    def upsert(self, chunks):
        for c in chunks:
            self.chunks.setdefault(c.doc_id, []).append(c)

    def delete_doc(self, doc_id):
        self.chunks.pop(doc_id, None)


@pytest.fixture()
def ctx(db_session, make_role):
    for r in ("hr_manager", "exec", "employee"):
        make_role(r)
    source = DataSource(
        name=f"Test{uuid.uuid4().hex[:6]} Database", type="postgresql",
        connection_config=dict(table="knowledge_records", id_column="record_code", title_column="title",
                               content_columns=["content"], category_column="category"),
        permission_mapping=dict(attach_roles=["hr_manager"], clearance_column="required_clearance",
                                compartment_column="compartment", roles_column="allowed_roles", default_clearance=1),
    )
    db_session.add(source)
    db_session.flush()
    return source, FakeStore(), MockEmbedder(dim=32)


def row(code, content="Some policy text.", clearance=2, compartment=None, roles=None, title=None):
    return dict(record_code=code, title=title or f"Title {code}", category="Cat", content=content,
                required_clearance=clearance, compartment=compartment, allowed_roles=roles)


def sync(db_session, ctx, rows):
    source, store, emb = ctx
    return db_sync.apply_rows(db_session, source, rows, emb, store)


def doc_for(db_session, ctx, code):
    return db_session.get(Document, f"db_{db_sync.source_key(ctx[0])}_{db_sync._slug(code)}")


def test_attach_role_is_the_default_and_a_row_can_override_it(db_session, ctx):
    r = sync(db_session, ctx, [row("A1"), row("A2", roles=["employee"], clearance=1), row("A3", roles=["hr_manager", "exec"])])
    assert not r.errors and not r.skipped and len(r.added) == 3
    assert doc_for(db_session, ctx, "A1").allowed_roles == ["hr_manager"]
    assert doc_for(db_session, ctx, "A2").allowed_roles == ["employee"]
    assert doc_for(db_session, ctx, "A3").allowed_roles == ["hr_manager", "exec"]


def test_normal_vs_partitioned_records(db_session, ctx):
    sync(db_session, ctx, [row("N1"), row("Z1", clearance=3, compartment="HR"), row("Z2", compartment="hr, board", clearance=4)])
    assert doc_for(db_session, ctx, "N1").compartments == []
    assert doc_for(db_session, ctx, "Z1").compartments == ["hr"]
    assert doc_for(db_session, ctx, "Z1").required_clearance == 3
    assert doc_for(db_session, ctx, "Z2").compartments == ["hr", "board"]
    chunk = ctx[1].chunks[doc_for(db_session, ctx, "Z1").id][0]  # the ACL travels with every chunk
    assert (chunk.allowed_roles, chunk.required_clearance, chunk.compartments) == (["hr_manager"], 3, ["hr"])
    assert chunk.text.startswith("[Title Z1 | ")  # title / department / category prefix


def test_unchanged_rows_are_not_reindexed(db_session, ctx):
    sync(db_session, ctx, [row("A1")])
    r = sync(db_session, ctx, [row("A1")])
    assert not r.changed


def test_content_change_and_acl_only_change_both_reindex(db_session, ctx):
    sync(db_session, ctx, [row("A1", clearance=2)])
    r = sync(db_session, ctx, [row("A1", content="New text.", clearance=2)])
    assert len(r.updated) == 1 and "New text." in ctx[1].chunks[doc_for(db_session, ctx, "A1").id][0].text
    r = sync(db_session, ctx, [row("A1", content="New text.", clearance=4)])
    assert len(r.updated) == 1
    assert doc_for(db_session, ctx, "A1").required_clearance == 4
    assert ctx[1].chunks[doc_for(db_session, ctx, "A1").id][0].required_clearance == 4


def test_removed_row_leaves_the_index_and_can_come_back(db_session, ctx):
    sync(db_session, ctx, [row("A1"), row("A2")])
    r = sync(db_session, ctx, [row("A1")])
    d = doc_for(db_session, ctx, "A2")
    assert len(r.removed) == 1 and d.status == "deleted" and d.id not in ctx[1].chunks
    r = sync(db_session, ctx, [row("A1"), row("A2")])
    assert d.status == "active" and d.id in ctx[1].chunks and len(r.updated) == 1


@pytest.mark.parametrize("bad, why", [
    (dict(roles=["no_such_role"]), "unknown role"),
    (dict(clearance=9), "out of range"),
    (dict(clearance="high"), "invalid clearance"),
    (dict(content="  "), "empty content"),
])
def test_invalid_records_are_not_indexed(db_session, ctx, bad, why):
    r = sync(db_session, ctx, [row("OK"), row("BAD", **bad)])
    assert len(r.added) == 1 and len(r.skipped) == 1 and why in r.skipped[0]
    assert doc_for(db_session, ctx, "BAD") is None


def test_record_without_any_role_fails_closed(db_session, ctx):
    ctx[0].permission_mapping = {**ctx[0].permission_mapping, "attach_roles": []}
    r = sync(db_session, ctx, [row("A1")])
    assert not r.added and "no allowed roles" in r.skipped[0]


def test_record_that_becomes_invalid_is_dropped_from_the_index(db_session, ctx):
    sync(db_session, ctx, [row("A1"), row("A2")])
    r = sync(db_session, ctx, [row("A1"), row("A2", roles=["no_such_role"])])
    d = doc_for(db_session, ctx, "A2")
    assert d.status == "deleted" and d.id not in ctx[1].chunks and len(r.removed) == 1 and r.skipped


def test_empty_result_never_wipes_the_index(db_session, ctx):
    sync(db_session, ctx, [row("A1")])
    r = sync(db_session, ctx, [])
    assert r.errors and doc_for(db_session, ctx, "A1").status == "active"
