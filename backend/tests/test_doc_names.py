"""Display names for citations: files keep their real file name, records of a registered
department database show data source, record code and title, and each citation says which kind it is."""

from app.models.data_source import DataSource
from app.models.document import Document
from app.services.doc_names import cite


def _doc(doc_id, source_ref, source_type):
    return Document(id=doc_id, source_type=source_type, source_ref=source_ref, status="active",
                    allowed_roles=["employee"], required_clearance=1, compartments=[], version="v1.0")


def test_database_record_is_labelled_with_source_code_and_title(db_session):
    db_session.add(DataSource(name="Test Dept Database", type="postgresql"))
    db_session.add(_doc("db_t_dept_a1", "db://test_dept_database/knowledge_records/td_l01/annual_leave_entitlement", "db"))
    db_session.flush()

    [c] = cite(db_session, [{"doc_id": "db_t_dept_a1", "snippet": "x"}])

    assert c["filename"] == "Test Dept Database · TD-L01 · Annual Leave Entitlement"
    assert c["source_type"] == "db"


def test_file_keeps_its_file_name_and_is_marked_as_file(db_session):
    db_session.add(_doc("doc_t_leave", "/company_share/hr/Leave_Policy_Admin_Guide -v 2.0.docx", "nas"))
    db_session.flush()

    [c] = cite(db_session, [{"doc_id": "doc_t_leave", "snippet": "x"}])

    assert c["filename"] == "Leave_Policy_Admin_Guide -v 2.0.docx"
    assert c["source_type"] == "file"


def test_unknown_source_name_falls_back_to_the_key(db_session):
    db_session.add(_doc("db_t_x", "db://some_unregistered_db/knowledge_records/ab_c1/long_title_here", "db"))
    db_session.flush()

    [c] = cite(db_session, [{"doc_id": "db_t_x", "snippet": "x"}])

    assert c["filename"] == "Some Unregistered Db · AB-C1 · Long Title Here"


def test_unknown_doc_id_gets_no_name(db_session):
    [c] = cite(db_session, [{"doc_id": "doc_nope", "snippet": "x"}])
    assert c["filename"] is None and c["source_type"] is None
