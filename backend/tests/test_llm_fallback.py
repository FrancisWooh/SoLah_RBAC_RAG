"""If the LLM call fails, the query still succeeds with the extractive answer."""

from app.services import query_service
from app.services.vectorstore.base import PermissionContext


class _BrokenLLM:
    def generate_answer(self, question, chunks):
        raise RuntimeError("llm down")


def test_llm_failure_degrades_to_extractive_answer(monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: _BrokenLLM())
    permission = PermissionContext(roles={"employee", "compliance_officer"}, clearance=2, compartments={"aml"})

    result = query_service.answer_text_query("KYC/AML 审核标准是什么？", permission)

    assert result.decision == "allow"
    assert result.answer.startswith(query_service.LLM_UNAVAILABLE_NOTE)
    assert "doc_kyc_aml_policy" in {c.doc_id for c in result.citations}
