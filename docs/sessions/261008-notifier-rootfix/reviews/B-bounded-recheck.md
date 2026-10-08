# B H0..H1 增量独立审查 verdict

failure-visibility: p2-only

审查范围固定为 `716f1dc727a1b6f6208f03dbd603bb4ce6b4e250..37685054f45517cd926067d85f9a853eb22bd43b`，风险档位 `personal`。H1 修复了历史三项 P2 的目标路径；本轮独立 public producer 探针发现两项新的 P2，因此原结构与分页合同**仍未全部完成**。未发现 P1；当前 findings 不阻断交付，但 P2 级别不代表原设计合同已达成。

## 历史三项 P2 的 H1 状态

历史基准为 `fabddd5` 中的 `B-bounded-verdict.md`，本轮没有修改旧 verdict。

| 历史 finding | H1 实测 | 原合同状态 |
|---|---|---|
| 普通 Markdown 链接可能被跨页拆开 | 企微 `send_markdown` 两个请求，正文 3799/349 UTF-8 字节；飞书 `send_card` 两个请求，真实 PreparedRequest body 20000/686 字节。两者均只在一个页内出现完整链接，去除系统页码后逐字还原。新增锁定：`tests/test_bounded_delivery.py:337`。 | 该输入通过 |
| 审核扩张后保留旧页码，池计数仍为原页数 | 单 webhook 与 pool 各实测审核调用 4 次，最终发送 5 页，页码统一为 1..5；输入拼接精确等于原文，替换输出拼接精确等于最终正文，用户原文里的 `(Page 1/4)`、`(Page 2/4)` 保留；池 `segment_count=5`。新增锁定：`tests/test_bounded_delivery.py:386`。 | 该输入通过 |
| 大代码块闭围栏不独立成行 | 长单行及多行代码均经 public `send_markdown` 发送；6 个代码页各有两处围栏，按每页只移除一条规则插入的边界 LF 后，代码正文逐字还原，后续普通段落在围栏外。新增锁定：`tests/test_bounded_delivery.py:457`。 | 原 finding 路径通过；小代码块另有新 finding，见下文 |

同一 public probe 在 H0 的对照结果：企微长链接页未出现完整链接；Feishu 带签名的对应输入因签名开销较大而通过，但 H1 新测试的无签名输入在 H0 以链接断言失败、H1 通过。审核路径 H0 实发 8 页且页码不是统一 1..8，pool `segment_count` 与 8 页不符；H1 为 5 页且计数匹配。长代码路径 H0 不能按一条合成 LF 规则重建正文，H1 精确恢复。完整 H0 JSON 与 H1 wheel JSON 分别留在派发 artifacts 的 `h0-public-probe.json` 与 `public-probe.json`。

## H1 新 findings

### P2-1：Markdown Unicode 边界把可分页字符判成整页超限

- **违反不变式**：`design.md`「关键不变式」第 2、3 项及本卡 residual-fit / Unicode-frontier 轴。只要单个字符可放入空白页，当前余量不足就应转到下一页，不能拒绝整条消息。
- **代码位置**：`wecom_notifier/core/segmenter.py:152-165`，尤其第 160 行将当前剩余容量直接传给 `_split_unicode`；单字符大于该局部余量时，第 135-136 行抛 `MessageSegmentOversizeError`，没有先 flush 当前页。
- **企微 public 入口复现**：`WeComNotifier.send_markdown` 输入为 `x*3797 + LF + 中 + z*300`。前一物理行后剩 2 字节，下一字符为 3 字节中文；真实 `PreparedRequest` 数量为 0，`SendResult.success=False`，错误为 `MESSAGE_SEGMENT_OVERSIZE: one character exceeds budget`。完整 3800 字节页显然容纳该字符。
- **飞书 public 入口复现**：`FeishuNotifier.send_card` 用签名和真实标题模板计算出的首段内容预算为 19719 字节；输入前缀占 `budget-2`，后缀以 4 字节 emoji 开始。真实请求数为 0，同样错误拒绝；emoji 可放入空白页。
- **H0 对照**：同一探针脚本在 H0 源码 scratch 中运行时，企微 Markdown 成功发送 2 页（3800/323 字节），Feishu interactive 成功发送 2 页（19712/111 字节）；H1 对同一输入均 0 POST 并返回 oversize。企微 text 两边均通过。
- **反向对照**：企微 `send_text` 使用相邻剩 2 字节、后续中文的输入，通过 4 个请求成功且正文逐字重建，字段大小为 2048、20、2048、477 字节。这说明错误局限在 Markdown 分段路径，不是测试环境不具备字符或预算。
- **严重度与交付阻断分开判定**：P2，未升级 P1。实际公共 API 可触发；失败有明确 `SendResult` 且零 POST，没有静默吞错或正文被伪报成功。按 personal 风险不阻断交付；但该拒绝形态不符合原合同。

### P2-2：可容纳的小代码块会被通用文本切分拆坏

- **违反不变式**：`design.md`「要点 3」及本卡 ordinary-fenced-block 轴：一个自身可容纳的合法代码块应保留完整结构，不因前页余量不足而拆开。
- **代码位置**：`wecom_notifier/core/segmenter.py:213-215` 在代码块整体不超页时调用 `append_plain(whole)`；`append_plain` 第 195-198 行经 `_append_markdown_text` 逐字符填满当前页，没有把该完整代码块作为单一结构移动到下一页。
- **企微 public 入口复现**：`WeComNotifier.send_markdown` 输入为 `x*3768 + LF + ```python` 小代码块 + `AFTER-CODE`。代码块整体 39 字节，小于 3800 字节预算；前文结束后当前页只剩 20 字节。真实发送成功并发出两个请求，Markdown 字段为 3800/41 字节；去掉系统页码后两页围栏数分别为 1/1，代码块不在任何一页完整出现。正文仍在，但格式语义损坏且结果标记成功。
- **H0 对照**：相同输入在 H0 成功发送两页，字段 3780/61 字节，围栏计数 0/2，整段代码块完整位于第二页。该结构破坏由 H1 增量引入。
- **严重度与交付阻断分开判定**：P2，未升级 P1。内容未丢且每页有界，影响是明确可复现的 Markdown 结构破坏；按 personal 风险不阻断交付。原结构合同未满足。

## 设计不变式核对

| 不变式 | H1 代码与锁定 | 结论 |
|---|---|---|
| 1. 凭据不进入本库日志或 `SendResult.error` | 本轮没有改凭据身份/脱敏实现；`tests/test_webhook_credentials.py` 由 H1 `make test` 执行。 | 对本增量未发现新问题 |
| 2. 最终正文按平台预算计量，含页码、围栏、审核替换和飞书签名整包 | `core/segmenter.py`；企微 `manager.py` / `pool_base.py` 的预算入口；飞书 `notifier.py::_plan_segments` 与 `sender.py::_prepared_body_size`。锁定于 `tests/test_bounded_delivery.py` 的真实 public API 请求断言。探针检查企微 text 2048、markdown_v2 3800 UTF-8 字节及飞书 PreparedRequest body 20000 字节。 | 已发送的页均有界；P2-1 是可行正文被错误拒绝，不能据预算有界宣称合同完成 |
| 3. 正文完整并按规则保留结构；仅允许列明的页码/表头/围栏/LF | 分段实现位于 `core/segmenter.py`；`tests/test_bounded_delivery.py` 锁文本空白、链接、表格及代码边界。本轮多行代码探针按“每个代码页只移除紧邻闭围栏的一条合成 LF”后精确重建原代码正文。 | 历史长代码问题通过；P2-2 仍违反小代码块结构，故合同未完成 |
| 4. 本地不可行计划首次 HTTP 前失败；远端分段失败不得成功 | 企微/飞书 manager 捕获 oversize 并更新 `SendResult`；`test_feishu_oversize_title_fails_before_first_post`、`test_segment_api_failure_after_first_card_is_reported_not_rolled_back`。 | 该失败状态不变式通过；P2-1 的“可行输入被错误判不可行”另违反第 2 项 |
| 5. 公共签名兼容且调用方无需预切 | H1 未修改 notifier 公共方法签名；`tests/test_webhook_pool.py::test_single_webhook_backward_compatibility` 与完整套件通过。 | 对本增量通过 |

本轮新增 helper 的实际调用者均不少于两个：`_segment_contents` 被 `_segment_bounded` 和 `_segment_reviewed` 调用；`_review_content` 被企微 manager、pool 与 `_segment_reviewed` 使用；`_append_markdown_text` 同时处理普通行及表格长行。未增加公开 API、配置、依赖、线程、重试/fallback 或新事实状态；未引入第二条投递路径。旧私有辅助链在 H0 已存在，本轮没有新增它。

## H0 红验、H1 验证与 OCR

- **H0 红验**：scratch 基于 `716f1dc...`，只将 H1 的 `tests/test_bounded_delivery.py` 拷入 H0；link（企微/飞书）、审核全局页序（single/pool）、代码围栏（单长行/多短行）共 6 个参数化实例均以目标 `AssertionError` 失败；Feishu 无签名输入的链接断言也在 H0 以 `AssertionError` 暴露切分。未出现 helper `ImportError`、模块导入错误或环境错误。原始 pytest 摘要在派发 artifacts `h0-red.stdout`，scratch stderr 记录工作树自动清理。
- **H1 scratch 测试**：`make test` 为 139 passed / 40.53 秒；完整 `tests/test_bounded_delivery.py` 为 21 passed / 14.66 秒。新测试没有覆盖 P2-1 的 1/2-byte Markdown 余量或 P2-2 的可容纳小代码块，故全绿不推翻 public probe。
- **独立 wheel**：从 H1 构建 `wecom_notifier-0.3.2-py3-none-any.whl`；在新 CPython 3.12.3 venv 安装后，从源码树外导入，版本为 0.3.2，模块来自 venv `site-packages`。所有本节 public probes 都运行在该已安装 wheel 上，并只 mock `requests.sessions.Session.send` 捕获真实 `PreparedRequest`；未访问真实 webhook 或 `.env`。结构化结果见派发 artifacts `public-probe.json`。
- **H0/H1 对照探针**：同一脚本在 H0 scratch 从该树源码导入运行，输出见派发 artifacts `h0-public-probe.json`；它只用于 H0/H1 差异，不代替独立 H1 wheel 证据。
- **OCR 前置**：完整 envelope 的 `status=skipped`、`findings=[]`，原因主腿和备腿各 `leg_timeout` 120 秒；此状态不等于 clean，也不替代上述独立复审。完整 stdout JSON 和 stderr 在派发 artifacts `ocr-review.stdout.json`、`ocr-review.stderr`。
- **CI**：派发时 H1 为 draft，draft 的 primary 可能 skip；本轮没有将 draft 绿当作 primary 通过。主干 CI 基线 API 查询失败，继承红无法判定。
