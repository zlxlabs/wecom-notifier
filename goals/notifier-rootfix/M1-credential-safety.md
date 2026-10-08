---
lane: notifier-rootfix
id: M1
slug: credential-safety
status: 进行中
owner: pi-lead 本仓根治会话
order: 1
priority: 高
depends_on: []
merged_pr: null
---

# M1：凭据与诊断身份分离

- **预期产出**：企微/飞书正常与失败日志、SendResult.error 不含假 webhook 密钥，实例可区分。
- **当前范围**：core 小函数与平台生产日志/错误路径；自有 tests/test_webhook_credentials.py。不改他会话旧测试整理/CI。
- **关键决策**：不截断URL作为脱敏，不关闭日志，不记录含凭据的原始异常。
- **已知阻塞**：最终全量/正式门禁依赖另一会话测试整理和CI接入；可以先实施窄回归。
- **推进前必须拿到的证据**：
  - [ ] 本地public notifier入口+真实loguru DEBUG sink，正常/网络/API/worker/池异常日志及错误均无假key；两个实例可区分。
  - [ ] 新回归在原main因目标断言失败，修复后通过；外部测试整理合并后全量与正式CI/gate通过。
- **完成条件**：上述证据齐全且PR合并；PR号写merged_pr，才标已完成。
