# B 卡：有界完整发送进度

## 2026-10-08：红验及首轮实现

- **当前阶段**：实现和验证已提交推送；draft PR #7 已创建并保持 draft。独立审查未进行；draft gate 的 `gate / primary` 为 SKIPPED，不代表正式主审通过。
- **本段结论**：`MessageSegmenter` 现按最终段分页迭代计费；企微单发与池入口分别采用 text 2048、markdown_v2 3800 字节预算，审核扩张后重新分段且不再次审核；飞书文本/卡片按 requests JSON 序列化的完整请求体 20,000 bytes 预算计划，卡片分页标题参与预算。失败通过 `MESSAGE_SEGMENT_OVERSIZE` 或实际 API 失败回写 `SendResult`。
- **红验**：将本卡新测置于基线 `21e5a2c81f7e1e9f41e1fd440351f9b6da386fc2` 的临时归档副本执行，按目标断言红，`11 failed / 4 passed`；输出保存在 dispatch `artifacts/base-red.log`。主要复现包括 10KB 表格/代码未分页、Feishu 30KB 卡片单次发送、prepared 请求超 20KB、企微 text/池内容超 2048、审核扩张未分段、非法标题仍发送、第二段失败不可见以及空白/围栏/微型预算缺陷。审核拒绝契约测试在基线通过，验证原拒绝/告警行为保持不变。修复后窄测 15 passed。
- **关键决策与已否决方案**：按企微不同字段限制使用独立预算；飞书按真实 `PreparedRequest.body` 而非自造紧凑 JSON 计量。超长单行/单元格允许逐 Unicode 字符文本降级；代码页内重新闭合围栏；超预算不删正文。未改 `ensure_ascii`、未新增重试/fallback，也未改既有测试和验证闸。飞书官方未注明 KB 换算，预算采用更严的十进制 20,000 bytes；标题和独立 Markdown 字段限制保留未知。
- **验证与构建**：窄测 `15 passed in 8.35s`；`make test` `133 passed in 35.07s`。构建 wheel 与 sdist 到 dispatch 报告目录的 `artifacts/`；wheel 安装至 `/tmp/wecom-notifier-032-venv`，从 `/tmp/wecom-notifier-wheel-smoke-cwd` 导入，路径为该 venv 的 `site-packages/wecom_notifier/__init__.py`，版本 0.3.2。首次安装冒烟误在 `/tmp` cwd 被同名 `re.py` 遮蔽标准库；改到干净临时 cwd 后测试通过，没有改库代码。
- **PR 与远端**：https://github.com/zlxlabs/wecom-notifier/pull/7，分支 `card/wecom-261008-B-bounded`。实现提交完整 SHA `08b219ad14f65e87ba1ba644663324e4af0ec888`，另有审核拒绝回归测试提交；基线/规划祖先 `21e5a2c81f7e1e9f41e1fd440351f9b6da386fc2` 保留，远端 main 为 `33f4c862b86ce77fd256a3ea56f93acf45876bf1`。PR 使用 `Refs #2`、`Refs #3`，未自动关单，明确要求 merge commit。
- **draft checks**：最后一次执行器观察到 PR 更新后 run `37731633425` 的 `gate / quality` 仍运行、`gate / classify_pr_paths` 成功；`gate / primary`、`gate / resolve_advisory`、`gate / ocr` 均为 SKIPPED。早一轮 run `37730586523` 的 `gate / gate (draft)` 成功只是聚合结果，不代表正式主审。PR 保持 draft。
- **下一步唯一动作**：由 Pi 协调独立会话审查并处理正式 gate；本执行器不自行标 ready、不合并。独立审查通过后再由授权收尾人执行 ready 与正式 gate 核验。

## 2026-10-08：按独立审查续修三项 P2

- **当前阶段**：续修实现、独立复现、窄测/全量、review probe 复跑及新 wheel 隔离冒烟均通过；尚未提交/推送这次续修。H0 固定为 `716f1dc727a1b6f6208f03dbd603bb4ce6b4e250`。
- **本段结论**：普通可容纳 Markdown 链接作为行内原子单元整体进入下一片（只有链接本身大于预算才按文本降级）；审核仍在原分段之后逐片调用一次，先按 `SegmentInfo` 页码元数据只剥除本库实际插入的前缀，再将审核结果整体编号；池 success `segment_count` 刷新为最终逻辑页数；每个拆开的代码块片段在闭围栏前增加独立 LF，该字节计入 3800 预算。
- **审查归属**：原独立 verdict 3 项 P2 / 0 P1；用户指定的三份 public `PreparedRequest` producer fixture 均在 H0 复现。H0 scratch 全目标文件红验为 `7 failed / 14 passed`，失败均为目标 `AssertionError`，无环境/helper 导入失败；输出 `artifacts/H0-red.log`。
- **审核语义**：未前移审核、未二次调用、未改变策略或原始文本分片的调用次数。现在 moderator 输入排除且仅排除由 segment 元数据确认的库自动页码，用户自带 `(Page x/y)` 原文保留；链接原子移动可能改变该链接附近的审核分片归属，但审核的全部用户正文拼接不变，这属于本次获准的结构修复。代码页新增的边界 LF 是系统语法字符，进入该页原有一次审核调用；用户代码字符/跨片调用边界未移动。
- **绿色验收**：新增文件 `tests/test_bounded_delivery.py` 共 21 项通过（`21 passed in 14.72s`）；`make test` `139 passed in 40.43s`。独立三个 probe 输出分别在 `artifacts/inline-link-boundary.out`、`artifacts/moderation-pagination.out`、`artifacts/markdown-structure.out`；代码围栏旧 probe 的原始重建器不剥离新增边界 LF，未照搬其宽松归一化，改用 `probe_markdown_structure_exact.py` 逐闭围栏移除恰好一条系统 LF，断言原代码字节精确重建，输出 `artifacts/markdown-structure-exact.out`。
- **新产物**：当前 H1 源码重构 0.3.2 sdist/wheel；隔离安装于 `/tmp/wecom-notifier-032-resume-h1-8faaff-venv`，从 `/tmp/wecom-notifier-032-resume-h1-cwd` 导入 `site-packages`，public send/mock producer smoke 覆盖 WeCom 链接/代码/审核池计数及 Feishu interactive 链接/签名。版本和导入证据在 `artifacts/wheel-smoke-h1.out`；wheel 与 sdist 不上传、不发布。
- **下一步唯一动作**：完成本地最终差异/行数检查后，创建一个续修提交并仅 push 一次更新 PR #7；保持 draft，不改 review verdict、不标 ready、不合并。
