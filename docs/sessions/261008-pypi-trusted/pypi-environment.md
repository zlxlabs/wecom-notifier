# PyPI GitHub Environment 配置收据

## 决策与范围
- 仓库：`zlxlabs/wecom-notifier`；environment：`pypi`。
- 只允许 `branch: main`；拒绝其他 branch 和所有 tag。不配置 secrets / PyPI token，不添加等待时间或审批人。
- 未改 workflow、README、应用、tests、其他 environment 或其他仓库。

## 修改前读取
- GitHub environments 列表读取时间：2026-10-08T11:23:15Z，`total_count=0`。另在任何写入前读取目标 GET `/repos/zlxlabs/wecom-notifier/environments/pypi`，返回权威 HTTP 404（GitHub 响应链接到官方 Get an environment 文档）。
- 写入前读取目标 deployment-branch-policies 列表，HTTP 404；环境不存在，故没有既有 branch policies 或保护规则可覆盖。

## 创建及权威回读
- 创建结果：新建 environment，非原有对象。PUT 创建于 `2026-10-08T11:24:51Z`；GitHub 返回 environment ID `23773364878`。
- 创建时仅设置 `deployment_branch_policy={protected_branches:false,custom_branch_policies:true}`，未提供 reviewers、wait_timer 或 secrets。
- POST 创建 branch policy，实际请求 `{name:"main",type:"branch"}`；GitHub 返回的 policy ID 为 `62361648`。environment protection rule ID `68105717`（类型 `branch_policy`）。
- 消费方 API 回读：environment 于 `2026-10-08T11:26:09Z`；策略列表于 `11:26:10Z`；按 API 列表返回的 ID 获取单条策略于 `11:26:11Z`。
- Environment URL：<https://api.github.com/repos/zlxlabs/wecom-notifier/environments/pypi>；HTML URL：<https://github.com/zlxlabs/wecom-notifier/deployments/activity_log?environments_filter=pypi>。
- Policy list URL：<https://api.github.com/repos/zlxlabs/wecom-notifier/environments/pypi/deployment-branch-policies>；单条 policy URL：<https://api.github.com/repos/zlxlabs/wecom-notifier/environments/pypi/deployment-branch-policies/62361648>。
- 白名单回读字段：environment `id/name/url/html_url/created_at/updated_at/deployment_branch_policy/protection_rules`；policy `id/name/type`。最终唯一 policy 为 `62361648 / main / branch`；策略标志为 `false / true`。无 required-reviewers 或 wait-timer protection rule。

## 行为检查与边界
- 基于消费者实际回读结构化检查：`branch main` 可通过；非 main `branch release` 拒绝；`tag main` 拒绝。唯一精确名称 `main` 无 wildcard，policy type 为 `branch`。
- 检查是基于已回读 GitHub 状态的策略判定，不是实际部署执行；没有触发 deployment、workflow、PyPI 上传、tag 或 GitHub Release，因此不代表已发行。
- 官方 schema 来源（读取并缓存于本次 dispatch artifacts）：[Create or update an environment](https://docs.github.com/en/rest/deployments/environments)；[Deployment branch policies](https://docs.github.com/en/rest/deployments/branch-policies)。
