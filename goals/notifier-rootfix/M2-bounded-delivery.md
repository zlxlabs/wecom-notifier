---
lane: notifier-rootfix
id: M2
slug: bounded-delivery
status: 进行中
owner: pi-lead 本仓根治会话
order: 2
priority: 高
depends_on: [notifier-rootfix/M1]
merged_pr: null
---

# M2：企微与飞书最终发送内容有界

- **预期产出**：最终正文按平台/类型预算完整分段；卡片分页；失败明确，准备0.3.2构建和安装证据。
- **当前范围**：统一现有分段器产出与最终计划；审核扩张；sender边界；飞书卡片；新入口回归。不开新分段框架，不改下游，不发布PyPI。
- **关键决策**：用户选择内容优先、必要格式降级。保留缩进/换行，不能全局忽略空白；核对官方计量对象后再定大小断言，不盲改JSON序列化。
- **已知阻塞**：本地合同实测与独立审查已完成；正式ready后的CI/gate与合并尚待完成。OCR四轮两腿超时为skipped，已记录工具仓issue1392，不表述为clean；独立运行时验证仍已执行。
- **推进前必须拿到的证据**：
  - [x] 官方企微text/markdown_v2与飞书卡片限制的URL及明确原文；未验证项不得当上限。见platform-limits.md与独立审查来源。
  - [x] 本地public send_markdown/send_card及池入口，实际requests传输边界，5KB+长行/10KB+表格及代码/30KB+中文卡片/审核扩张，逐段有界、正文完整、分页正确。
  - [x] 本地非法计划零请求；第二段网络/API失败时SendResult不成功，允许已发送前段。
  - [x] 原基线及修复基线目标断言红、全量150项与完整bounded32项、独立审查无代码finding；H2轮子隔离安装及真实producer与精确边界通过。见reviews/B-closeout-verdict.md。
  - [ ] 原PR #7 ready后正式CI/gate通过并合并；不以本地或draft检查替代。
- **完成条件**：不变式证据齐全、PR合并且补丁产物准备完成；生产发布和下游升级不在完成声明内。
