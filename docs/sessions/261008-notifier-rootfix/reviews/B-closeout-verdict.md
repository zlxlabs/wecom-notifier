# B 独立增量审与原合同复验结论

- 固定审查范围：37685054f45517cd926067d85f9a853eb22bd43b..2e2549fc5d112d979cfe1f6ecf226b4e69ab9e66
- 规格：docs/sessions/261008-notifier-rootfix/design.md、platform-limits.md；风险档 personal
- H2：2e2549fc5d112d979cfe1f6ecf226b4e69ab9e66
- 变更：wecom_notifier/core/segmenter.py 13 行与 tests/test_bounded_delivery.py 206 行；合计净增 217 行
failure-visibility: skipped

## 审查裁决

H1..H2 只补足了“当前余量容不下下一个可分页字符时推进下一页”的既定规则。没有新增抽象、公开 API、字段、状态、配置、依赖、线程、parser、包装层或 fallback；没有发现新增双路径。H2 的分段行为与本批原合同实测满足。独立 OCR 前置调用最终为 skipped，所以本 verdict 不标成 clean：没有代码 finding，但 OCR 没有给出可采信的 clean 结果。

- 代码 finding：无。
- finding severity：无；这与 OCR 的 skipped 状态分开记录。
- 本轮 H2 验证新红：无。H1 反向红验预期失败，不属于 H2 新红。
- CI 基线：派卡信息记为 gh api request failed，故继承红未能判定；本轮没有运行 CI，也没有把本地测试结果冒充 CI 结论。

## 增量四问与关键不变式

| 检查项 | 结论与证据 |
|---|---|
| 是否只实现已登记行为 | 是。segmenter.py:160-165 在普通 Markdown 片当前有余量、但放不下首个 Unicode 字符时先结束当前片；segmenter.py:230-239 在长代码首片余量不足以容纳首个正文字符时先 flush，再按空页可用预算切分。H1 反向红验命中这两处。 |
| 是否新增未经批准抽象 | 否。仅改现有 MessageSegmenter 分段流程和本批回归测试；未增加可复用层或新消费者。 |
| 是否增加状态、事实源或 fallback | 否。无新状态、配置、重试或错误吞并；真实无法放入空页的字符仍报 oversize。 |
| 是否留下双路径 | 否。小型可容纳代码块仍整体保留；长代码继续走现有分片路径，当前前缀不够首字符时 flush 后从完整空页容量切分。 |
| 页预算与计量对象 | 满足。企微按最终字段 UTF-8 字节数；飞书按实际 PreparedRequest.body 字节数。页码与代码围栏开销计入预算。 |
| 正文、代码结构与页码 | 满足。原文拼接恢复；代码页围栏独立闭合，既定合成换行可辨认，缩进和空行保留；用户字面 Page 文本保留，系统页码全局从 1 到 N。 |
| 审核与池 | 满足。审核替换扩张后重新分段；单发及池入口各对每个初始片审核一次，池的逻辑 segment_count 对齐最终请求数。 |
| 失败语义与零 POST | 满足。空页不可能容纳单字符时仍失败；实际非零响应和后续分段失败仍返回非成功，前面已接受的请求不伪装回滚。 |

## 有限输入与独立实测

覆盖范围按已登记调用点、两种真实计量方式和本批改变条件构造，不外推为完整 Markdown 语法承诺。

- H2 完整文件：python -m pytest tests/test_bounded_delivery.py -q，32 passed。新增用例在 tests/test_bounded_delivery.py:523-701 锁定企微 text/markdown 与飞书 wire 余量、ASCII/中文/emoji、可分页与真正不可分页字符、小型代码块原子性、长代码首片、缩进/空行和后续段落。
- H1 反向红验：在 H1 scratch 中只用 H2 的 tests/test_bounded_delivery.py，命令过滤 unicode_advances_page or whole_fit_code_block or oversize_code_first_slice，得到 7 failed、3 passed、22 deselected。7 个失败均为目标 AssertionError（公共发送结果为 MESSAGE_SEGMENT_OVERSIZE: one character exceeds budget），涉及企微 Markdown 中文余量、飞书 emoji wire 余量、两平台小代码块和长代码中文/emoji 首片；未出现 ImportError 或环境错误。企微 text、ASCII 精确余量和长代码空页用例按原规则通过。
- H2 全量：make test 在 H2 scratch 中 150 passed；紧接着同一 scratch 完整 bounded 文件 32 passed。
- 空页失败对照：MessageSegmenter(max_bytes=2) 对 3 UTF-8 字节的“中”拒绝；预算恰为 3 的“中”和恰为 4 的 emoji 成功。
- 独立 wheel 消费：从 H2 scratch 构建 wecom_notifier-0.3.2-py3-none-any.whl（SHA256 a7543a8e709a379bee18cad93c29e0d647f6b9c19dbed38c8888e2dee6a8ae5e），安装到新虚拟环境。cwd 在 worktree 外，调用时 env -u PYTHONPATH；实际导入版本 0.3.2，模块路径为该 venv 的 site-packages/wecom_notifier/__init__.py。
- 已安装包真实 producer：通过公开 notifier API 调到 requests.sessions.Session.send，捕获并解析实际 PreparedRequest.body。企微 text 成功 16 页、最大正文 2047 UTF-8 字节；飞书卡片成功 7 页、最大整请求体 19998 字节；两者原文精确恢复。假响应非零码返回失败。两平台 39 字节小代码块各完整落在一页，AFTER-CODE 在闭围栏后同页；长代码前缀余量不足、空当前页、中英文/emoji 及缩进空行均恢复正确。
- 独立历史交叉：假 URL、假 key、requests.get 词表假响应；Session.send 和 requests.get 均被 mock，没有请求真实企微、飞书或词表 endpoint。短链接两平台各保持完整且只出现一页；超大表格行与长 URL 文本有界且标记/原文保留；审核扩张单发与池入口各审核 5 个初始片一次、用户 Page 文本保留、全局最终页码正确；池 segment_count 与请求数一致；飞书 11 页签名与标题总数正确；第二页假失败返回失败；真实 PreparedRequest 最大体积不超过 20000 字节。
- 精确边界探针：飞书精确预算计算把分页标题后缀 (1/2) 纳入固定卡片开销；按实际分页标题校准后，恰好 12 wire bytes 的 emoji 留在当前页，真实 body 为 20000 字节。企微剩余 0 字节遇中、剩 1 字节遇中文、剩 2 字节遇中文均推进下一页；剩 1 字节遇 ASCII、剩 3 字节遇中文原页容纳。飞书实际 JSON wire 余量 0/1/2 字节遇 emoji 均推进；wire 成本恰为 12 字节时原页容纳，实际请求体恰达 20000 字节。

## OCR 前置

按要求仅调用一次，范围固定 H1..H2，背景摘要 948 bytes，单腿超时 120 秒、链总预算 240 秒、外层 330 秒。完整 envelope：

- status=skipped
- reason=primary=leg_timeout; backup:deepseek=leg_timeout
- primary minimax：leg_timeout，120.109 秒
- backup deepseek：leg_timeout，120.059 秒
- findings=[] 不表示 clean；本 verdict 保留 failure-visibility: skipped
- 卡面提及的同机既有记录：issue #1392；本轮没有再增加扫描腿、预算或重试。

## 复跑命令与结果

在本 worktree 根目录运行。DELEGATE_REPORT_PATH 是本派发提供的报告路径；长命令均由 session 执行，scratch helper 会在命令结束后清理临时 worktree。

1. H2 全量及 bounded 文件：

   artifacts="$(dirname "$DELEGATE_REPORT_PATH")/artifacts"
   SCRATCH_WORKTREE_ROOT="$artifacts/scratch" "$HOME/projects/personal/agent-config/scripts/git/scratch-worktree.sh" "$PWD" 2e2549fc5d112d979cfe1f6ecf226b4e69ab9e66 -- sh -c 'make test && .venv/bin/python -m pytest tests/test_bounded_delivery.py -q'

   结果：150 passed；32 passed。

2. H1 红验：

   artifacts="$(dirname "$DELEGATE_REPORT_PATH")/artifacts"
   SCRATCH_WORKTREE_ROOT="$artifacts/scratch" "$HOME/projects/personal/agent-config/scripts/git/scratch-worktree.sh" "$PWD" 37685054f45517cd926067d85f9a853eb22bd43b -- sh -c 'git show 2e2549fc5d112d979cfe1f6ecf226b4e69ab9e66:tests/test_bounded_delivery.py > tests/test_bounded_delivery.py && python3 -m venv .venv && .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt pytest && .venv/bin/python -m pytest tests/test_bounded_delivery.py -q -k "unicode_advances_page or whole_fit_code_block or oversize_code_first_slice"'

   结果：7 个目标断言红、3 passed、22 deselected；红点如上，均非导入/环境失败。

3. Wheel 构建：

   artifacts="$(dirname "$DELEGATE_REPORT_PATH")/artifacts"
   SCRATCH_WORKTREE_ROOT="$artifacts/scratch" "$HOME/projects/personal/agent-config/scripts/git/scratch-worktree.sh" "$PWD" 2e2549fc5d112d979cfe1f6ecf226b4e69ab9e66 -- python3 -m pip wheel --disable-pip-version-check --no-deps . -w "$artifacts/wheelhouse"

   结果：wecom_notifier-0.3.2-py3-none-any.whl，SHA256 如上。独立探针脚本及运行产物位于 "$artifacts"，consumer_probe.py、consumer_crossings.py、consumer_boundaries.py；均由该已安装 wheel 执行。消费命令是在 artifacts/consumer-cwd 中运行 env -u PYTHONPATH "$artifacts/consumer-venv/bin/python" "$artifacts/<probe>.py"。

4. 隔离消费环境：

   artifacts="$(dirname "$DELEGATE_REPORT_PATH")/artifacts"
   python3 -m venv "$artifacts/consumer-venv"
   "$artifacts/consumer-venv/bin/python" -m pip install "$artifacts/wheelhouse/wecom_notifier-0.3.2-py3-none-any.whl[moderation]"
   cd "$artifacts/consumer-cwd"
   env -u PYTHONPATH "$artifacts/consumer-venv/bin/python" "$artifacts/consumer_probe.py"
   env -u PYTHONPATH "$artifacts/consumer-venv/bin/python" "$artifacts/consumer_crossings.py"
   env -u PYTHONPATH "$artifacts/consumer-venv/bin/python" "$artifacts/consumer_boundaries.py"

   结果：3 个探针 exit 0；模块来自 site-packages，环境未设置 PYTHONPATH。\n\n## 交付与范围

Verdict 固定引用 H2，不覆写旧 verdict。工作树仅新增本文件；没有修改实现、测试、配置、依赖、工作流或其他文档；没有创建 PR、改 PR 状态、部署或发布。评审行为复验完成，OCR 前置按 skipped 留有明确状态，不能解读为 OCR clean。
