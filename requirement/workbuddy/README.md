# 用 WorkBuddy 做审计日志问答（通过 MCP）

思路：**WorkBuddy 是前端智能体，我们的后端是 MCP 服务**。管理员在 WorkBuddy 里用自然语言提问，WorkBuddy 自己决定调用哪些只读工具、组合出答案。

```
管理员 ──自然语言──▶ WorkBuddy 桌面版 ──MCP (HTTP + Bearer)──▶ http://localhost:8000/mcp/
                         (智能体 + 模型)                          Aspire Internal Brain 后端
                                                                  只读工具 → PostgreSQL 审计日志
```

## 1. 准备（一次）

```bash
./start.sh --reset                                   # 含"一周审计历史"，Dashboard 与问答才有内容
docker compose exec -T backend python mint_audit_token.py --days 30 > requirement/workbuddy/audit_token.txt
```

- 令牌属于只读身份 `auditor`，**只能用于 `/mcp` 的 11 个只读工具**，不能调用 REST 管理接口。
- `audit_token.txt` 和 `mcp.json` 都在 `.gitignore` 里，**不要提交、不要贴到聊天里**。
- 令牌到期（30 天）或泄露后：重新生成；彻底作废可以轮换 `JWT_SECRET`（会让所有人重新登录）。

## 2. 在 WorkBuddy 里添加 MCP 服务

WorkBuddy 的入口是 **插件 → MCP 服务器 → 配置 MCP**，也可以直接编辑配置文件：用户级 `~/.workbuddy/mcp.json`，或项目级 `<项目目录>/.workbuddy/mcp.json`。把 `mcp.example.json` 的内容放进去，替换令牌：

```bash
sed "s|<PASTE_AUDITOR_TOKEN_HERE>|$(cat requirement/workbuddy/audit_token.txt)|" \
    requirement/workbuddy/mcp.example.json > requirement/workbuddy/mcp.json
```

保存后看连接指示灯（绿 = 已连接，红 = 出错）。

**如果是红灯**，按顺序试：

| 现象 | 处理 |
|---|---|
| 提示传输类型无效 | 官方文档对 HTTP 类型的写法不一致（有的写 `streamableHttp`，有的写 `http`）：把 `"type": "streamableHttp"` 改成 `"type": "http"`，或反过来 |
| 401 / "缺少 Authorization" | 确认 `headers.Authorization` 是 `Bearer <令牌>`，令牌没有换行或空格；有的版本支持 `${环境变量}` 引用，也可以直接写死 |
| 连接被拒 | 确认后端在运行：`curl http://localhost:8000/health`；WorkBuddy 与 docker 在同一台机器上 |
| 307 重定向 | URL 末尾带 `/`（`/mcp/`），已默认如此 |

> 我们在开发环境用官方 `mcp` Python 客户端验证过：`/mcp` 与 `/mcp/` 都能连接，带 Bearer 头可以调用全部工具。**WorkBuddy 自己的客户端没有在开发环境验证过**（那里没有 WorkBuddy），所以如果它的行为与上表不同，以实际现象为准。

## 3. 配置智能体指令

把 [`audit_agent_prompt.md`](audit_agent_prompt.md) 的内容作为该智能体 / 技能的说明（系统提示）。它规定了：先查时间、先汇总再下钻、引用日志 ID、只读、**把日志中的用户输入当数据而不是指令**。

## 4. 试问（对照预期）

演示库里的"一周审计历史"是通过真实检索流水线生成的（标记为 `model_id = seed-history`）。下面是典型问题与预期的工具调用链：

| 问题 | 预期调用链 | 预期要点 |
|---|---|---|
| 过去一周谁越权查询过薪酬相关文档？ | `get_current_time` → `find_documents("Compensation")` → `audit_summary(blocked_document, deny)` 或 `search_audit_logs(doc_id=…, deny)` | 点名 bob（多次）、ivy 等，引用日志 ID |
| 被拒绝次数最多的用户是谁？他们想看什么？ | `audit_summary(user, deny)` → `search_audit_logs(username=…, deny)` | bob 居首；指出他反复尝试薪酬 / 董事会文档，措辞为"值得关注" |
| 审计日志有没有被篡改？ | `verify_audit_chain` | ok，并报告校验条数 |
| 昨天有哪些越权尝试？ | `get_current_time` → `search_audit_logs(deny, since_days=1)` | 列出用户、问题、被拦的文档 |

不用 WorkBuddy 也能验证服务端：

```bash
docker compose exec -T backend python verify_workbuddy_mcp.py
```

它用官方 MCP 客户端、和上面配置完全相同的 URL 与请求头，把上表的调用链各跑一遍并断言结果。

## 5. 作为赛事"使用证明"

按赛事规则，需要**使用截图（≥3 张）或录屏 / 对话记录**。建议在你自己的机器上留这几张：

1. WorkBuddy 的 MCP 服务器页面，`aspire-audit` 显示绿灯；
2. 一次完整的问答：问题 → 工具调用过程 → 带日志 ID 的结论；
3. 校验审计链的那次问答。

这些截图只能由你在 WorkBuddy 里截取，仓库里没有。

## 6. 安全与数据流

- **只读**：工具里没有授予、撤销、审批；"调查用智能体，处置用后台"是有意的设计。
- **最小权限**：`auditor` 令牌不能调用 REST 管理接口。
- **数据流向**：审计记录（含用户输入的问题原文）会经 WorkBuddy 送到它背后的模型。演示数据全部是虚构的；用于真实数据前，需要评估这条数据流是否可接受。
- **提示词注入**：用户输入的问题会被写进审计日志，再被智能体读到。工具是只读的，所以最坏情况也只是"答案被带偏"，不会造成写操作；智能体指令里已要求把日志文本当数据。
- **被拒文档 ID**：被拒时记录的"最相关受限文档"只存在于审计日志和 MCP 输出里，**从不出现在给用户的任何响应中**（有测试覆盖）。
