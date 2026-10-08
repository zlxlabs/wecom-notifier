# PR #5：凭据安全独立审查 verdict

- 固定审查范围：`0db86951fd37152d7f69bffd74deb2760c582a7f..bdec090b3629e3fda2bc1e2b87910e58ac464497`
- 风险等级：`personal`（来自本树 `AGENTS.md`）
- 审查对象：16 个变更文件；完整差异为 549 行新增、71 行删除
- 本轮结论：无 P1；一项 P2 诊断缺口，不阻断交付
- 未评判：B 的分段、正文预算、飞书卡片不变式；设计明确将其留给 B 卡

failure-visibility: p2-only

## 判定摘要

凭据安全主路径得到代码与本地运行证据支持。正常、API 错误、连接错误及 worker 异常的企微、飞书和企微池路径均没有把假 key 写进本库测试 sink 或 `SendResult.error`；发送仍把原 URL 交给 `requests.post`，失败继续标记失败。网络失败后重试一次再成功的 mock HTTP 探针在两平台都观察到两次请求和最终成功。

P2 finding 仅涉及意外 worker 异常：清除异常文本/堆栈后，manager/scheduler 的失败日志和返回错误也没有补上 `webhook_id`。该失败是真实可触发且结果仍明确失败，但错误记录不能直接归属实例；普通、API 与网络发送错误日志均带实例 ID。按 `personal` 风险定级为可排查性不足，不阻断交付。

## 规范与不变式映射

| A 约束 | 实现落点 | 实际锁定 / 证据 | 裁定 |
|---|---|---|---|
| 凭据不进入本库日志或 `SendResult.error` | `core/webhook_identity.py:5-8`；两平台 sender；WeCom/Feishu manager、pool 与 `WebhookResource.__repr__` | `tests/test_webhook_credentials.py:94-211` 覆盖 API echo、网络错误、worker 异常、池路径；本地 DEBUG sink 使用 `diagnose=True, backtrace=True` | 主路径成立；见 P2 异常记录身份缺口 |
| 实例可区分 | `webhook_identity` 在 WeCom 与 Feishu sender/manager 均有真实调用点；池路径及资源 repr 也使用 | `test_public_success_logs_distinct_stable_identity_and_posts_original_urls` 用两个不同 key/平台，断言四个不同 ID 且各出现至少两次 | 正常及 sender 失败日志可区分；意外 worker 异常日志不满足，列 P2 |
| 原 HTTP 鉴权 URL 不变 | `wecom_notifier/platforms/wecom/sender.py:192-197`；`wecom_notifier/platforms/feishu/sender.py:230-235` | 公共入口成功回归断言 `posted_urls == WECom_URLS + FEISHU_URLS`；重试探针再次逐 URL 比较 | 通过；脱敏只用于诊断输出 |
| 成功/失败状态不被安全收敛改写 | sender 返回成功/失败；manager 继续 `mark_failed` / `mark_success` | 公共入口成功、API/网络/worker 错误测试；mock 网络失败后成功探针 | 通过；未观察到失败被报成功 |
| API 文案收敛但仍可诊断 | WeCom `safe_errcode`、Feishu `safe_code`；API/网络日志带 `webhook_id` | API echo 测试断言保留数字 `999`、去掉远端文案、URL 和 key；连接错误测试断言结果非空且无回显 | 通过；自由文本按约束移除 |

## Producer 分支核对

| Producer / 路径 | 变更后的输出 | 真实消费者/验证 |
|---|---|---|
| WeCom `Sender._send_request` | 调试、API、timeout、连接与 unexpected 错误日志用稳定 ID；API error 仅数字码或 `unknown` | 单 URL 与 pool 入口；成功、API echo、连接失败、worker 异常 |
| Feishu `FeishuSender._send_request` | 同样用稳定 ID；替换远端 `msg`，网络异常不格式化 exception | 单 URL 入口；成功、API echo、连接失败、worker 异常 |
| WeCom `WebhookManager` | 初始化/线程启停显示 ID；异常类型名替代异常文本/堆栈；发送失败继续写 `SendResult` | 同步 public API 排队到真实 worker；异常注入实际走 manager worker |
| Feishu `_FeishuWebhookManager` | 同上；分段失败继续 `mark_failed` | `FeishuNotifier.send_text` 公开入口与 worker |
| WeCom pool / `WebhookPoolBase` | 发送/重试标注资源 ID；异常 catch 不泄露异常文本；错误结果保留失败 | 两个不同 WeCom URL，发送由 pool scheduler 与 adapter 处理 |
| `WebhookResource.__repr__` | 资源诊断字段由 URL 前缀改为 hash ID | pool scheduler 异常的 Loguru diagnose 会格式化资源对象；worker fixture 覆盖该路径 |
| `setup_logger` 自有 sink | console/file 均关闭 Loguru diagnose 局部变量回显 | 自定义 sink 仍启用 diagnose/backtrace 的入口回归验证 |

该核对表以调用/输出动作铺开，不把只存在于成功或初始化路径上的 ID 误当成每个失败事件都有 ID。P2 finding 正是异常 catch 的事件级身份缺口。

## Finding

### P2 — worker 异常失败记录缺少 webhook 身份

- **违反的不变式**：`design.md`「关键不变式 1」要求日志/错误不含凭据且实例可区分；验收路径要求覆盖 worker 异常。
- **位置**：`wecom_notifier/platforms/wecom/manager.py:106-111`、`wecom_notifier/platforms/feishu/notifier.py:285-291`、`wecom_notifier/core/pool_base.py:130-135`。这些 catch 将异常安全地收敛为类型名，但失败日志与 `Internal error (...)` 均没有 `webhook_id`。
- **实测**：在当前 H0 用 `tests/test_webhook_credentials.py::test_worker_exceptions_are_sanitized_for_single_feishu_and_wecom_pool` 的相同注入方式（sender 抛出带 URL 的 `RuntimeError`），再用 DEBUG/`diagnose=True` sink 检查失败事件。独立探针结果：WeCom 与 Feishu 均为 `failure=True`、`result_id=False`、`error_log_id=False`、`key_in_result=False`、`key_in_error_log=False`。manager 初始化/启动日志另外带 ID，但失败事件本身没有，可定位性依赖旁路日志。
- **反证与影响**：sender 的 API、网络与一般请求异常分支均在错误日志中写 `webhook_id`；worker 异常的失败状态也保留。缺口限于请求处理过程中逃出 sender 的意外异常，表现为排查上下文不足，不会泄密或把失败报成成功。
- **阻断裁定**：不阻断。触发在本地注入中可复现；后果是失败事件缺少直接实例标签，仍有 message ID、异常类型与 manager 启停 ID，属于 P2 可排查性不足。

## 完整 diff 检查与实现判断

- 全量范围包含 README、设计/路线图文档、新增回归，以及两平台 sender、manager、pool、资源 repr 和共用身份函数；不是只看新测试。
- `webhook_identity` 在企微与飞书两边均实际调用，符合设计所述的共用消费者理由；稳定 ID 是 URL 的 SHA-256 前 16 位十六进制，不向日志输出 URL 前缀。
- 所有本次触及的凭据输出路径已逐处检查：sender 请求日志、API/网络错误、manager 启停/worker、池发送/重试、资源 repr、失败 `SendResult`。本库主动发布的异常消息不再格式化原异常或远端自由文本；README 说明应用自有 sink 与第三方库仍由应用负责。
- `requests.post` 的授权 URL、请求参数、成功判断、HTTP 网络重试计数和 rate-limit 重试循环未改。实际 mock 探针两平台都在第一次 `ConnectionError` 后以相同 URL 再请求一次并成功（每 URL 2 次）；失败状态由入口回归实际断言。
- 未新增公开 API、配置、依赖、后台机制或恢复路径；原有异常 catch 只改为记录类型名。`error or "send failed"` 是错误字符串为空时的文案默认，不改变失败状态；当前 sender 的失败返回均提供非空错误文本。
- `setup_logger` 的库自有 stdout/file sink 显式设 `diagnose=False`；入口回归另用用户自配的真实 loguru DEBUG sink（`diagnose=True, backtrace=True`）验证，未通过关闭日志获得安全结果。

### 16 个变更文件的审阅范围

- 规划/契约文档：`GOALS.md`、`README.md`、`docs/sessions/261008-notifier-rootfix/design.md`、`docs/sessions/261008-notifier-rootfix/progress/A-credentials-progress.md`、`goals/notifier-rootfix/M1-credential-safety.md`、`goals/notifier-rootfix/M2-bounded-delivery.md`。检查其 A/B 切分、凭据契约、边界/非目标与状态表达；不把 B 目标当成 A 的审查 finding。
- 回归：`tests/test_webhook_credentials.py`，完整读 211 行；覆盖真实 loguru sink、两平台与两 key、原 URL、API echo、网络异常、worker 与池。
- 公共 logger / 共用身份：`wecom_notifier/core/logger.py`、`wecom_notifier/core/webhook_identity.py`、`wecom_notifier/core/pool_base.py`。
- 飞书路径：`wecom_notifier/platforms/feishu/notifier.py`、`wecom_notifier/platforms/feishu/sender.py`。
- 企微路径：`wecom_notifier/platforms/wecom/manager.py`、`wecom_notifier/platforms/wecom/pool.py`、`wecom_notifier/platforms/wecom/resource.py`、`wecom_notifier/platforms/wecom/sender.py`。
- 上述实现文件逐项对照原 SHA 与 H0；本次没有测试以外的临时源码注入，也没有把 B 的分段规则当作凭据卡结论。

## OCR 前置

- 命令固定为 `--from 0db86951fd37152d7f69bffd74deb2760c582a7f --to bdec090b3629e3fda2bc1e2b87910e58ac464497`，摘要文件 681 字节；单腿 120 秒、全链预算 240 秒，外层 330 秒。
- 实际调用：`ocr-review --repo <本 worktree> --from 0db86951fd37152d7f69bffd74deb2760c582a7f --to bdec090b3629e3fda2bc1e2b87910e58ac464497 --audience agent --concurrency 4 --background-file /tmp/wecom-credentials-review-spec.md`。
- 真实 stdout envelope：`status=skipped`，`reason=primary=leg_timeout; backup:deepseek=leg_timeout`，`findings=[]`。minimax 与 deepseek 两腿分别运行 120.110 秒与 120.112 秒后超时。
- 结论是 **skipped（未完成扫描）**，不是 reviewed 或干净；配置没有 `*_config_error`，因此继续独立完整审查。OCR 输出未用于缩小 diff 或替代本 verdict。

## 运行验证

所有测试使用 mock HTTP；核对 `tests/test_*.py` 未加载 `.env`，也没有真实 HTTP 客户端调用。`make test` 的依赖安装发生在本 worktree 的 `.venv`，该目录被 `.gitignore` 忽略且未纳入提交。

1. 当前 H0 全量：`make test`，退出码 0；`118 passed in 26.94s`。
2. 当前 H0 凭据入口文件：`.venv/bin/python -m pytest tests/test_webhook_credentials.py -q`，退出码 0；`7 passed in 8.11s`。
3. 基线红验：由 scratch 脚本从 `8587e013cf1bf37d72f225d54ed2aa496e55d9ab` 创建 detached worktree，只复制新增 `tests/test_webhook_credentials.py`，在 scratch cwd 运行两条代表回归：

   ```sh
   REVIEW_TREE="$PWD" ../../agent-config/scripts/git/scratch-worktree.sh \
     ../../wecom-notifier \
     8587e013cf1bf37d72f225d54ed2aa496e55d9ab -- sh -c \
     'cp "$REVIEW_TREE"/tests/test_webhook_credentials.py tests/test_webhook_credentials.py && "$REVIEW_TREE"/.venv/bin/python -m pytest -q tests/test_webhook_credentials.py -k "public_success_logs_distinct_stable_identity_and_posts_original_urls or worker_exceptions_are_sanitized_for_single_feishu_and_wecom_pool"'
   ```

   退出码 1；`2 failed, 5 deselected in 3.14s`，两条均因目标凭据/日志断言触发 `AssertionError`，不是新增模块 `ImportError`。全文件补充红验为 `7 failed in 8.21s`，同样是目标断言转红。
4. 重试/URL mock 探针：WeCom 与 Feishu 各对原 URL 首次抛 `ConnectionError`、第二次返回成功；输出均为 `requests=2 url_preserved=True recovered=True key_in_logs=False`。没有真实网络访问。
5. 基线 CI 作业在卡面记录为不可用；本轮未运行 CI/gate，也未读取或接管 PR 状态。

## 现场、边界与执行记录

- 开始现场：分支 `card/wecom-261008-A-review`，HEAD 正是冻结 H0 `bdec090b3629e3fda2bc1e2b87910e58ac464497`，工作树干净；dispatch ID 与该 worktree 锁匹配，按卡面继续，没有误判为他人占用。
- 只新增本 verdict；未改生产/测试/README/依赖/工作流，未创建 PR、未改 PR 状态、未合并。`Task-Id` 与 `Fixes-Issue` 在卡面为空，未补造关联。
- scratch 红验树由脚本自动回收；本地测试 `.venv` 保持 ignored，不入提交。没有更改主 checkout 或其他 worktree。
- 踩到的环境坑：从 `/tmp` 直接执行临时探针时，Python 将 `/tmp` 放在导入路径前，已有 `/tmp/re.py` 遮住标准库 `re`，探针未启动。改为从审查 worktree 用 `python -c` 执行同一脚本后得到上述真实结果；未改任何仓库文件。
- 最耗时步骤是 OCR 全链的两次 120 秒超时（共约 240 秒）。OCR skipped 已如实记录，随后仍完成全量测试、入口回归、base 红验与完整 diff 审查。
