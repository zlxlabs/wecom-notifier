# B 卡：有界完整发送进度

## 2026-10-08：红验及首轮实现

- **当前阶段**：实现和验证已提交推送；draft PR #7 已创建并保持 draft。独立审查未进行；draft gate 的 `gate / primary` 为 SKIPPED，不代表正式主审通过。
- **本段结论**：`MessageSegmenter` 现按最终段分页迭代计费；企微单发与池入口分别采用 text 2048、markdown_v2 3800 字节预算，审核扩张后重新分段且不再次审核；飞书文本/卡片按 requests JSON 序列化的完整请求体 20,000 bytes 预算计划，卡片分页标题参与预算。失败通过 `MESSAGE_SEGMENT_OVERSIZE` 或实际 API 失败回写 `SendResult`。
- **红验**：将本卡新测置于基线 `21e5a2c81f7e1e9f41e1fd440351f9b6da386fc2` 的临时归档副本执行，按目标断言红，`11 failed / 3 passed`；输出保存在 dispatch `artifacts/base-red.log`。主要复现包括 10KB 表格/代码未分页、Feishu 30KB 卡片单次发送、prepared 请求超 20KB、企微 text/池内容超 2048、审核扩张未分段、非法标题仍发送、第二段失败不可见以及空白/围栏/微型预算缺陷。修复后窄测 14 passed。
- **关键决策与已否决方案**：按企微不同字段限制使用独立预算；飞书按真实 `PreparedRequest.body` 而非自造紧凑 JSON 计量。超长单行/单元格允许逐 Unicode 字符文本降级；代码页内重新闭合围栏；超预算不删正文。未改 `ensure_ascii`、未新增重试/fallback，也未改既有测试和验证闸。飞书官方未注明 KB 换算，预算采用更严的十进制 20,000 bytes；标题和独立 Markdown 字段限制保留未知。
- **验证与构建**：窄测 `14 passed in 7.39s`；`make test` `132 passed in 34.08s`。构建 wheel 与 sdist 到 dispatch 报告目录的 `artifacts/`；wheel 安装至 `/tmp/wecom-notifier-032-venv`，从 `/tmp/wecom-notifier-wheel-smoke-cwd` 导入，路径为该 venv 的 `site-packages/wecom_notifier/__init__.py`，版本 0.3.2。首次安装冒烟误在 `/tmp` cwd 被同名 `re.py` 遮蔽标准库；改到干净临时 cwd 后测试通过，没有改库代码。
- **PR 与远端**：https://github.com/zlxlabs/wecom-notifier/pull/7，分支 `card/wecom-261008-B-bounded`，实现提交完整 SHA `08b219ad14f65e87ba1ba644663324e4af0ec888`；远端分支 tip 与本地一致，远端 main 保持 `33f4c862b86ce77fd256a3ea56f93acf45876bf1`。PR 使用 `Refs #2`、`Refs #3`，未自动关单，明确要求保留规划祖先并 merge commit。
- **draft checks**：run `37730586523` 的 `gate / quality` 与 `gate / classify_pr_paths` 成功；`gate / primary`、`gate / resolve_advisory`、`gate / ocr` 等均为 SKIPPED；`gate / gate (draft)` 聚合成功不是正式主审证据。该 PR 仍 draft。
- **下一步唯一动作**：由 Pi 协调独立会话审查并处理正式 gate；本执行器不自行标 ready、不合并。独立审查通过后再由授权收尾人执行 ready 与正式 gate 核验。
