文档访问权限（RBAC）问答记录
整理日期：2026-10-05
说明：本文件整理了围绕“文档访问策略”的问答，内容来自对代码、数据库和数据目录的实际查看。
      未实际验证的地方已标注“推断”或“预期”。


================================================================
1. 一次投诉流程回答里出现“升级矩阵”，是不是 LLM 编的
================================================================
结论：不是编的。语料里有 customer_support/Escalation_Matrix.xlsx（S03，角色
customer_support;card_ops，密级 1）。用 PDPA 问题复测时，回答内容与该文件
“Data privacy request (PDPA)”一行逐项吻合：
  L1 Customer Support L1 / L2 Data Protection Officer / L3 Legal Counsel /
  3 business days / SupportDesk

为降低模型自行发挥的概率，在两处系统 prompt 加了“严格依据资料”的限制：
  - backend/app/services/llm/openai_compat_llm.py（英文，Anthropic 与 OpenAI 兼容后端使用）
  - backend/app/services/llm/hunyuan_llm.py（中文，Hunyuan 与 DeepSeek 后端使用）
新增规则：
  - 回答中的每个步骤、角色、团队、时限、阈值、联系人、表格或矩阵必须出现在资料里
  - 不得补充、推断、泛化，不得自行构造资料未写的升级层级、SLA、负责人或表格
  - 尽量引用或贴近资料原文
  - 资料只覆盖一部分时，只回答该部分，并明确说明哪些部分未涉及
注意：prompt 只能降低概率，不能保证杜绝。


================================================================
2. 回答里的两种“来源”
================================================================
  来源:[doc_customer_support_sop]、[doc_s03]
      由 LLM 在正文里写出。系统 prompt 要求用 [doc_id] 标注引用，doc_id 是内部编号，不是文件名。
  来源: Complaint_Handling_SOP.docx  Escalation_Matrix.xlsx
      由前端在回答下方显示。后端 doc_names.py 用 doc_id 查库得到真实文件名。

处理：保留内联引用，并在前端替换成真实文件名。
  改动：frontend/src/pages/Query.tsx 新增 inlineFilenames()
  规则：[doc_xxx]、【doc_xxx】、[doc_xxx,第7节] 按该轮 citations 的 filename 替换；
        不在 citations 里的 id 保持原样；文件名里的下划线做转义，避免被当成斜体。
  遗留：模型在末尾写的“来源:”行仍会出现，与下方来源标签重复。如需去掉，
        可在 prompt 里加“不要在末尾单独列出来源，只在正文内联引用”。


================================================================
3. 访问控制的三层规则
================================================================
一份文档必须同时通过角色、密级、分区三道检查，用户才能检索到它。
检查在向量检索阶段（Qdrant 过滤条件）完成，发生在大模型看到内容之前，
大模型不决定谁能看什么。

  层     回答的问题                 属于谁                    用户能否自行改变
  角色   你的职能是否被允许         用户（可多个，含临时）    只能申请，管理员批准后生效
  密级   你能看多敏感的内容         用户本身                  不能
  分区   你是否被划入该敏感领域     用户本身                  不能

3.1 密级（clearance）
  形式：数字 1 到 4。判断：用户密级 >= 文档密级。有高低层级。
    1 Public/Employee（全体员工）  2 Internal  3 Confidential  4 Secret

3.2 角色（role）
  有效角色 = 永久角色 + 尚未到期的临时角色。到期不靠后台任务，每次查询时实时判断。
  临时角色流程：用户提交申请（理由、时长）-> 管理员批准 -> 写入临时授权并记审计日志
  -> 角色缓存立即失效（缓存 TTL 30 秒）-> 到期后不再计入。

3.3 分区（compartment）
  形式：一组标签（hr、aml、finance、credit、security、legal、board）。
  判断：文档无分区则不限；有分区则用户的分区列表至少包含其中一个。
  标签之间没有高低，互相独立。
  分区属于用户本身，申请任何角色都不会增加分区。

3.4 密级与分区的区别
  密级是纵向的高低，分区是横向的隔间。
  只有密级：同级别的人能看同级别所有内容。
  只有分区：同分区的人能看该分区全部内容，分不出更敏感的。
  组合示例：
    Leave_Policy_Admin_Guide   密级 2   hr         密级>=2 且有 hr 分区
    Compensation_Bands         密级 3   hr         密级>=3 且有 hr 分区
    Exec_Compensation          密级 4   hr;board   密级>=4 且有 hr 或 board

3.5 角色与分区的区别（各自区分哪些文件）
  角色：区分不同部门或岗位的文档，如客服投诉流程、卡业务额度规则、财务发票审批。
  分区：在同一岗位内再隔离最敏感的一类。现有分区文档（按 documents_index.csv 统计）：
    hr 4 份（年休假、薪酬、绩效、入职清单，限 hr_manager）
    aml 5 份（限 compliance_officer）
    finance 3 份，另有 1 份项目文档
    credit 2 份、security 1 份、legal 1 份
    board：高管类，其中一份要求 hr;board
  大多数文档没有分区（31 份无分区），例如员工手册、远程办公政策、投诉流程、
  升级矩阵、发票审批流程。


================================================================
4. 为什么 frank、alice 申请了 HR 角色仍然查不到年休假
================================================================
答案在 hr/Leave_Policy_Admin_Guide.docx（H01），manifest 登记的要求：
  角色 hr_manager，密级 >= 2，分区 hr。

  账号    密级  分区     角色结果       密级结果     分区结果
  frank   1     无       有（临时）     不满足       不满足
  alice   2     aml      有（临时）     满足         不满足（aml 不含 hr）
  henry   3     hr       有（永久）     满足         满足

结论：这是按设计工作，不是 bug。临时角色只授予角色，不会带密级和分区。
alice 一开始被批的是 finance_analyst，不是 hr_manager；2026-10-05 再查时她已有 hr_manager。

可选改进（未做）：让角色自带它隐含的分区和密级，随临时角色到期自动失效。


================================================================
5. 演示脚本（预期结果，按策略推导，演示前请先彩排）
================================================================
  场景   账号    问题                          拦在哪层
  A 角色 alice   信用卡额度调整规则是什么？   角色：alice 没有 card_ops
  B 密级 frank   发票审批流程是什么？         密级：申请到 finance_analyst 后角色满足，但密级 1 < 2
  B 对照 alice   同上                          无，有 finance_analyst 且密级 2，应正常回答
  C 分区 alice   工作 3 年有几天年休假？      分区：有 hr_manager、密级 2，但分区是 aml
  C 对照 henry   同上                          无，应正常回答并引用 Leave_Policy_Admin_Guide.docx
  D 无分区 alice 远程办公政策是什么？         无，这份 HR 文档不分区

被拒时页面显示“无权限访问该内容”，系统有意不说明是哪一层不足，也不透露文档名。
完整讲解稿已整理在 claude.ai 文档《文档访问策略与演示指南》。

演示账号状态（2026-10-05 数据库快照）：
  frank  密级 1  分区 无          角色 employee、customer_support，临时 hr_manager（约 2026-10-06 01:37 到期）
  alice  密级 2  分区 aml         角色 employee、compliance_officer，临时 finance_analyst
                                  （约 2026-10-06 01:48 到期）、临时 hr_manager
  henry  密级 3  分区 hr          角色 employee、hr_manager
  admin  密级 4  分区 aml、finance 角色 platform_admin、employee
临时角色有效期均为 1 天，演示前请检查是否过期。


================================================================
6. 权限数据从文档放入目录到 Qdrant 的流程
================================================================
数据来源：
  data/manifest.json         权限的权威来源，程序读取它
  data/documents_index.csv   同一信息的可读版本，代码里没有读它，改它无效
  Postgres documents 表      运行时事实来源（权限、状态、内容哈希）
  Qdrant chunk payload       每个文本块带一份文档权限的副本，用于检索过滤

链路：manifest.json -> documents 表 -> 解析、切块、向量化 -> Qdrant（权限复制到每个 chunk）
      -> 提问时按有效角色、密级、分区下推过滤 -> 只返回有权限的块 -> 大模型生成

同步（backend/app/services/library_sync.py）：后台定时运行，也可手动
POST /api/admin/library/sync。
  - 新文件有 manifest 条目：按条目权限注册并建立索引
  - 新文件无条目但是已有文档的新版本（如 X -v 2.0.docx）：继承旧版本权限，旧版本归档
  - 新文件两者都不是：不建立索引，只在报告里提示（失败即拒绝）
  - 文件内容变化（哈希不同）：删除旧 chunk 后重建
  - 文件被删除：标记 deleted 并清除向量；若是最新版则恢复上一版本
  - 忽略最近 2 秒内修改的文件；目录为空时不会清空索引

推断（未验证）：权限只在“新增文档”时从 manifest 读取。只改 manifest 里已索引文档的权限，
不会自动更新到 documents 表和 Qdrant。


================================================================
7. 文档头部权限：以 manifest 为准，新文件读取头部并写回 manifest（已实现，未做完整流程验证）
================================================================
决定：manifest.json 保持权威。
  - Leave_Policy_Admin_Guide 密级以 manifest 为准，保持 2 级（Internal）。
    文档头部写的是 Confidential，两者不一致，但头部对已有条目不起作用，也不修改源文档。
    若以后想消除不一致，需要人工把文档头部改成 Internal。

新文件的处理顺序（backend/app/services/library_sync.py、doc_header.py）：
  1. manifest 有条目：以 manifest 为准，不读头部。
  2. 无条目但是已有文档的新版本：继承旧版本权限。
  3. 都不是：读取文件开头的权限块，生成条目并追加到 manifest.json（原子替换，已有条目不改），
     再按该条目建立索引。
  4. 头部缺失、不完整或无法识别：不入库，输出 ERROR 报警（同一文件只记录一次，同步报告每轮都列出）。

头部必填两项：Classification（Public/Internal/Confidential/Secret 对应 1 到 4）、
Compartments（没有写 none）。
Allowed Roles 可选：写了就用它（必须是 roles 表里已有的角色）；没写则按部门补默认角色（见下）。
可选：Document ID、Department、Version。
写 manifest 失败（如目录只读）同样不入库。
docker-compose.yml 里 data 目录由只读改为可写，需 docker compose up -d backend 重建后端容器后生效。

Allowed Roles 没写时的默认规则（backend/app/services/doc_header.py 的 default_roles）：
  - 用头部的 Department 和文件所在的顶层文件夹，查下表。
  - 两者都能映射且结果不一致（如头部写 HR、文件放在 public 下）：报警，不入库，要求显式写 Allowed Roles。
  - 两者都映射不出来：报警，不入库。
  - 默认取各部门最窄的“所属角色”，不用 employee（Public 除外），宁可少开放，不多开放。
    需要多个角色（如升级矩阵给 customer_support 和 card_ops）时，请显式写 Allowed Roles。
  - Projects 目录没有默认：项目文档属于具体某个项目角色（proj_merger 等），无法从部门推出，必须显式写。

  部门（头部 Department / 文件夹）        默认角色
  Public / public                          employee
  Compliance / compliance                  compliance_officer
  Risk & Credit / risk_credit              risk_analyst
  Card Operations / card_ops               card_ops
  Customer Support / customer_support      customer_support
  Finance / finance                        finance_analyst
  HR / hr                                  hr_manager
  Marketing / marketing                    marketing_manager
  Sales & Partnerships / sales_partnerships account_manager
  Engineering & Security / engineering_security  engineer、security_engineer
  Legal / legal                            legal_counsel
  Executive / executive                    exec
  Projects / projects                      （无默认）
  说明：映射表按 manifest.json 里各部门的用法整理。头部 Department 不在表里（如 People and Culture）
  时，由文件夹决定。

测试：backend/tests/test_doc_header.py（头部解析与默认角色，15 个用例通过）。完整同步流程未在真实库上跑过。


================================================================
8. 离职、转岗时密级和分区如何更新（现状与缺口）
================================================================
现状：
  - 用户、密级、分区由 backend/seed_data.py 的 USERS 列表写入，是演示种子数据。
  - 系统没有任何接口能修改 users.clearance 和 users.compartments，管理员也不行。
  - users 表只有 username、email、department、clearance、compartments，没有在职/停用字段，
    登录和查询也不检查在职状态。
  - 管理员能通过 /roles/revoke 撤销角色；临时角色到期自动失效。

隐患：撤销全部角色后，密级和分区仍保留；之后再被授予某个角色，旧分区会立刻重新生效。
      离职账号仍能登录。

最小补法（未做）：
  1. users 加 status 字段（active/disabled），登录和查询时检查，离职置为 disabled。
  2. 加管理员专用接口修改密级和分区，每次变更写审计日志并清缓存。普通用户仍不能改，
     符合“用户只能申请角色，不能改密级、不能跨越分区”的要求。
  3. 转岗时一并处理：撤销旧岗位永久角色，再更新分区和密级。
生产做法：以 HR 系统或 IdP 为源头，用映射规则（如 部门=HR -> 分区 hr）生成属性，
          定时或事件触发同步，变更写审计日志并清缓存。演示阶段可放入路线图。


================================================================
9. 是否引入 Casbin 等策略引擎
================================================================
现状：属性来自本地数据库（user_roles、users），backend/app/services/rbac.py 在查询时计算
有效角色并用 Redis 缓存 30 秒；规则写在检索层，三项文档属性作为 Qdrant payload，
由 qdrant_store.py 转成过滤条件在向量检索时一次性下推。

不建议用 Casbin 替换整个检索过滤：Casbin 要逐文档判断，若改成先检索 top-k 再逐个判断，
会损失召回（被拒文档占用名额），并增加延迟与成本。

分层建议（后续 feature）：
  - 检索过滤：保留 Qdrant 下推
  - 有效属性计算（角色、临时授权、到期、项目成员）：可交给策略引擎
  - 管理操作鉴权（谁能审批、授权、撤销）：适合 Casbin
  - 引擎选择：Casbin 轻量、嵌入应用；OPA 表达力强但集成复杂，本项目收益有限

对评分的帮助（评分维度见 requirement/demo_script.md 第 7 节：AI 创新 30、技术卓越 20、
体验与演示 25、商业价值 25）：几乎没有。页面上的拒绝、放行、审计行为不变，评委感受不到差别，
且会改动已稳定的主链路。
结论：现在不做，作为路线图写一条“策略引擎化：把有效属性计算和管理接口鉴权外置为可版本化策略，
检索仍保持预过滤”。答辩时可以说明：需要把权限条件下推到向量检索，逐文档判断会损失召回。
更高优先级的是 requirement/feedback.txt 提到的 CodeBuddy/WorkBuddy 使用证明。


================================================================
10. 本次实际改动的文件
================================================================
  backend/app/services/llm/openai_compat_llm.py   系统 prompt 加严格依据资料的限制
  backend/app/services/llm/hunyuan_llm.py         同上（中文）
  frontend/src/pages/Query.tsx                    内联 [doc_id] 引用替换为文件名
未改动任何用户、角色、密级、分区数据。未改动 manifest.json 和 documents_index.csv。


================================================================
11. 审计统计的 MCP 服务（WorkBuddy 对接）
================================================================
11.1 定位
  - 通过 MCP 把后台管理的审计与角色数据以只读工具开放给智能体（WorkBuddy）。
    管理员在 WorkBuddy 里用自然语言提问，由智能体自己决定调用哪些工具并组合出答案。
  - 统计对象是审计日志和后台数据，不是文档内容；不是自然语言转 SQL。
    原因：WorkBuddy 没有可供我们调用的聊天接口，但支持连接外部 MCP，所以方向是 WorkBuddy 调用我们
    （设计说明见 backend/app/mcp_server.py 文件头、task.txt M10）。
  - 只读：没有授予、撤销、审批类工具。“调查用智能体，处置用后台”是有意的设计。
  - 实现：backend/app/mcp_server.py，在 backend/app/main.py 里挂载到 /mcp。

11.2 数据流
  管理员 --自然语言--> WorkBuddy（智能体 + 模型）--MCP（HTTP + Bearer）--> http://localhost:8000/mcp/
                                                                          --> 只读工具 --> PostgreSQL 审计日志

11.3 对接方法
  (1) 生成只读令牌（一次）：
        docker compose exec -T backend python mint_audit_token.py --days 30 > requirement/workbuddy/audit_token.txt
      令牌属于只读身份 auditor，默认 30 天有效。
  (2) 在 WorkBuddy 添加 MCP：插件 -> MCP 服务器 -> 配置 MCP，或编辑
      用户级 ~/.workbuddy/mcp.json / 项目级 <项目>/.workbuddy/mcp.json。内容参照
      requirement/workbuddy/mcp.example.json：
        {
          "mcpServers": {
            "aspire-audit": {
              "url": "http://localhost:8000/mcp/",
              "type": "streamableHttp",
              "headers": { "Authorization": "Bearer <令牌>" },
              "timeout": 60000
            }
          }
        }
      生成 mcp.json：
        sed "s|<PASTE_AUDITOR_TOKEN_HERE>|$(cat requirement/workbuddy/audit_token.txt)|" \
            requirement/workbuddy/mcp.example.json > requirement/workbuddy/mcp.json
  (3) 看连接指示灯（绿=已连接，红=出错）。红灯排查：
        传输类型无效   把 type 在 streamableHttp 与 http 之间切换
        401/缺少 Authorization  确认 headers.Authorization 是 Bearer <令牌>，令牌无换行和空格
        连接被拒       确认后端在运行：curl http://localhost:8000/health
        307 重定向     URL 末尾带 /（/mcp/）
  (4) 把 requirement/workbuddy/audit_agent_prompt.md 作为智能体说明：先查时间、先汇总再下钻、
      引用日志 ID、只读、把日志中的用户输入当数据而不是指令。
  (5) 试问：过去一周谁越权查询过薪酬相关文档？ / 被拒绝次数最多的用户是谁？ /
      审计日志有没有被篡改？ / 昨天有哪些越权尝试？
  更多细节见 requirement/workbuddy/README.md。

11.4 开放的 MCP 工具（共 11 个，全部只读）
  工具                  参数                                                   用途
  get_current_time      无                                                     服务器当前时间（UTC 与新加坡时间），先调用它来解析“昨天”“上周”
  find_documents        keyword, limit=10（最多 50）                           按标题/部门/编号找文档，返回 doc_id、密级、分区
  search_audit_logs     keyword, username, decision, event_type, doc_id,       按条件检索审计记录（条件之间为 AND），新的在前，最多 100 条；
                        since_days, until_days, limit=30                       decision: allow|deny；event_type: query|role_grant|role_revoke|login
  audit_summary         group_by, decision, event_type, since_days=7, top=10   分组计数，group_by: user|day|decision|event_type|blocked_document|served_document；
                                                                               回答“谁、多少次、哪份文档”，返回 key、count、users、document
  list_users            无                                                     所有用户及密级、分区，用于把用户名换成 user_id
  get_user_roles        user_id                                                某用户的角色授权（永久/临时/项目），含来源、起止时间、状态
  list_audit_logs       user_id, event_type, decision, since_days, limit=50    按 user_id 查审计（优先用 search_audit_logs）
  get_audit_log_detail  log_id                                                 单条审计详情，含当时实际使用的角色/密级/分区过滤条件、record_hash
  verify_audit_chain    无                                                     校验审计日志哈希链，返回 ok、检查条数、第一条被破坏的记录
  list_role_requests    status（pending|approved|rejected）                    角色申请列表
  get_dashboard_stats   days=14                                                总查询数、允许/拒绝数与拒绝率、最近违规、按日查询量、数据源同步状态

11.5 身份验证
  - 11 个工具每一个都在入口处调用 _authorize_admin，依次检查：
      1. 必须是 HTTP 调用；
      2. 必须带 Authorization: Bearer <token>，否则返回“缺少 Authorization”；
      3. 令牌必须是系统签发的有效 JWT（签名与有效期），伪造或过期被拒绝；
      4. 令牌对应用户必须存在，且当前有效角色包含 platform_admin 或 auditor。
         角色每次调用实时计算，撤销角色后旧令牌立即失效。
  - 令牌权限很小：auditor 令牌只能调用这 11 个只读工具，不能调用 REST 管理接口（要求 platform_admin）。
  - 令牌等同密码：audit_token.txt 和 mcp.json 已在 .gitignore，不要提交，不要贴到聊天里。
  - 作废方式：去掉 auditor 用户的角色（立即生效），或轮换 JWT_SECRET（所有人需重新登录）。
    没有只作废某一个已签发令牌的黑名单。
  - 后台管理页面的登录是另一套：走 /api/auth/login 用账号密码换取 8 小时令牌，与 MCP 共用同一套 JWT 机制，
    但有效期和角色范围不同。

11.6 安全与数据流提示
  - 审计记录里含用户输入的问题原文，会经 WorkBuddy 送到它背后的模型。演示数据为虚构；
    用于真实数据前，需要评估这条数据流是否可接受。
  - 用户输入会被写进审计日志再被智能体读到，存在提示词注入风险。工具只读，最坏情况是答案被带偏，
    不会造成写操作；服务说明和智能体指令都要求把日志文本当数据。是否遵守取决于 WorkBuddy 的智能体。
  - 被拒时记录的“最相关受限文档”只存在于审计日志和 MCP 输出，从不出现在给用户的响应中（有测试覆盖）。

11.7 验证情况
  - WorkBuddy 里的实际测试：已由用户确认通过。
  - 服务端验证脚本：docker compose exec -T backend python verify_workbuddy_mcp.py
    （官方 MCP 客户端，同样的 URL 与请求头）。2026-10-05 运行：除 1 项外全部通过——
    连接、11 个工具齐全、无写工具、薪酬文档越权查询、按日拒绝统计、审计链校验（92 条）、被拒内容不泄露。
    失败的 1 项是“bob 是被拒次数最多的用户”：实际 alice 11、frank 9、bob 5。
    判断是当天用 alice、frank 反复测试年休假产生了大量真实拒绝记录，盖过了种子数据，
    属于脚本预期值过时，不是功能错误（未逐条核对）。
    演示前想让脚本和 README 预期一致，可 ./start.sh --reset 重置演示数据（会清掉当天记录和临时角色授权）。

11.8 其他开放的 REST 接口（后台与业务，供对照）
  认证与业务：
    POST /api/auth/login、GET /api/auth/me
    POST /api/query/text、/api/query/text/stream、/api/query/image
    GET /api/chat/sessions、GET /api/chat/sessions/{id}、DELETE /api/chat/sessions/{id}
    GET /api/roles、POST /api/role-requests、GET /api/role-requests/me
  后台管理（要求 platform_admin）：
    GET /api/admin/roles、GET /api/admin/users、GET /api/admin/users/{id}/roles
    POST /api/admin/roles/grant、/api/admin/roles/revoke
    POST /api/admin/projects/join、/api/admin/projects/leave
    GET /api/admin/role-requests、POST /api/admin/role-requests/{id}/approve、/reject
    GET /api/admin/audit/logs、/logs/{id}、/verify、/export
    GET /api/admin/dashboard/stats
    POST /api/admin/library/sync（立即同步文档库）
  注：系统没有任何接口能修改用户的密级和分区（见第 8 节）。
