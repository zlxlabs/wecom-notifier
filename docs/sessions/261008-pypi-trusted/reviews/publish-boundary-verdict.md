# PyPI 发布边界独立审查

failure-visibility: clean

- Dispatch-Id：`dlg-20261008-111851-708ca8`
- 固定审查范围：`e6c288a91e2714c6994f004baa0c62245e8be11f..e1d9198d65d2ba60fce191c2d689b818cfaa812c`
- 审查对象：`.github/workflows/publish.yml`、`README.md`
- 风险档：personal；只审查，不修改发布能力，不触发正式 workflow、OIDC 换证或上传。

## 结论

固定范围未发现违反任务卡 Spec 的代码或文档 finding。严重度：无；本次代码审查交付阻断：否。`failure-visibility` 为 `clean` 仅表示本轮独立 review 未发现 finding；OCR 状态另记为 `skipped`。

这不等于正式发布成功或 OIDC 身份已实测。PyPI Trusted Publisher 登记与 GitHub `pypi` environment 的 main-only 外部策略仍是后续发布前置；依任务卡要求，不把它们判成代码缺陷。任务卡提供了 PyPI 0.3.2 当前 HTTP 404 状态，本轮未再次查询这个会变化的外部状态。

## Spec 对照

1. **触发、权限、互斥**：`.github/workflows/publish.yml:3-17,104-116` 仅 `workflow_dispatch`，仓级 concurrency 使用 `cancel-in-progress: false`；发布 job 限 `refs/heads/main`、绑定 `pypi` environment，只有它声明 `id-token: write`。build job 继承只读 `contents: read`。未配置静态 PyPI 凭据、skip-existing、workflow retry 或 fallback。通过。
2. **版本、测试、构建**：`publish.yml:32-92` 将输入版本作为环境变量，正则限制为三段数字版本，再与 `pyproject.toml` 和 `wecom_notifier/__init__.py` 的唯一 `__version__` 赋值相等；源码当前两处均为 0.3.2。其后调用 `make test`，再清空 runner-temp 输出目录、build wheel/sdist，拒绝额外或非普通文件并执行 `twine check --strict`。`Makefile:1-4` 创建 `.venv` 并跑完整 `pytest tests -q`。本轮未跑项目测试套件；实际 workflow heredoc 探针见下文。通过。
3. **artifact producer/consumer 与 runtime 路径**：`publish.yml:94-146,172-175` 同名上传/下载 0.3.2 artifact，下载显式使用同一 `github.run_id`，两端都要求恰好两个预期文件且拒绝符号链接。官方 pinned action 源确认完整 SHA；PyPA action 以 composite 方式把 `packages-dir` 传给生成的 Docker action。官方 runner 源显示 runner temp 宿主目录挂载到 `/github/runner_temp`，该路径注册到容器映射，并且 Docker action 输入环境变量在启动前经 `TranslateToContainerPath()` 翻译；因此 `$RUNNER_TEMP/wecom-notifier-dist` 的实际消费路径映射到 `/github/runner_temp/wecom-notifier-dist`。这是官方 runner/action 源码之间的路径链检查，不是本机路径存在性或自写 path-map fixture。未执行 hosted runner 或 publisher action；不把此源码检查称为真实 GitHub run。
4. **PyPI 预检与部分上传**：`publish.yml:149-170` 仅 HTTP 404 允许继续，200 拒绝，其他 HTTP 状态以 unknown 失败；网络错误未被吞掉。上传 action 未启用 skip-existing，上传后失败即失败且没有回滚/自动重跑。预检与上传之间不是跨外部竞争的原子锁；仓内 concurrency 只串行化本 workflow。通过。
5. **可信身份与账户配置**：`publish.yml:104-116,172-175` 限制 main、选择 `pypi` environment，并只在发布 job 授予 OIDC token。README 的 owner/repository/workflow/environment 与任务卡锁定值一致（`README.md:34-45`）。PyPI 账户登记及 GitHub environment 策略尚未实际完成，不作为本轮 finding。
6. **上传后分发物和消费者验证**：`publish.yml:177-256` 从 PyPI JSON 的完整 `urls` 分发清单提取文件名与 SHA256，并与 build 目录中的 wheel/sdist 字节哈希逐项比较；不把 PEP 740 attestation 当成 distribution。随后从 `https://pypi.org/simple` 在 runner-temp 新 venv 安装精确版本，切到源码外 cwd、清除 `PYTHONPATH`，核验 metadata/module 版本及 site-packages 路径，再用 mock `requests.post` 断言实际请求 payload。通过代码检查与隔离 inline-script 探针；没有真实 PyPI 包可供安装验证。
7. **README 行为与副作用**：`README.md:34-48` 对发布者登记字段和手动命令的描述与 workflow 一致；列出的 owner/repository/workflow/environment 没有被称为密码或机密。README 声明发布仅作用于 PyPI，workflow 未创建 tag/release、部署、下游升级或发送消息。通过。

## 审查 finding 与交付判断

- P1：无。
- P2：无。
- P3：无。
- 代码审查交付阻断：否。
- 正式发布是否已成功：未执行，不能声称成功。

## 探针与验证

探针脚本从固定 H0 的 `.github/workflows/publish.yml` 提取原始 inline Python heredoc，不重写被测消费逻辑；临时 fixture 与网络 response stub 由本轮新建在 dispatch report artifacts 下，未读取或复用实现者报告/fixture。15 个预期结果均得到：

- 版本 `0.3.2` 通过；`0.3.3` 不匹配失败；shell 注入载荷被格式校验拒绝，未创建 sentinel。
- build 与 download 的两文件正常集合通过；增加普通额外条目或软链接均失败。
- PyPI 预检的 mock 404 通过；200 与 503 分别以重复版本和 unknown 拒绝。
- 发布后校验的两文件真实 fixture 哈希通过；加入第三个 distribution 或改错哈希均失败。顶层独立 attestation fixture 不计入 `urls`。

命令：`DELEGATE_REPORT_PATH="$DELEGATE_REPORT_PATH" python3 "$DELEGATE_REPORT_PATH.artifacts/probe_workflow.py"`，结果 `15 probes / all expected outcomes observed`。原始逐项 stdout/stderr 在 `probe-results.json`。本机仅有 Python 3.12.3，workflow 指定 3.11；因此此探针不声称与发布 runner Python 版本等价。脚本未访问网络，status 与发布响应均由 `sitecustomize` mock。

`git diff --check`：通过。没有运行 `make test`、GitHub workflow、真实 PyPI upload 或真实第三方 publisher action。唯一进行的外网机制核查是 8 个官方来源 URL；清单与 source/producer 输入保存在 `official-source-evidence.json` 和 `official-source-evidence.md`。

独立复算使用本轮新取的固定 SHA action.yml 与官方 runner 源，不读取实现者报告/内部 review；脚本 fixture 由本轮单独生成。publisher workflow 与原发布入口本身必然共用源码中的版本和文件名契约；原入口具体使用的枚举、测试夹具和容器假设未知，本轮不声称与之不共享。容器路径结论来自 runner 的实际 mount 与 input translation 源码，不使用本机自写映射推演。

## 三个降层问题

1. **不可逆上传何时发生？** 仅在 `publish` job 到达 PyPA upload action（`publish.yml:172-175`）时。预检 404 是只读线索；上传开始后不回滚，之后的公开 PyPI 校验失败不能撤销已上传文件。
2. **版本身份实际唯一吗？** 不是跨所有发布者的原子唯一性保证。仓内 concurrency 串行本 workflow，预检不能锁住其他外部上传者；PyPI 冲突会让 action 失败，但可能存在部分分发物已上传的窗口。Spec 不要求扩展成任意竞争下的原子发行。
3. **保护覆盖代码条件还是实际发布行为？** workflow 的版本、文件集合、HTTP 状态、PyPI 清单/摘要及消费导入均有代码判定；本轮对 inline 判定做了隔离 mock 探针。真实 runner/OIDC/发布行为未执行，官方 runner 源只佐证路径挂载和翻译机制。

## 状态、偏差与耗时

- OCR：`skipped`，不是 clean。完整 envelope 在 `ocr.stdout`；主腿为 `primary_marker_active(primary_failed_unclassified)`，备腿 `deepseek` 超时 `120.052s`。按约束未重试或增加腿，之后仍完整 review。
- 独立 review：完成，`clean`。
- CI 基线：派发信息注明 `gh api request failed`，继承红无法判定；本轮未运行 CI 或 GitHub workflow，没有新红。
- 固定被审 diff 为 275 insertions（workflow 257、README 18），高于卡面 target 120 / hard 180；本执行器没有实现改动授权，未扩展审查范围或改写冻结对象。
- 首次探针 harness 将 `RUNNER_TEMP` fixture 指向 dist 子目录本身，未符合 workflow 的 parent-temp 语义；修正为 parent temp 并按原始 workflow 重新执行后，15 项全部得到预期结果。最耗时步骤为 OCR 备腿等待约 120 秒。
