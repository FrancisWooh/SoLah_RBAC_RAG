RBAC-RAG 企业知识系统 "Aspire Internal Brain"
Tencent Cloud AI CAN DO IT Hackathon Singapore 2026 — FinTech Track (Aspire)
提交截止：2026-10-16

本文件整合了 requirement/Technical Proposal for RBAC AIG.docx 的原始需求，
以及 requirement/feedback.txt 中对赛事规则、评分权重、时间窗口的分析后得出的
范围调整，作为实际开发时的功能/任务清单。原始完整设计见 docx，本文件是
"做什么、先做什么、不做什么"的执行版。

====================================================================
0. 项目一句话描述
====================================================================
员工用自然语言（文字/图片/语音）查询企业内部知识，系统基于 RBAC 严格过滤
检索结果，确保用户只能看到自己被授权访问的内容，并对查询、权限变更、
数据同步事件进行完整审计。

====================================================================
1. 强制性赛事要求（必须满足，否则不进入评分）
====================================================================
[ ] 项目必须基于腾讯 CodeBuddy 和/或 WorkBuddy 构建
[ ] 需提供使用证明：开发过程截图（3张以上）或录屏/开发对话记录
    （通过 Product Sharing 组件提交）
[ ] 优先使用腾讯云 AI 技术栈作为主路径（混元 LLM / 混元 Embedding /
    腾讯云 VectorDB / 腾讯云 OCR-ASR / COS），本地开源方案（Qdrant /
    DeepSeek / PaddleOCR / Whisper）仅作降级备选，不作为默认实现
[ ] 10-16 前完成提交；预留时间准备 8 分钟演讲 + 5 分钟 Q&A 的 Demo Day 展示

====================================================================
2. 范围裁剪原则（两周工期，必须遵守）
====================================================================
- Phase 1 必须 100% 完整可运行、零 bug、docker-compose 一键启动
- Phase 2 中与"可见演示效果"无关的后端基础设施（CDC、Kafka、NAS 文件监听、
  连接器注册表）降级为"架构图/PPT 中讲解，不在代码中真实实现"
- Phase 3 中只挑 1 个"演示亮点"真正实现：推荐图片 OCR 多模态查询
  （视觉冲击力最强，且对应官方评分"AI 创新"维度）
- 蓝绿索引切换、多版本并存、术语映射层等如时间允许再做，不纳入必须交付范围

====================================================================
3. 功能需求清单（按优先级分组）
====================================================================

--- P0 / Phase 1（MVP，必须完整实现）---
[ ] 用户登录（模拟 SSO），JWT 中携带 user_id、role、clearance、compartments
[ ] GET /api/auth/me 返回当前用户及动态计算出的"有效角色"
    （有效角色 = 永久角色 + 未过期的临时角色）
[ ] 文字查询接口：POST /api/query/text
[ ] 向量检索前置权限过滤：allowed_roles 命中 AND required_clearance <=
    user.clearance AND compartments 为 user.compartments 子集
[ ] LLM 基于过滤后的检索片段生成回答，返回结果附来源文档引用
[ ] 向量数据库接入（优先腾讯云 VectorDB，payload 过滤；本地可用 Qdrant 降级）
[ ] 审计日志：每次查询（含 allow/deny）写入 audit_logs，仅追加不可改
[ ] 管理后台 - 角色管理页：用户角色列表、手动授予/撤销临时角色
[ ] 管理后台 - 审计日志页：列表、按 user_id/event_type/decision/时间 筛选、详情
[ ] 预置模拟数据脚本 seed_data.py（用户、角色、文档、权限关系）
[ ] docker-compose.yml 一键启动全部服务

--- P1 / Phase 2（时间允许再做，优先级低于 P0）---
[ ] 临时角色申请-审批流程：role_requests 提交 -> 审批人批准/拒绝 -> 写入
    user_roles 并设置有效期
[ ] 项目自动授予角色：加入 project_members 触发自动写入临时角色，
    project_end_at 到期自动失效
[ ] 管理后台 - Dashboard 页：查询量、拒绝率、越权告警、同步健康度统计
[ ] 数据源管理页（仅展示配置与状态，真实 CDC/NAS 同步可用"模拟任务"代替）
[ ] GET /api/admin/audit/export 导出 CSV/JSON

--- P2 / Phase 3（只精选 1-2 项，优先图片 OCR）---
[ ] 图片查询：POST /api/query/image，OCR/VLM 转文本后走标准查询流程
    （优先腾讯云 OCR；本地降级 PaddleOCR）
[ ] 语音查询：POST /api/query/audio，ASR 转文本后走标准查询流程（如时间允许）
[ ] 审计日志自然语言问答（"AI 创新"加分项）：管理员可直接用自然语言在
    Dashboard 中查询审计日志，例如"过去一周谁越权查询过 AML 政策？"，
    由 LLM 将问题转换为对 audit_logs 的结构化查询并生成摘要回答
[ ] 检索内容注入防护：将向量检索出的文档内容显式标记为"不可信数据"，
    防止 prompt injection 影响权限判断逻辑（呼应官方"security logging"要求）

--- 不纳入本次交付（已从原方案中砍掉，仅保留在架构文档中）---
- PostgreSQL/Oracle CDC（Debezium + Kafka）真实接入
- NAS 目录 watchdog 文件监听真实接入
- 蓝绿索引切换、多版本共存治理
- 术语规范化映射层（如有余力可做成简单同义词表，不做复杂消歧 agent）

====================================================================
4. 技术栈（已按反馈调整优先级，腾讯云优先）
====================================================================
后端：Python 3.11+ / FastAPI / SQLAlchemy / Pydantic
前端：React + TypeScript + Ant Design
元数据库：PostgreSQL（用户、角色、审计日志、文档元数据）
向量数据库：腾讯云 VectorDB（主） / Qdrant 本地（降级备选）
缓存：Redis（会话、权限缓存，TTL 30 秒，变更时主动失效）
LLM：腾讯混元 TurboS API（主） / DeepSeek-R1-Distill-Qwen-14B 本地（降级）
Embedding：hunyuan-embedding 1024维（主） / BGE-M3（降级）
OCR/ASR：腾讯云 OCR / ASR（主） / PaddleOCR / Whisper（降级）
对象存储：腾讯云 COS（原始图片/音频）
开发工具：CodeBuddy（主力编码/review/test），WorkBuddy（承担部分 agent
          功能，如审计问答 agent，而非仅作合规留痕）
部署：Docker Compose 一键启动

====================================================================
5. 数据模型（沿用原设计，详见 docx 第3节）
====================================================================
users / roles / user_roles / project_members / role_requests /
documents / audit_logs / data_sources
（审计日志建议追加实现：哈希链字段，使日志真正"防篡改可验证"，
  而不仅是"仅追加"的应用层约定）

====================================================================
6. API 端点清单（P0 范围内优先实现，P1/P2 见上方分组）
====================================================================
认证：POST /api/auth/login, GET /api/auth/me
查询：POST /api/query/text, POST /api/query/image, POST /api/query/audio
角色管理：GET /api/admin/roles, GET /api/admin/users/{id}/roles,
          POST /api/admin/roles/grant, POST /api/admin/roles/revoke,
          GET /api/admin/role-requests,
          POST /api/admin/role-requests/{id}/approve,
          POST /api/admin/role-requests/{id}/reject
审计：GET /api/admin/audit/logs, GET /api/admin/audit/logs/{id},
      GET /api/admin/audit/export
数据源：GET/POST /api/admin/datasources,
        POST /api/admin/datasources/{id}/sync,
        GET /api/admin/datasources/{id}/status
Dashboard：GET /api/admin/dashboard/stats

====================================================================
7. 前端页面清单
====================================================================
用户前台：/login, /app/query
管理后台：/admin, /admin/roles, /admin/audit, /admin/datasources,
          /admin/dashboard

====================================================================
8. Demo 场景（已替换为 Aspire 业务语境，对应"商业价值"评分维度）
====================================================================
场景一（正常查询）：
  compliance_officer 登录 -> 查询"KYC/AML 审核标准" -> 成功返回并显示来源

场景二（越权拒绝）：
  compliance_officer 查询"客服投诉处理 SOP" -> 被拒绝（无客服权限）
  -> 审计日志记录 deny

场景三（临时角色）：
  管理员将 bob 加入 proj_card_program -> 自动授予 card_ops 临时角色
  -> bob 查询"企业卡额度调整规则"成功
  -> 管理员将 bob 移出项目 -> bob 再次查询被拒绝

场景四（多模态输入，P2 亮点）：
  用户上传手写笔记照片"CASA账户的KYC要求" -> OCR识别 -> 检索 -> 回答

场景五（审计追溯 + 自然语言问答，AI 创新加分项）：
  管理员在 Dashboard 中用自然语言提问"过去一周谁越权查询过 AML 政策？"
  -> 系统生成摘要回答 -> 展示明细列表 -> 导出 CSV

场景六（Dashboard）：
  展示查询量、拒绝率、越权告警、同步健康度

====================================================================
9. 交付物清单
====================================================================
[ ] 完整可运行代码（后端 + 前端）
[ ] docker-compose.yml 一键启动
[ ] README（安装、配置、运行说明）
[ ] seed_data.py 预置模拟数据脚本
[ ] 8 分钟演讲稿 + Demo 录屏/脚本（与代码并行准备，不要留到最后）
[ ] 架构图（Mermaid）
[ ] 审计日志样例导出文件
[ ] CodeBuddy/WorkBuddy 使用证明（截图 3 张以上或开发记录录屏）

====================================================================
10. 开发顺序建议
====================================================================
Week 1：P0 全部功能打通（登录->查询->RBAC过滤->LLM回答->审计落库->
        角色管理/审计后台页面），全程用 CodeBuddy 开发并截图留痕
Week 2 前半：补 P1（角色申请审批、Dashboard）+ P2 精选亮点（图片 OCR、
        审计自然语言问答）
Week 2 后半：联调、UI 打磨、演讲稿与 Demo 录屏准备，预留 1-2 天应对
        docker-compose 环境问题

====================================================================
11. 附录：文件与数据库重复记录的 RAG 测试（HR 休假政策）
====================================================================
目的：观察同一事实同时存在于文件和数据库时，RAG 的检索与回答表现
（来源是否重复、冲突时模型如何处理）。

数据：backend/seed_leave_duplicates.py 向 hr_db 写入 4 条 HR-L* 记录，
与 data/hr/Leave_Policy_Admin_Guide.docx (H01) 重合。
权限与 H01 一致（密级2、分区 hr、角色继承 hr_manager），两份数据对同样的人可见。

  记录     类型      与文件的关系
  HR-L01   完全相同  年假：中文原文照抄（18天，每2年加1天，上限25天）
  HR-L02   改写      病假：英文改写，数字一致（14天门诊，60天住院）
  HR-L03   冲突      年假结转：文件为最多5天、3月底前用完；
                     记录为10天、6月30日前用完
  HR-L04   冲突      陪产假：文件为2周、出生后16周内；
                     记录为3周、12个月内

操作：
  写入并同步：docker compose exec backend python seed_leave_duplicates.py
  删除并同步：docker compose exec backend python seed_leave_duplicates.py --remove
  注意：./start.sh --reset 或 seed_dept_databases.py 会重建 hr_db，
        HR-L* 记录会丢失，需要重新执行上面的写入命令。

测试用例（用 henry 登录，hr_manager，密级3，分区 hr）：
  1. "How many days of annual leave do I get after 3 years?"
     -> 对应 HR-L01（完全相同）。看来源里文件和数据库是否各出现一次，
        回答是否正确（19天）。
  2. "How many days of paid sick leave do staff get?"
     -> 对应 HR-L02（改写）。看改写后的记录是否也被召回，回答是否一致。
  3. "How many days of unused annual leave can I carry over?"
     -> 对应 HR-L03（冲突，5天 vs 10天）。看模型是否指出冲突、
        是否按"文件是唯一权威来源"处理。
  4. "How long is paternity leave?"
     -> 对应 HR-L04（冲突，2周 vs 3周）。观察同上。
  5. 对照：用 bob 或 frank 提同样的问题
     -> 无 hr 分区权限，文件和数据库两份都应不可见。

====================================================================
12. 附录：角色、密级、分区的区别与作用
====================================================================
三者是文档（或数据库记录）上的三道独立门，用户必须同时通过全部三道才能看到内容。
判定规则：
  用户拥有文档要求的角色之一  AND  用户密级 >= 文档密级
  AND  文档的所有分区都在用户的分区里

  项目        回答的问题            值的形式                   典型用途
  角色 role   你是做什么的？        多个，名字（hr_manager）   按岗位和部门划界（横向）
  密级        你被信任到多高？      一个数字，1 到 4           按敏感程度分层（纵向）
  分区        你有这件事的知情权吗？ 多个标签（aml、hr、board） 按需知（need-to-know）收口

各自的作用：
  角色：决定"哪类人"。文档的 allowed_roles 列了哪些角色，用户有其中任意一个即可。
        例：年假政策只给 hr_manager，合规官 alice 直接被拒。
        角色可以是临时的：加入 proj_merger 项目后获得同名角色，移出后失效。
  密级：决定"多敏感"。用户密级大于或等于文档要求才行。
        例：制裁筛查程序要求 3，alice 是 2 被拒；carol 是 3 可看。
        解决同一部门内部也分深浅的问题。
  分区：决定"有没有被特别授权"，最严格的一道：文档标了哪些分区，用户必须全部拥有。
        例：Access_Control_Policy 需要 security 分区，carol 角色和密级都够但无此分区，被拒。
        例：Exec_Compensation 要求 hr 和 board 两个分区，vera 两个都有才能看。
        普通文档没有分区，满足前两项的人都可看。

为什么要三个：
  只用角色，无法区分"同岗位但资历不同"，也无法收窄到某一项具体事务。
  角色管横向（哪个岗位），密级管纵向（多敏感），分区管跨部门的特殊事项
  （如并购尽调、董事会材料）。三者合用才能表达"并购估值模型：要有项目角色、
  密级 3、并且有 finance 分区"。bob 加入项目后只拿到角色这一关，所以仍看不到它。

容易混淆的点：
  - 管理员不等于有权限：admin 的角色是 platform_admin，只管授权，不在业务文档的
    allowed_roles 里，所以看不到业务内容。
  - 全员文档：角色写 employee，密级 1，没有分区，所有人都能看。
  - 数据库记录：每行有自己的 allowed_roles、required_clearance、compartment；
    没写角色时继承数据库的归属角色，规则相同。
  - 用户申请角色时不能修改密级和分区，二者由管理员维护，避免通过申请绕过后两道门。

权限矩阵（每份文档对每个账号的可见情况）见 requirement/doc_permission_matrix.md：
C = 密级不足，Z = 分区不足，— = 角色不符，✓ = 可访问。
