# PyPI 0.3.2 发行后独立验收收据

## 裁决

- 包验收：**通过**。PyPI 正式 index 安装的 `wecom-notifier==0.3.2` 与唯一 run 的 wheel/sdist 字节一致；3.11.15 隔离消费者验证通过。
- 原始 GitHub Actions run：**仍为 failure**，未重跑、未改写。本收据不把包通过冒充整 run 成功。
- 失败点：`Verify published PyPI files and hashes` 请求 PyPI 版本 JSON 时收到 HTTP 404；发生在文件清单/哈希比较之前。发行几秒后公开包与 metadata 可取且逐字节匹配。

## 冻结 run 与失败证据

- 项目 `zlxlabs/wecom-notifier`，run `37776634042`，attempt `1`，workflow `.github/workflows/publish.yml`，event `workflow_dispatch`，ref `main`，冻结 HEAD `5b4e5f5d802a308391118d48ec30f406287ef349`。run `2026-10-08T12:24:30Z` 启动、`12:26:15Z` 完成，run conclusion=`failure`。
- job `Test and build distributions` (`113309044537`) success；`Publish verified distributions to PyPI` (`113309548953`) failure。发布 step `Publish with PyPI Trusted Publishing` success；紧随的 `Verify published PyPI files and hashes` failure；两个 public-index consumer step skipped。未以 `--log-failed` 尾部推测失败。
- 白名单日志证据（publisher job，`2026-10-08T12:26:13Z`）：`2026-10-08T12:26:13.3418799Z urllib.error.HTTPError: HTTP Error 404: Not Found`；`12:26:13.3516234Z` exit code 1。完整日志不纳入仓库；过滤记录在私有 artifacts。
- 该 step 先对 runner 本地已构建包计算期望 SHA，再 `urlopen(https://pypi.org/pypi/wecom-notifier/0.3.2/json, timeout=20)`；无 HTTPError 处理。404 使程序在加载 metadata 与对比 `urls` / SHA 前直接退出。隔离的已知空态 HTTP 404 fixture 也令相同请求路径子进程 exit 1、`HTTPError.code=404`，确认此失败机制可复现。
- 时间线：wheel 上传时间 `12:26:10.213149Z`，sdist `12:26:12.049399Z`；实际失败请求日志 `12:26:13.3418799Z`（距 sdist 时间约 1.29 秒）。随后公开 JSON 与文件可访问，强烈支持“上传刚完成时版本 JSON 尚未可见”的传播时序推断；但历史响应只有 404，未记录其内部原因，故**404 机制确定、底层传播/缓存原因未能确证**，不把后续 200 单独当根因证明，也没有证据指向哈希错或包损坏。

## Producer → PyPI 字节验收

- 重新核实 run artifact `wecom-notifier-0.3.2`：artifact ID `11549419553`、未过期、`172507` bytes，绑定 run `37776634042`、冻结 SHA。下载并保留原始 ZIP；ZIP SHA256 `f97944e21518d607a39a0f84b8267f4be184c13a7a402a23f87b6ef16821d8fb`。
- 官方 PyPI `https://pypi.org/pypi/wecom-notifier/0.3.2/json` 实取 HTTP 200；name=`wecom-notifier`、version=`0.3.2`，`urls` 恰好两项且两项 `yanked=false`。wheel METADATA 与 sdist 两份 PKG-INFO 均为正确 name/version。
- `wecom_notifier-0.3.2-py3-none-any.whl`（86,572 bytes）：run ZIP、PyPI metadata SHA256、单独 HTTP 200 下载字节的 SHA256 均为 `293348c70151ad9827772830f4eac21d672a23dc41ec843969f813dc7f019531`；三份字节相同。
- `wecom_notifier-0.3.2.tar.gz`（91,936 bytes）：run ZIP、PyPI metadata SHA256、单独 HTTP 200 下载字节的 SHA256 均为 `17559ceb7d968349a796ccd947136930ebb3315e4fab62b44932240a006411d0`；三份字节相同。
- 独立获取每个 distribution URL；未将 attestation 当发行包。PyPI 原始 JSON、run ZIP、producer 两包、公开下载两包及过滤失败证据保留在仓库外的执行器私有 report artifacts 目录（私有文件 mode 0600；ZIP/JSON 内可重算以上 SHA）。

## 正式 index 安装与真实请求边界

- 在沙箱新 venv 用 Python `3.11.15`、`--no-cache-dir --index-url https://pypi.org/simple` 安装 exact `wecom-notifier==0.3.2`。从沙箱 cwd、`env -u PYTHONPATH` 验证 distribution/module version 均为 `0.3.2`，`wecom_notifier.__file__` 位于该 venv `site-packages`，不是 worktree。
- 复制未修改的 `tests/test_bounded_delivery.py` 到沙箱，在安装包环境运行：**32 passed**。首次因未安装声明的可选 moderation extras 有 4 项失败；仅向临时 venv 安装 `pypinyin`、`pyahocorasick` 后复跑 32 项全过。未改仓内测试或任何业务 venv。
- 安装后消费者 probe mock `requests.sessions.Session.send`，只向 `example.invalid` 构造真实非零 POST `PreparedRequest`，没有外发网络。保留 18 条真实序列化请求记录及其 JSON/原始 body bytes：企微 text 8 条（最大 2,048 UTF-8 bytes）、企微 markdown 2 条（最大 3,800 bytes，中文/emoji 低余量与小代码块组合）、飞书签名 interactive 8 条（最大请求体 19,998 bytes，逐请求验证 timestamp/sign）。三组正文按生成页码去标记后逐字符重建，均保留边界正文；没有全局 trim / 清空白重建。
- 请求记录 `sandbox/public-consumer-probe.jsonl`、32 项测试输出及安装日志均在上述 artifacts 私有目录；未保存或发送任何真实 webhook 凭据/通知。

## 下一步与边界

- 此卡没有改 workflow，也没有触发、rerun、重新上传或回滚。现在重跑同版本不合理：PyPI 已有且字节完全匹配的不可变 `0.3.2`；workflow 的现存版本预检会拒绝重复发行，重发也不能修复已完成的历史 run。
- 建议另开审阅后的 workflow 修正卡：仅为发布后 metadata HTTP 404 的短暂可见性设置有界等待，并保留最终 fail-loud；不得重传已存在发行版。当前报告不代替主脑对原 run 的领域终态裁决。
