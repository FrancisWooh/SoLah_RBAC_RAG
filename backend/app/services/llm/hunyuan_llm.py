"""Tencent Hunyuan chat backend (the primary LLM per readme.txt). NOT
exercised against a real Tencent Cloud account here — no
TENCENT_SECRET_ID/KEY were available. Class/field names (ChatCompletionsRequest,
Message.Role/Content, Choices[0].Message.Content) are confirmed against the
installed tencentcloud-sdk-python-hunyuan package's own docstrings, but the
live call itself is untested. Smoke-test before relying on it.
"""

from app.core.config import settings
from app.services.vectorstore.base import ScoredChunk

SYSTEM_PROMPT = (
    "你是企业内部知识助手。只能依据下面提供的资料回答问题，"
    "资料之外的内容不要编造。回答中的每个步骤、角色、团队、时限、阈值、联系人、表格或矩阵"
    "都必须出现在资料中；不得自行补充、推断或泛化，不得自行构造资料未写明的升级层级、SLA、负责人或表格，"
    "尽量引用或贴近资料原文。资料只覆盖问题的一部分时，只回答该部分，并明确说明哪些部分资料未涉及，"
    "不要用通用做法补全。如果不同资料对同一事项给出了不一致的信息（数字、期限、时限、额度或规则不同），"
    "不得择一采用、取折中值或悄悄合并，必须明确指出资料之间存在冲突，逐一列出各版本及其来源【doc_id】，"
    "除非某份资料自己声明取代另一份，否则不要自行判定哪个正确；表述不同但含义一致的资料不算冲突。回答末尾用【doc_id】标注引用的资料来源。"
    "如果资料不足以回答问题，请明确说明。"
)


class HunyuanLLM:
    def __init__(self):
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.hunyuan.v20230901 import hunyuan_client

        cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "hunyuan.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = hunyuan_client.HunyuanClient(cred, "ap-singapore", client_profile)

    def generate_answer(self, question: str, context_chunks: list[ScoredChunk]) -> str:
        from tencentcloud.hunyuan.v20230901 import models

        context_text = "\n".join(f"【{c.doc_id}】{c.text}" for c in context_chunks) or "（无检索到的资料）"

        system_msg = models.Message()
        system_msg.Role = "system"
        system_msg.Content = SYSTEM_PROMPT

        user_msg = models.Message()
        user_msg.Role = "user"
        user_msg.Content = f"资料：\n{context_text}\n\n问题：{question}"

        req = models.ChatCompletionsRequest()
        req.Model = settings.hunyuan_model
        req.Messages = [system_msg, user_msg]
        req.Stream = False

        resp = self._client.ChatCompletions(req)
        return resp.Choices[0].Message.Content
