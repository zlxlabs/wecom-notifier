# B 卡：有界完整发送进度

## 2026-10-08：红验及首轮实现

- **当前阶段**：实现、窄测、`make test`、0.3.2 sdist/wheel 构建与隔离安装冒烟均通过；未提交、未推送、未建 draft PR；独立审查与正式 CI 尚未进行。
- **本段结论**：`MessageSegmenter` 现按最终段分页迭代计费；企微单发与池入口分别采用 text 2048、markdown_v2 3800 字节预算，审核扩张后重新分段且不再次审核；飞书文本/卡片按 requests JSON 序列化的完整请求体 20,000 bytes 预算计划，卡片分页标题参与预算。失败通过 `MESSAGE_SEGMENT_OVERSIZE` 或实际 API 失败回写 `SendResult`。
- **红验**：将本卡新测置于基线 `21e5a2c81f7e1e9f41e1fd440351f9b6da386fc2` 的临时归档副本执行，按目标断言红，`11 failed / 3 passed`；输出保存在 dispatch `artifacts/base-red.log`。主要复现包括 10KB 表格/代码未分页、Feishu 30KB 卡片单次发送、prepared 请求超 20KB、企微 text/池内容超 2048、审核扩张未分段、非法标题仍发送、第二段失败不可见以及空白/围栏/微型预算缺陷。修复后窄测 14 passed。
- **关键决策与已否决方案**：按企微不同字段限制使用独立预算；飞书按真实 `PreparedRequest.body` 而非自造紧凑 JSON 计量。超长单行/单元格允许逐 Unicode 字符文本降级；代码页内重新闭合围栏；超预算不删正文。未改 `ensure_ascii`、未新增重试/fallback，也未改既有测试和验证闸。飞书官方未注明 KB 换算，预算采用更严的十进制 20,000 bytes；标题和独立 Markdown 字段限制保留未知。
- **验证与构建**：窄测 `14 passed in 7.39s`；`make test` `132 passed in 34.08s`。构建 wheel 与 sdist 到 dispatch 报告目录的 `artifacts/`；wheel 安装至 `/tmp/wecom-notifier-032-venv`，从 `/tmp/wecom-notifier-wheel-smoke-cwd` 导入，路径为该 venv 的 `site-packages/wecom_notifier/__init__.py`，版本 0.3.2。首次安装冒烟误在 `/tmp` cwd 被同名 `re.py` 遮蔽标准库；改到干净临时 cwd 后测试通过，没有改库代码。
- **下一步唯一动作**：按允许范围完成差异/白名单自检，用显式文件路径提交实现并推送，确认远端 tip 后创建引用 #2/#3 的 draft PR。
