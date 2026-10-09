# 数据库数据源 — 演示用例设计

目标：除 `data/` 文件夹外，RAG 还能把 Postgres 里的业务记录同步进知识库，并沿用同一套 RBAC（角色 + 密级 + 分区）。

## 1. 三条规则

| # | 需求 | 设计 |
|---|---|---|
| 1 | 不同记录有不同访问权限 | 每条记录自带 ACL 列：`required_clearance`、`compartment`、`allowed_roles`（可空）。 |
| 2 | 不同的库代表不同部门，用 attach role 确定 | 每个库在 `data_sources` 登记一行，`permission_mapping.attach_roles` 是该库的默认角色。记录的 `allowed_roles` 为空时继承它，非空时覆盖它。 |
| 3 | 记录分普通数据和分区数据 | `compartment IS NULL` 为普通数据，只受角色 + 密级约束。`compartment` 有值为分区数据，用户还必须持有该分区（`compartments ⊆ user.compartments`）。 |

记录的有效 ACL：

```
allowed_roles        = 记录.allowed_roles  若非空，否则 库.attach_roles
required_clearance   = 记录.required_clearance（NULL 时取 default_clearance）
compartments         = [记录.compartment] 若非空，否则 []（多个分区用逗号分隔）
```

判定规则与文件库一致：角色命中 AND 密级 ≤ 用户密级 AND 分区 ⊆ 用户分区。

安全约定（fail closed）：`allowed_roles` 里出现系统中不存在的角色、密级不在 1–4、没有任何可用角色、或内容为空时，该记录不入索引并告警（只告警一次）；已入索引的记录变成非法后，会被撤出索引。数据库连不上或查询结果为空时，不会清空已有索引。

## 2. 五个部门库

库名 `*_db`，表名统一为 `knowledge_records`（`record_code, title, category, content, required_clearance, compartment, allowed_roles, updated_at`）。同步账号 `rag_reader` 只有只读权限。

| 库 | 部门 | attach role | 分区 | 记录数（普通 / 分区） |
|---|---|---|---|---|
| `hr_db` | HR | `hr_manager` | `hr`、`board` | 4 / 4 |
| `finance_db` | Finance | `finance_analyst` | `finance`、`board` | 4 / 4 |
| `risk_credit_db` | Risk & Credit | `risk_analyst` | `credit` | 4 / 4 |
| `compliance_db` | Compliance | `compliance_officer` | `aml` | 4 / 4 |
| `support_db` | Customer Support | `customer_support` | 无（全是普通数据，作对照） | 6 / 0 |

**与 `data/` 不重复**：数据库里放的是登记册、台账、阈值表、业务规则细则这类“记录型”内容，主题都避开 `data/` 里已有的政策文档（休假、报销、KYC/AML、STR、制裁筛查、催收、评分卡、估值模型等）。已用全文关键词和 4 词短语比对过，没有重复的事实或段落。

## 3. 演示账号

| 账号 | 角色 | 密级 | 分区 |
|---|---|---|---|
| henry | hr_manager | 3 | hr |
| gina | finance_analyst | 3 | finance |
| dave | risk_analyst | 3 | credit |
| alice | compliance_officer | 2 | aml |
| carol | compliance_officer + mlro | 3 | aml |
| frank | customer_support | 1 | — |
| bob | engineer | 2 | — |
| vera | exec | 4 | board, hr, finance |

## 4. 演示用例

“结果”列：✓ 可见；— 角色不匹配；C 密级不足；Z 缺分区。

### 用例 A：库 = 部门（attach role）

| 提问 | 账号 | 结果 |
|---|---|---|
| “What are the overtime allowance rules for line managers?”（HR-N04） | henry | ✓ |
| 同一问题 | gina | — 拒绝（不是 hr_manager，也不是 exec） |
| “What are the withholding tax rates for non-resident vendors?”（FIN-N03） | gina | ✓ |
| 同一问题 | henry | — 拒绝 |

### 用例 B：同一个库里，记录权限不同

| 记录 | 提问要点 | henry | vera | bob |
|---|---|---|---|---|
| HR-N01 内部调岗规则（allowed_roles=employee，密级 1） | internal job transfer | ✓ | ✓ | ✓（记录覆盖了库的默认角色，全员可见） |
| HR-N02 长期服务奖（继承 hr_manager，密级 2） | long-service award | ✓ | — | — |
| HR-N04 加班津贴（hr_manager + exec，密级 2） | overtime allowance | ✓ | ✓ | — |

要点：同一个 `hr_db`，三条记录有三种可见范围。

### 用例 C：普通数据 vs 分区数据

| 记录 | 类型 | alice (2, aml) | carol (3, aml) | henry (3, hr) |
|---|---|---|---|---|
| CMP-N02 个人账户交易规则（普通，密级 2） | 普通 | ✓ | ✓ | — |
| CMP-Z01 电汇发起人信息规则（aml，密级 2） | 分区 | ✓ | ✓ | — |
| CMP-Z02 贸易洗钱红旗指标（aml，密级 3） | 分区 | C | ✓ | — |
| CMP-Z04 执法机构请求台账（aml，密级 3，只限 mlro） | 分区 | — | ✓ | — |

要点：alice 能看分区内的低密级记录，看不到高密级记录（C）。只有 carol 持有 mlro 角色，才能看 CMP-Z04。

### 用例 D：分区不够，角色再对也不行

| 记录 | 说明 | gina (3, finance) | vera (4, board/hr/finance) |
|---|---|---|---|
| FIN-Z01 中期股息提案（finance，密级 3） | 分区 + 密级都满足 | ✓ | ✓ |
| FIN-Z04 董事会股票回购授权（board，密级 4，roles=exec） | gina 角色、密级、分区都不满足 | — | ✓ |
| HR-Z04 关键人才留任奖（hr，密级 4，roles=hr_manager+exec） | henry 角色对、分区对，但密级只有 3 | C（henry） | ✓ |

### 用例 E：分区数据与项目角色

| 记录 | 说明 | gina | bob（加入 proj_merger 后） |
|---|---|---|---|
| FIN-Z03 并购过桥贷款契约条款（finance，密级 3，roles=finance_analyst + proj_merger） | 项目角色命中，但 bob 密级 2、无 finance 分区 | ✓ | C + Z 双重拒绝 |

要点：临时项目角色只解决“角色”这一关，不能绕过密级和分区。

### 用例 F：普通库（无分区）作对照

| 记录 | frank (1) | bob (2) |
|---|---|---|
| SUP-N01 ATM 取现限额（employee，密级 1） | ✓ | ✓ |
| SUP-N05 VIP 客户处理（customer_support + account_manager，密级 2） | C | — |

### 用例 G：同步行为

同步在后台每 30 秒（`DB_SYNC_INTERVAL`）自动运行一次，也可以手动触发。

| 操作 | 预期 |
|---|---|
| 在 `hr_db` 里 `UPDATE` 一条记录的 `content` | 下一轮同步后，答案变成新内容 |
| 把 HR-N04 的 `required_clearance` 从 2 改为 4 | 只改权限也会重新索引，henry 不再能检索到 |
| `DELETE` 一条记录 | 向量库里对应 chunk 被清掉 |
| 往 `finance_db` 插一条 `allowed_roles={no_such_role}` 的记录 | 不入库，告警（fail closed） |
| 在 `data_sources` 删掉某个库 | 该库的所有记录撤出索引 |

触发方式：

- 后台线程：随 backend 启动，间隔 `DB_SYNC_INTERVAL` 秒，0 为关闭。
- 管理接口：`POST /api/admin/library/db-sync`（需要 platform_admin，可选参数 `source_id`）。
- 命令行：`docker compose exec backend python sync_databases.py`。

## 5. 相关文件

- `backend/seed_dept_databases.py`：创建 5 个库、`rag_reader` 账号、记录，并在 `data_sources` 登记。可重复执行（先删后建）。
- `backend/app/services/db_sync.py`：同步器。
- `backend/sync_databases.py`：命令行入口。
- `backend/tests/test_db_sync.py`：单元测试（行 ACL、attach role、分区、变更/删除、fail closed）。
