# PyPI 0.3.2 Trusted Publishing 启动收据

## 授权与边界
- 用户明确授权将 `wecom-notifier` 0.3.2 发布到 PyPI，并选择 Trusted Publishing；本收据只证明安全触发已核实，不代表发行成功。
- 目标：`zlxlabs/wecom-notifier` 的 `Publish to PyPI`（`.github/workflows/publish.yml`），`main`，冻结源提交 `5b4e5f5d802a308391118d48ec30f406287ef349`。
- 本次唯一触发输入为 `version=0.3.2`。未创建 tag/GitHub Release，未改 workflow 或应用代码，未读取/生成发布密钥，也未读取运行日志。

## 触发前核验
- 真实远端 `refs/heads/main` 与冻结 SHA 相同：`5b4e5f5d802a308391118d48ec30f406287ef349`。
- GitHub workflow API：名称 `Publish to PyPI`，路径 `.github/workflows/publish.yml`，状态 `active`。
- `pypi` 环境的部署分支策略恰为唯一 `main` 分支；环境 secrets 数量为 0。
- 单独请求公开版本 JSON `https://pypi.org/pypi/wecom-notifier/0.3.2/json` 得 HTTP 404（触发前）。
- 冻结 SHA 的既有 workflow run 数量为 0。基线时间 `2026-10-08T12:24:28Z`；workflow runs 总数 0，基线 IDs：无。

## 单次触发与权威回读
- 在主仓 main checkout 的 merge lease 内，仅执行一次：`gh workflow run publish.yml --repo zlxlabs/wecom-notifier --ref main -f version=0.3.2`；命令退出码 0。
- GitHub Actions run ID：`37776634042`；URL：<https://github.com/zlxlabs/wecom-notifier/actions/runs/37776634042>。
- 首次权威 run API 回读：`event=workflow_dispatch`，`path=.github/workflows/publish.yml`，`head_branch=main`，`head_sha=5b4e5f5d802a308391118d48ec30f406287ef349`，`created_at=2026-10-08T12:24:30Z`，`run_started_at=2026-10-08T12:24:30Z`，初始 `status=in_progress`、`conclusion=null`，`run_attempt=1`。
- 收尾时 run API 已变为 `status=completed`、`conclusion=failure`（`updated_at=2026-10-08T12:26:15Z`）。只读结构化 job/step 状态：`Test and build distributions` 成功；`Publish verified distributions to PyPI` 失败，其中 `Publish with PyPI Trusted Publishing` 步骤成功、`Verify published PyPI files and hashes` 步骤失败，之后消费者安装/导入步骤跳过。未读取任何日志。
- Run API 的 `inputs` 字段返回 `null`；版本输入依据为上述唯一一次实际 CLI 参数 `-f version=0.3.2`，并以零 run 基线后立即出现的唯一新 run 与时间线关联。未读取日志。

## 当前状态
- 安全启动已核实；工作流最终以失败结束，但 Trusted Publishing 步骤报告成功、其后的发布文件/哈希核验步骤失败。公开 PyPI 包是否存在、文件与哈希是否正确均未由本执行器确认；请 Pi 主脑通过 managedCI 接收并立即另验公开包状态。不得据此重发 dispatch。
- 未重发 dispatch，未启动 CI watcher，未读取日志，也未冒充发行领域终态判定。
