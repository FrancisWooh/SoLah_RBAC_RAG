# 文档 × 角色 × 密级 权限矩阵（草案）

判定规则（与 `readme.txt` P0 一致）：`allowed_roles` 命中 AND `required_clearance` ≤ user.clearance AND `compartments` ⊆ user.compartments。所有人隐含 `all_staff` 角色。★ = 已存在于 demo_content.py / seed_data.py。

## 1. 角色画像（演示账号）

| 账号 | 角色 | clearance | compartments |
|---|---|---|---|
| alice | compliance_officer | 2 | aml |
| carol | compliance_officer, mlro | 3 | aml |
| dave | risk_analyst | 3 | credit |
| erin | card_ops | 2 | — |
| frank | customer_support | 1 | — |
| gina | finance_analyst | 3 | finance |
| henry | hr_manager | 3 | hr |
| ivy | marketing_manager | 2 | — |
| jack | account_manager | 2 | — |
| bob | engineer | 1 | — |
| kate | security_engineer | 3 | security |
| leo | legal_counsel | 3 | legal |
| vera | exec | 4 | board, hr, finance |
| admin | platform_admin | 4 | aml, finance |
| bob+M | engineer, proj_merger | 2 | — |

`bob+M` = bob 被加入 proj_merger 后的状态（临时角色，需将 clearance 提到 2，见待确认项）。

## 2. 矩阵（✓ 可访问；C=因密级不足被拒；Z=因分区不足被拒；—=角色不匹配）

| ID | 文档 | allowed_roles | 密级 | 分区 | alice | carol | dave | erin | frank | gina | henry | ivy | jack | bob | kate | leo | vera | admin | bob+M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | **Public / 全员** | | | | | | | | | | | | | | | | | | |
| P01 | Company_Overview.pdf | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| P02 | Employee_Handbook.pdf（不含年假细则） | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| P03 | Office_Locations_Holidays.md | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| P04 | Data_Classification_Policy.pdf | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| P05 | Vendor_Newsletter（含注入句，测防护） | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | **Compliance** | | | | | | | | | | | | | | | | | | |
| C01 | KYC_AML_Policy_v3.pdf ★现有 | compliance_officer | 2 | aml | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — | — | — | — |
| C02 | CASA_KYC_Requirements.docx ★现有 | compliance_officer | 2 | aml | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — | — | — | — |
| C03 | Sanctions_Screening_Procedure.docx | compliance_officer | 3 | aml | C | ✓ | — | — | — | — | — | — | — | — | — | — | — | — | — |
| C04 | STR_Filing_Guideline.pdf | compliance_officer | 3 | aml | C | ✓ | — | — | — | — | — | — | — | — | — | — | — | — | — |
| C05 | MAS_Notice_626_Summary.pdf | compliance_officer, risk_analyst, legal_counsel | 2 | — | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — | ✓ | — | — | — |
| C06 | Annual_Compliance_Training.pptx | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | **Risk & Credit** | | | | | | | | | | | | | | | | | | |
| R01 | Credit_Limit_Assessment_Model.docx | risk_analyst | 3 | credit | — | — | ✓ | — | — | — | — | — | — | — | — | — | — | — | — |
| R02 | SME_Risk_Scorecard.xlsx | risk_analyst | 3 | credit | — | — | ✓ | — | — | — | — | — | — | — | — | — | — | — | — |
| R03 | Fraud_Rules_Playbook.md | risk_analyst, card_ops | 2 | — | — | — | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — | — |
| R04 | Collections_Policy.pdf | risk_analyst, customer_support | 2 | — | — | — | ✓ | — | C | — | — | — | — | — | — | — | — | — | — |
| | **Card Ops** | | | | | | | | | | | | | | | | | | |
| K01 | Card_Limit_Adjustment_Rules.docx ★现有 | card_ops | 1 | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — | — | — |
| K02 | Dispute_Chargeback_SOP.pdf | card_ops, customer_support | 1 | — | — | — | — | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — |
| K03 | Scheme_Rules_Summary.pdf | card_ops | 2 | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — | — | — |
| | **Customer Support** | | | | | | | | | | | | | | | | | | |
| S01 | Complaint_Handling_SOP.docx ★现有 | customer_support | 1 | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — | — |
| S02 | FAQ_Account_Opening.md | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S03 | Escalation_Matrix.xlsx | customer_support, card_ops | 1 | — | — | — | — | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — |
| | **Finance** | | | | | | | | | | | | | | | | | | |
| F01 | Expense_Policy.pdf | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| F02 | Invoice_Approval_Workflow.pdf | finance_analyst | 2 | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — |
| F03 | Revenue_Recognition_Policy.docx | finance_analyst | 2 | finance | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — |
| F04 | Q3_Management_Accounts.xlsx | finance_analyst | 3 | finance | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — |
| F05 | Budget_FY2027_Draft.xlsx | finance_analyst | 3 | finance | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — | — |
| | **HR** | | | | | | | | | | | | | | | | | | |
| H01 | Leave_Policy_Admin_Guide.docx（年假） | hr_manager | 2 | hr | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — |
| H02 | Compensation_Bands.xlsx | hr_manager | 3 | hr | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — |
| H03 | Performance_Review_Guide.docx | hr_manager | 2 | hr | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — |
| H04 | Onboarding_Checklist.md | hr_manager | 2 | hr | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — | — |
| H05 | Remote_Work_Policy.pdf | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | **Marketing / Sales** | | | | | | | | | | | | | | | | | | |
| M01 | Brand_Guidelines.pdf | all_staff | 1 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| M02 | Campaign_Plan_VN_Launch.pptx | marketing_manager | 2 | — | — | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — |
| M03 | Competitor_Analysis_2026.pdf | marketing_manager, account_manager, exec | 2 | — | — | — | — | — | — | — | — | ✓ | ✓ | — | — | — | ✓ | — | — |
| M04 | Press_Release_Template.docx | marketing_manager | 1 | — | — | — | — | — | — | — | — | ✓ | — | — | — | — | — | — | — |
| A01 | Pricing_and_Fee_Schedule.pdf | account_manager, customer_support, marketing_manager | 1 | — | — | — | — | — | ✓ | — | — | ✓ | ✓ | — | — | — | — | — | — |
| A02 | Partner_Agreement_Template.docx | account_manager, legal_counsel | 2 | — | — | — | — | — | — | — | — | — | ✓ | — | — | ✓ | — | — | — |
| | **Engineering / Security** | | | | | | | | | | | | | | | | | | |
| E01 | API_Design_Standards.md | engineer, security_engineer | 1 | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ | — | — | — | ✓ |
| E02 | Incident_Response_Runbook.md | engineer, security_engineer | 2 | — | — | — | — | — | — | — | — | — | — | C | ✓ | — | — | — | ✓ |
| E03 | Access_Control_Policy.pdf | security_engineer, compliance_officer | 3 | security | C | Z | — | — | — | — | — | — | — | — | ✓ | — | — | — | — |
| E04 | Postmortem_2026-08_Outage.docx | engineer, security_engineer | 2 | — | — | — | — | — | — | — | — | — | — | C | ✓ | — | — | — | ✓ |
| | **Legal** | | | | | | | | | | | | | | | | | | |
| L01 | PDPA_Policy.pdf | legal_counsel, compliance_officer | 2 | — | ✓ | ✓ | — | — | — | — | — | — | — | — | — | ✓ | — | — | — |
| L02 | NDA_Template.docx | legal_counsel, account_manager | 1 | — | — | — | — | — | — | — | — | — | ✓ | — | — | ✓ | — | — | — |
| L03 | Vendor_Contract_Review_Checklist.docx | legal_counsel | 2 | legal | — | — | — | — | — | — | — | — | — | — | — | ✓ | — | — | — |
| | **Projects（临时角色）** | | | | | | | | | | | | | | | | | | |
| J01 | proj_merger/Due_Diligence_Report.docx | proj_merger | 2 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ |
| J02 | proj_merger/Valuation_Model.xlsx | proj_merger | 3 | finance | — | — | — | — | — | — | — | — | — | — | — | — | — | — | C |
| J03 | proj_mas_audit/Evidence_Index.xlsx | proj_mas_audit | 2 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| J04 | proj_card_launch_vn/Licensing_Notes.docx | proj_card_launch_vn | 2 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| J05 | proj_aml_upgrade/Design_Doc.md | proj_aml_upgrade | 2 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| | **Executive** | | | | | | | | | | | | | | | | | | |
| X01 | Board_Minutes_Q3.pdf | exec | 4 | board | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | — | — |
| X02 | Exec_Compensation.xlsx | exec, hr_manager | 4 | hr, board | — | — | — | — | — | — | C | — | — | — | — | — | ✓ | — | — |
| X03 | Strategy_FY2027.pptx | exec | 3 | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | — | — |

## 3. 各账号可见文档数（共 52 份）

| alice | carol | dave | erin | frank | gina | henry | ivy | jack | bob | kate | leo | vera | admin | bob+M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14 | 16 | 15 | 15 | 14 | 14 | 14 | 14 | 14 | 11 | 14 | 15 | 14 | 10 | 14 |

## 4. 演示场景对照

| 场景 | 账号 → 查询 | 预期 | 命中文档 |
|---|---|---|---|
| 正常查询 | alice → KYC/AML 审核标准 | allow | C01 |
| 越权（角色） | alice → 年假政策 | deny | H01（alice 无 hr_manager） |
| 越权（密级） | alice → STR 提交指引 | deny(C) | C04 需 clearance 3，alice 为 2；carol 可见 |
| 越权（分区） | dave → 季度管理账目 | deny | F04（角色不匹配） |
| 管理员≠内容权限 | admin → 薪酬级别 | deny | H02（admin 管权限，不读业务内容） |
| 临时角色 | bob → 并购尽调报告 | 加入前 deny，加入后 allow，移出后 deny | J01；J02 仍 deny（需 finance 分区） |
| 提示注入 | 任意 → 查询 P05 相关内容 | 回答不得受文档内指令影响 | P05 |

## 5. 待确认
1. J01/J02 密级：现有 bob clearance=1，演示并购文档需 ≥2。选项 A：bob 提到 2（本稿采用）；选项 B：J01 降为密级 1。
2. 年假政策：为保持现有场景二，H01 仅 hr_manager 可见，因此 P02 员工手册不能包含年假细则。
3. 现有 3 个用户（alice/bob/admin）不足，需新增 12 个账号。
4. 是否需要 archived 旧版本样本（如 C01 v1）用于测试版本治理。
