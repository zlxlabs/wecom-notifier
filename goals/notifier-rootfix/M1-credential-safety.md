---
lane: notifier-rootfix
id: M1
slug: credential-safety
status: 已完成
owner: pi-lead 本仓根治会话
order: 1
priority: 高
depends_on: []
merged_pr: 5
---

# M1：凭据与诊断身份分离

- **预期产出**：企微/飞书正常与失败日志、SendResult.error 不含假 webhook 密钥，实例可区分。
- **当前范围**：core 小函数与平台生产日志/错误路径；自有 tests/test_webhook_credentials.py。不改他会话旧测试整理/CI。
- **关键决策**：不截断URL作为脱敏，不关闭日志，不记录含凭据的原始异常。
- **已知阻塞**：PR 门禁与合并已完成；合并提交的 push CI 正在托管复验，不将 pending 说成绿。
- **推进前必须拿到的证据**：
  - [x] 本地public notifier入口+真实loguru DEBUG sink，正常/网络/API/worker/池异常日志及错误无假key；正常和sender错误可区分实例。意外worker异常事件缺直接实例ID为非阻断P2待办，已记录issue与verdict。
  - [x] 独立全量118 passed、新文件7 passed；原基线整文件7条目标AssertionError红验。
  - [x] ready后正式gate run#37725666864 success，primary/quality均success，审查记录已入库；PR #5已merge，合并提交33f4c862b86ce77fd256a3ea56f93acf45876bf1。
- **完成条件**：凭据安全增量经独立审查、正式PR门禁和合并完成；合并后push CI持续取证，失败立即处置。
- **证据**：docs/sessions/261008-notifier-rootfix/reviews/A-credentials-verdict.md。
