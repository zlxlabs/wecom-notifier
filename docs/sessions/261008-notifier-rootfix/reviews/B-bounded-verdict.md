# PR7 有界分段独立审查 verdict

审查固定范围 `33f4c862b86ce77fd256a3ea56f93acf45876bf1..716f1dc727a1b6f6208f03dbd603bb4ce6b4e250`，风险档位 `personal`。结论：3 项 P2、0 项 P1。三项均不阻断投递：实测请求仍成功、正文仍有界；但普通链接、代码块围栏和审核扩张后的全局分页规则没有全部达成，不能据 P2 定级宣称原始验收已满足。

failure-visibility: p2-only

## Findings

### P2-1：长 Markdown 行会拆开本身可容纳的普通链接

- **违反的约定**：`design.md`「内容优先」要求保护普通结构，只允许超大不可分链接/表格按文本降级；README 也承诺可容纳的链接保留原文结构。
- **位置**：`wecom_notifier/core/segmenter.py:134`、`:140` 的 `append_plain` 对超预算整行直接按 Unicode 字符切片；普通 Markdown 行由 `:231` 进入该路径。
- **实际入口复现**：`WeComNotifier.send_markdown` → `requests.Session.send` 捕获真实 `PreparedRequest`。输入为 3,788 个 ASCII 前缀字符后接 38 字节 `[useful](https://example.invalid/path)`，再接 300 字符。得到 2 个请求，正文分别 3,800 / 348 字节；拼接后正文完全相同，但链接被切在 `[` 后，两个分页中都不存在完整链接。复跑脚本及输出见派发 artifacts 的 `reproduce_inline_link_boundary.py`、`inline-link-boundary.out`。
- **阻断交付**：否。内容完整且每段低于 markdown_v2 限额，但该链接无法作为链接呈现；这是明确承诺的结构损失，不属于获批的超大不可分链接降级。

### P2-2：审核扩张把原页码带入局部分段，池的结果页数也过期

- **违反的约定**：设计不变式 2/3 及卡面分页轴要求审核替换后最终页数统一、页号唯一顺序，不能嵌套旧页码或用局部页数代表整条消息；审核只执行一次。
- **位置**：`wecom_notifier/platforms/wecom/manager.py:261` 对每个原分段分别再次分段；`wecom_notifier/core/pool_base.py:304` 同样逐段重分。池在 `:162` 先记原段数、`:180` 替换为重分段结果，却在 `:255` 仍把旧 `total_segments` 写入 `SendResult.segment_count`。
- **实际入口复现**：使用真实 `WeComNotifier.send_text`，审核词列表由 mock GET 提供，替换规则将「扩张词」替成「[敏感词]」，输入为 454 次重复；分别走单 webhook 与 webhook 池。两者都成功发出 7 个 `PreparedRequest`，每个 `text.content` 均不超过 2048 UTF-8 字节，最终正文与实际审核器输出重建一致；但页码重复为局部 `1/3…3/3`，且首段出现新旧页码并列。池的 `SendResult.segment_count` 为 3，实际请求为 7。输出见 `reproduce_moderation_pagination.py`、`moderation-pagination.out`。
- **阻断交付**：否。正文没有丢失、预算满足且请求成功，但用户看到的页号和池结果计数不代表实际全局页序。

### P2-3：代码块分片会把闭围栏拼到代码行末尾

- **违反的约定**：`design.md`「代码块补围栏」和卡面代码围栏轴要求闭围栏位于有效独立行，分片边界的换行必须计入预算；围栏字符偶数不足以证明语法有效。
- **位置**：`wecom_notifier/core/segmenter.py:172` 与 `:179` 直接拼接 `part + closing`，没有保证 `part` 以换行结束。
- **实际入口复现**：`WeComNotifier.send_markdown` → 实际 `PreparedRequest`。对标题相邻的单行 9,000 字符 fenced code 以及 `a\n` 重复的多行 code 分片，均成功发送；每个代码页计数仍为两处围栏字符，但部分闭围栏直接粘在代码行尾（例如 `a` 后紧接三个反引号），不是独立行。两例的代码正文均可重建，页后的 `AFTER-CODE` 普通段落也在围栏外。输出见 `probe_markdown_structure.py`、`markdown-structure.out`。
- **阻断交付**：否。文本和字节预算仍完整，但对应代码页的 Markdown 围栏语法失效，代码格式无法按约定呈现。

## 不变式映射与证据

| 设计不变式 | 代码 / 测试证据 | 判定 |
|---|---|---|
| 1. 凭据不进本库日志或 SendResult.error | 固定 diff 未修改凭据实现；`tests/test_webhook_credentials.py` 随 `make test` 全量通过。此项属于既有 A 范围，本 verdict 不重审其实现。 | 对 B 没有新增发现 |
| 2. 最终消息预算含页码、围栏、审核扩张 | 分段实现位于 `core/segmenter.py`；企微管理器/池按 2048/3800 预算调用；飞书在 `feishu/notifier.py` 规划，`feishu/sender.py` 用 `PreparedRequest.body` 计量。全量与目标测试通过；真实企微请求字段最大 2048，飞书签名卡片请求体最大 19,999，13 页飞书最大 19,991，超大表头最大 3,799。 | 预算计量通过；分页/代码呈现见 P2-2、P2-3 |
| 3. 正文按规则完整，普通 Markdown 结构保护，不全局抹空白 | 新测试检查文本、表格、空行、缩进；本次 public API 探针核对正文重建。普通 38 字节链接跨页损坏，代码闭围栏粘行；两者为 P2-1、P2-3。 | 正文重建通过；格式要求未全部达成 |
| 4. 本地非法计划零 POST；远端分段失败不得成功 | `tests/test_bounded_delivery.py` 覆盖超长卡片标题零请求与第二段 API 拒绝；另对企微/飞书 public API 注入第二段 API 拒绝、超时恢复和连接错误耗尽。企微暂态恢复成功（4 次尝试/3 次接受），耗尽失败（3/1），API 拒绝失败（2/1）；飞书暂态恢复成功（3/2），耗尽失败（3/1）。已接受的首段未回滚。 | 通过；不承诺多请求原子性 |
| 5. 公共签名兼容且调用方无需预分段 | 对固定 base/head 的 AST 参数比较：`WeComNotifier.send_text/send_markdown`、`FeishuNotifier.send_text/send_card`、`MessageSegmenter.segment` 参数均不变；向后兼容测试在全量套件通过。 | 通过 |

## 运行与来源

- 官方限制：企微 [群机器人配置说明（91770）](https://developer.work.weixin.qq.com/document/path/91770) 明示 text 内容上限 2048 字节、markdown_v2 内容上限 4096 字节并要求 UTF-8；该对象是解析后字段内容，不是 JSON 整体。飞书 [自定义机器人使用指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot.md) 明示请求体不得超过 20 KB，并说明卡片在整个 JSON 请求体中发送；官方没有声明 KB 换算或卡片标题独立限额，因此代码采用 20,000 字节是保守项目口径。原文摘录保存在派发 artifacts 的 `official-source-excerpts.md`；浏览器读取失败与 curl 成功读取原文分开记录。
- 固定 head 临时 worktree：`make test` 通过，133 passed / 35.65 秒；随后 `pytest tests/test_bounded_delivery.py -q` 通过，15 passed / 8.52 秒。测试与日志在派发 artifacts 的 `make-test.log`、`bounded-test.log`。
- 原基线 `21e5a2c81f7e1e9f41e1fd440351f9b6da386fc2`：只拷入新增 `tests/test_bounded_delivery.py`，两条 public 入口红验分别是企微字段预算与飞书 interactive 分页；各以 `AssertionError` 失败，没有 helper `ImportError`。详见 `base-reds.status` 与两份 `base-test-*.log`。
- Wheel：临时树以 `python -m build --wheel` 构建 `wecom_notifier-0.3.2-py3-none-any.whl`；隔离 venv 安装后从非源码 cwd 导入 `site-packages` 中版本 0.3.2。企微 public text 3 个请求、最大字段 2048；飞书 public card 8 个请求、最大 body 19,999，标题页号和正文重建均正确。详见 `wheel-smoke.out`。
- OCR：完整 envelope 为 `status=skipped`、`findings=[]`、`reason=primary=leg_timeout; backup:deepseek=leg_timeout`；主/备腿各超时 300 秒。此结果不是 clean，不能覆盖上述全量独立审查。
- 正式 primary CI/gate 未核实。派发记录说明该 PR 处于 draft、primary job 会 skip，且主干基线 GitHub API 查询失败；draft 质量检查不作为审查通过证据。

## 范围与归属

审查对象始终是指定 SHA。`21e5a2c` 是 Pi 的规划元数据提交，只更新 GOALS 与 M1/M2 文档，不将其归给实现执行器；bounded delivery 实现从 `08b219a` 起。远端检查时 `origin/main=33f4c862`、`origin/card/wecom-261008-B-bounded=716f1dc`，本审查分支尚无远端同名 ref。审查过程中原工作区保持干净；临时测试树由 `scratch-worktree.sh` 自动清理。

## 未被新增测试文件锁定的组合

这三项缺陷都由真实 public producer 探针复现，但新增 `tests/test_bounded_delivery.py` 没有断言：长行中短链接跨页、代码页闭围栏必须独立成行、原消息已多页且审核再扩张后的全局页序/池 `segment_count`。现有代码围栏测试只断言每页 `count("```")==2`，不能约束闭围栏行位置。跨 10 页 Feishu 实际探针则通过：13 页标题从 1/13 到 13/13、body <=20000、正文完整。

`MessageSegmenter` 中旧的 `_segment_text/_segment_markdown/_segment_table` 私有辅助链仍在文件内，但当前公共 `segment()` 和生产发送者都走 `_segment_bounded`；全仓调用点检索只看到旧辅助链内部互调，没有发现生产消费者。按本卡范围，不把无当前消费者的旧私有方法单独报成阻断 finding。
