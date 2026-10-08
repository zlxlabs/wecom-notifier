# A 卡：企微与飞书凭据隔离进度

## 2026-10-08：入口回归与凭据隔离实现

- **当前阶段**：实现已完成，窄回归本地通过；等待提交并创建 draft PR，尚未完成独立审查/正式 CI。
- **本段结论**：企微、飞书单 webhook 与企微池的本库日志改用稳定 `webhook_id`；请求仍使用原 URL。第三方错误回显和原始异常堆栈不进入库日志/`SendResult.error`，错误类别/API 数字码与消息定位信息保留。真实 loguru `DEBUG` sink（`diagnose=True`、`backtrace=True`）入口测试 7 项通过。
- **关键决策与已否决方案**：采用 URL 的 SHA-256 短标识，不以 URL/URL 前缀作为身份；API 失败只输出受控类别/数字码，不保留远端自由文本；worker 捕获异常只记录类型和消息 ID，不记录异常对象/traceback。未关闭日志、未改发送 URL、未新增重试/fallback/catch 以外的恢复逻辑；未改既有测试、构建/工作流文件。
- **下一步唯一动作**：按显式文件路径提交本卡绿色实现并推送分支，随后创建引用 #1 的 draft PR。

## 2026-10-08：首个绿色提交已推送并建立 Draft PR

- **当前阶段**：PR #5 已建立并保持 draft；远端分支 tip 已核实；本卡等待独立审查及主脑正式验收。
- **本段结论**：窄测最终 7 项通过；分支 `card/wecom-261008-A-credentials` 远端 tip 与本地 HEAD 均为 `c9800d6bb25d7ca2bd45ed8fe808bdd6dc85a7fb`。PR 为 https://github.com/zlxlabs/wecom-notifier/pull/5；`gh pr checks 5` 返回该分支无检查，不能视为 CI 全绿。
- **关键决策与已否决方案**：PR 正文仅 `Refs #1`，未自动关闭 issue；规划祖先 `8587e013cf1bf37d72f225d54ed2aa496e55d9ab` 保持不变，要求后续 merge commit 进入 main。此前首推被本地默认分支落后远端的公开扫描闸拒绝；执行 `git fetch origin main` 更新 remote-tracking ref 后，未绕闸重试并成功推送。全量旧测试/正式 CI 未运行，等待测试整理卡落 main。
- **下一步唯一动作**：交主脑独立审查 PR #5，并在测试整理/CI 产物落 main 后接续正式全量与门禁验收。
