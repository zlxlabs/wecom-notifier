# 更新日志

所有值得注意的项目更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.3.2] - Unreleased (preparation only)

### 修复（Fixed）

- 企微 text/markdown_v2 与飞书 text/interactive 的分段计划纳入页码、表头、代码围栏、标题和最终序列化预算；飞书按实际 `PreparedRequest.body` 限制完整请求体。
- 超长表格行按文本切分、普通 Markdown 链接在预算允许时整体移至下一页；超长代码块跨页补齐独立行围栏，并按每页闭围栏插入一条计入预算的边界换行。保留正文、缩进与原始换行；无法满足极小预算时以 `MESSAGE_SEGMENT_OVERSIZE` 明确失败。
- 企微逐原分段审核一次；审核输入仅剔除带元数据确认的库插入页码，审核结果再统一计算最终页序，池成功计数使用最终逻辑页数。无法本地规划的消息在首次 HTTP 前失败，中途平台拒绝则整体 `SendResult` 失败。

> 本版本仅准备构建与隔离安装验证，尚未发布、未上传 PyPI、未创建 GitHub Release。

## [0.3.1] - 2026-01-31

### 🐛 修复（Fixed）

#### 修复 FeishuNotifier 退出时未正确停止工作线程的问题

**问题描述**：
- `FeishuNotifier` 缺少 `stop_all()` 方法和 `__del__` 析构函数
- 程序退出时，飞书的 `_FeishuWebhookManager` 工作线程无法正确停止
- 与 `WeComNotifier` 行为不一致（企微有 "Stopping WebhookManager for..." 日志，飞书没有）

**修复内容**：
- 在 `FeishuNotifier` 类中添加 `stop_all()` 方法
- 添加 `__del__` 析构函数，在对象销毁时自动调用 `stop_all()`
- 现在程序退出时会正确输出 "Stopping FeishuWebhookManager for..." 日志

**技术细节**：
```python
def stop_all(self):
    """停止所有 Webhook 管理器"""
    with self._managers_lock:
        for manager in self._managers.values():
            manager.stop()

def __del__(self):
    """析构函数"""
    if hasattr(self, '_managers'):
        self.stop_all()
```

---

## [0.3.0] - 2026-01-31

### ✨ 新增（Added）

#### 飞书 (Feishu/Lark) 平台支持

新增 `FeishuNotifier` 类，提供完整的飞书机器人通知功能：

```python
from wecom_notifier import FeishuNotifier

notifier = FeishuNotifier(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx")

# 发送文本消息
notifier.send_text("Hello, Feishu!")

# 发送富文本消息
notifier.send_rich_text(
    title="通知标题",
    content=[
        [{"tag": "text", "text": "第一行内容"}],
        [{"tag": "a", "text": "链接", "href": "https://example.com"}]
    ]
)

# 发送卡片消息
notifier.send_card(
    title="卡片标题",
    elements=[
        {"tag": "div", "text": {"content": "卡片内容", "tag": "plain_text"}}
    ]
)
```

**功能特性**：
- 支持文本消息 (text)
- 支持富文本消息 (post)
- 支持交互式卡片消息 (interactive)
- 支持图片消息 (image)
- 支持 @ 用户（`@all`、手机号、`open_id`、`user_id`）
- 支持签名验证
- 双层频率限制（100次/分钟 + 5次/秒）
- 长文本自动分段

#### 多平台架构

项目重构为多平台架构：

```
wecom_notifier/
├── core/              # 共享核心模块
│   ├── rate_limiter.py    # 通用频率限制器
│   ├── segmenter.py       # 通用消息分段器
│   ├── pool_base.py       # Webhook池基类
│   └── moderation/        # 内容审核模块
├── platforms/         # 平台特定实现
│   ├── wecom/            # 企业微信
│   └── feishu/           # 飞书
└── *.py               # 向后兼容层
```

**核心抽象**：
- `RateLimiter` - 通用频率限制器，支持自定义限制策略
- `MessageSegmenter` - 消息分段器，支持 text/markdown 分段
- `WebhookPoolBase` - Webhook 池抽象基类

#### 可选的内容审核依赖

内容审核功能现在是可选的：

```bash
# 基础安装（不含审核功能）
pip install wecom-notifier

# 安装审核功能
pip install wecom-notifier[moderation]
```

使用审核功能时，如果缺少依赖会给出友好提示：
```
ConfigurationError: Content moderation requires additional dependencies.
Install with: pip install wecom-notifier[moderation]
Missing packages: pyahocorasick, pypinyin
```

### 🔄 变更（Changed）

#### 依赖优化

- `pypinyin` 和 `pyahocorasick` 从必需依赖移至可选依赖 `[moderation]`
- 基础安装更轻量，仅需 `requests` 和 `loguru`

#### 项目描述更新

- 项目描述更新为"多平台机器人通知组件"
- 添加飞书相关关键词：`feishu`、`lark`

### 📚 文档（Documentation）

- README.md 新增飞书快速入门和 API 参考
- USAGE_GUIDE.md 新增飞书章节（第10节）
- 新增多平台同时通知示例

### ✅ 兼容性（Compatibility）

- **完全向后兼容**：所有现有的导入路径和 API 保持不变
- 原有代码无需任何修改即可在 0.3.0 上运行
- `WeComNotifier` 的所有功能和参数保持一致

---

## [0.2.3] - 2026-01-02

### 🐛 修复（Fixed）

#### 修复 Markdown 分段时标题单独成页的问题

**问题描述**：
- 当 `current` 整体是一个标题时（如 `# 主题详述`），由于条件判断中 `content_without_heading` 为空字符串导致回溯失败
- 标题被单独作为一个分段输出，形成孤立的标题页

**修复内容**：
- 新增 `elif` 分支处理 `current` 整体是标题的情况
- 尝试将标题与后续段落按行合并
- 如果第一行太长无法完整合并，则按字符拆分部分合并
- 只有在极端情况（标题本身接近字节限制）才允许单独分段

#### 修复多个连续标题时回溯导致的孤立标题问题

**问题描述**：
- 当 `current` 包含多个连续标题（如 `# A\n\n# B`）时，回溯逻辑会把前面的标题 `# A` 单独分段
- 导致出现只有一个标题的孤立分段

**修复内容**：
- 新增 `_is_only_headings()` 方法：检测内容是否只包含标题（没有其他正文内容）
- 回溯前检查 `content_without_heading` 是否也只是标题
- 如果是，跳过回溯，改用标题合并逻辑处理，避免产生孤立标题

**效果对比**：
```
改进前:
分段1: 内容...
分段2: # 主题详述        ← 孤立标题页
分段3: # 主题一 + 正文...

改进后:
分段1: 内容...
分段2: # 主题详述 + # 主题一 + 正文...  ← 标题与正文合并
```

---

## [0.2.2] - 2025-12-26

### 🐛 修复（Fixed）

#### 修复表格前有文字时分段后表头丢失的问题

**问题描述**：
- 当 Markdown 内容中表格前面有文字时（如 `一些描述\n| 列1 | 列2 |`），分段后续页的表格会丢失表头
- 导致后续分段的表格无法正确渲染

**修复内容**：
- 在 `_segment_markdown()` 中添加对段落中间包含表格的检测逻辑
- 分离表格前的文字和表格部分，分别处理
- 确保表格分段时保留完整表头

#### 修复 Markdown 分段时标题与正文分离的问题

**问题描述**：
- 当分段边界恰好在 Markdown 标题（`#` 开头）之后时，标题会被孤立在上一页末尾
- 标题与其下方的正文内容被分到不同的分段，影响阅读体验

**修复内容**：
- 新增 `_is_heading()` 方法：检测 Markdown 标题（`#` 到 `######`）
- 新增 `_extract_trailing_heading()` 方法：提取当前内容末尾的标题
- 在分段逻辑中添加回溯机制：
  - 当检测到添加段落会超限时，检查当前内容末尾是否有孤立标题
  - 如果有，将标题移至下一分段，与正文保持在一起

**效果对比**：
```
改进前:
分段1: 第一段内容 + ## 标题  ← 标题孤立
分段2: 正文内容

改进后:
分段1: 第一段内容
分段2: ## 标题 + 正文内容  ← 标题与正文在一起
```

---

## [0.2.1] - 2025-11-03

### 🐛 修复（Fixed）

#### 修复依赖声明不完整问题

**问题描述**：
- 用户通过 `pip install wecom-notifier` 安装库时，会遇到 `ModuleNotFoundError: No module named 'ahocorasick'` 等错误
- 原因：`pyproject.toml` 的 `dependencies` 中只声明了 `requests`，缺少其他必需依赖

**修复内容**：
- 补全 `pyproject.toml` 中的依赖声明，添加：
  - `loguru>=0.7.0` - 日志系统核心依赖
  - `pypinyin>=0.44.0` - 敏感词拼音替换功能
  - `pyahocorasick>=2.0.0` - AC自动机算法，高效敏感词检测

**影响**：
- ✅ 用户安装库后，所有依赖会被自动安装
- ✅ 修复了导入失败的问题
- ✅ 无需手动安装额外依赖

**技术细节**：
- pip 读取 `pyproject.toml` 中的 `dependencies` 字段安装依赖
- `requirements.txt` 仅用于开发环境，不影响包的发布

---

## [0.2.0] - 2025-11-03

### ⚠️ 破坏性变更（Breaking Changes）

#### 移除 `log_level` 参数

**之前（v0.1.x）**：
```python
# ❌ 不再支持
notifier = WeComNotifier(log_level="INFO")
```

**现在（v0.2.0+）**：
```python
# ✅ 方式1：使用快速配置
from wecom_notifier import setup_logger
setup_logger(log_level="INFO")
notifier = WeComNotifier()

# ✅ 方式2：应用层统一配置
from loguru import logger
logger.add("app.log", level="INFO")
notifier = WeComNotifier()

# ✅ 方式3：完全静默
from wecom_notifier import disable_logger
disable_logger()
notifier = WeComNotifier()
```

**影响**：
- `WeComNotifier.__init__()` 不再接受 `log_level` 参数
- 现有代码需要更新日志配置方式
- 不再自动调用 `logger.remove()`，不会破坏应用的日志配置

**迁移指南**：详见 [日志配置指南](doc/logging_configuration_guide.md)

---

### ✨ 新增（Added）

#### 独立的日志模块

- **新模块**：`wecom_notifier/logger.py`
  - 提供库专属的 logger 实例（带 `library="wecom_notifier"` 标识）
  - 不污染全局日志配置

#### 日志配置函数

导出了三个便捷函数：

1. **`setup_logger()`** - 快速配置日志
   ```python
   from wecom_notifier import setup_logger

   setup_logger(
       log_level="INFO",           # 日志级别
       add_console=True,            # 控制台输出
       add_file=True,               # 文件输出
       log_file="wecom.log",        # 文件路径
       colorize=True                # 颜色支持
   )
   ```

2. **`disable_logger()`** - 禁用本库日志
   ```python
   from wecom_notifier import disable_logger
   disable_logger()
   ```

3. **`enable_logger()`** - 重新启用日志
   ```python
   from wecom_notifier import enable_logger
   enable_logger()
   ```

#### 详细的日志配置文档

- **新文档**：`doc/logging_configuration_guide.md`（15页）
  - 3种配置方式详解
  - 常见场景示例（Flask、Django、定时任务等）
  - 故障排查指南
  - 性能优化建议

---

### 🔄 变更（Changed）

#### 日志系统架构重构

**核心改进**：
- ✅ **不再破坏应用日志** - 移除了 `logger.remove()` 调用
- ✅ **用户完全控制** - 默认不配置任何日志处理器
- ✅ **库专属标识** - 所有日志带 `library="wecom_notifier"` 标识
- ✅ **遵循最佳实践** - 符合 Python 第三方库标准

**技术细节**：
- 所有模块改用 `get_logger()` 获取库专属 logger
- 使用 `logger.bind(library="wecom_notifier")` 创建隔离实例
- 支持通过 filter 精确控制日志输出

#### 所有模块日志更新

更新了以下模块使用新的 logger 系统：
- `notifier.py` - 主类
- `webhook_pool.py` - Webhook池
- `webhook_manager.py` - Webhook管理器
- `sender.py` - HTTP发送器
- `content_moderator.py` - 内容审核器
- `content_filter.py` - 内容过滤器
- `sensitive_word_loader.py` - 敏感词加载器
- `moderation_strategies.py` - 审核策略

---

### 🗑️ 移除（Removed）

- **`WeComNotifier.__init__(log_level=...)`** - 不再接受日志级别参数
- **`WeComNotifier._setup_logger()`** - 移除自动日志配置方法
- **`constants.DEFAULT_LOG_LEVEL`** - 移除默认日志级别常量

---

### 📚 文档（Documentation）

#### 新增文档

1. **日志配置指南** (`doc/logging_configuration_guide.md`)
   - 3种日志配置方式详解
   - 日志级别说明和使用场景
   - 常见场景示例（10+个实际案例）
   - 动态调整日志的多种方法
   - 与标准 logging 模块集成
   - 性能考虑和优化建议
   - 故障排查（4个常见问题）

2. **测试脚本** (`test_logging_refactor.py`)
   - 验证日志系统的5项核心功能
   - 可用于回归测试

#### 更新文档

- **README.md**
  - 新增完整的"日志配置"章节
  - 移除初始化参数中的 `log_level`
  - 更新所有代码示例

- **USAGE_GUIDE.md**
  - 新增"日志配置"章节（第10节）
  - 更新自定义配置示例
  - 更新最佳实践中的单例示例
  - 更新故障排查中的日志控制方法

- **日志最佳实践** (`doc/wecom_notifier_logging_best_practices.md`)
  - 保留原始需求分析文档
  - 记录重构的设计原则

---

### 🎯 设计原则

此次重构遵循以下第三方库日志最佳实践：

1. **库不配置日志** ✅
   - 默认情况下不调用 `logger.add()` 或 `logger.remove()`
   - 由用户在应用层完全控制

2. **使用库专属 logger** ✅
   - 所有日志带 `library="wecom_notifier"` 标识
   - 用户可通过 filter 精确控制

3. **不污染全局** ✅
   - 不修改 loguru 的全局配置
   - 不影响应用程序或其他库的日志

4. **提供便捷工具** ✅
   - 为新手用户提供 `setup_logger()` 快速配置
   - 为高级用户提供完全自由

5. **向后兼容性说明** ⚠️
   - 这是一个破坏性变更（主版本号升级 0.1.x → 0.2.0）
   - 提供详细的迁移指南
   - 旧的 `log_level` 参数不再支持

---

### 📊 测试验证

通过 `test_logging_refactor.py` 验证：
- ✅ 库不主动配置日志（遵循最佳实践）
- ✅ `setup_logger()` 正常工作
- ✅ `disable_logger()` 可以完全禁用
- ✅ `enable_logger()` 可以重新启用
- ✅ 所有日志都带有 `library='wecom_notifier'` 标识

---

### 🔗 相关资源

- [日志配置指南](doc/logging_configuration_guide.md) - 完整的配置文档
- [日志最佳实践](doc/wecom_notifier_logging_best_practices.md) - 设计原则
- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html) - 官方指南
- [Loguru 文档](https://loguru.readthedocs.io/) - loguru 使用手册

---

## [0.1.5] - 2025-10-25

### 改进
- **页码标记优化** - 将分段提示从"续上页/未完待续"改为清晰的页码格式
  - **新格式**：`(Page X/Y)` 显示在每段开头，换行符分隔
  - **智能显示**：仅当分段数 > 1 时显示页码，单段内容不显示
  - **位置固定**：页码统一放在每段开头，便于快速识别当前进度
  - **调试增强**：`SegmentInfo` 新增 `page_number` 和 `total_pages` 字段，方便日志调试

### 技术细节
- 删除旧常量：`SEGMENT_CONTINUE_PREFIX`、`SEGMENT_CONTINUE_SUFFIX`
- 新增常量：`PAGE_INDICATOR_FORMAT`、`MAX_PAGE_INDICATOR_BYTES`（预留20字节）
- 更新字节预留逻辑：从42字节（旧提示）调整为20字节（页码标记）
- 示例效果：
  ```
  (Page 1/3)
  消息内容第一段...

  (Page 2/3)
  消息内容第二段...

  (Page 3/3)
  消息内容第三段...
  ```

---

## [0.1.4] - 2025-10-21

### 修复
- **Markdown分段超限问题** - 修复 `_segment_text()` 和 `_segment_markdown()` 方法未预留续页提示空间的bug
  - **问题1**：分段时直接使用 `max_bytes`（3800字节）作为限制，但之后添加续页提示（约42字节）可能导致超过4096字节限制
  - **问题2**：在 `_segment_markdown()` 第151行，当 `current` 不为空且 `test_content` 超限时，直接将 `para` 赋给 `current`，但未检查 `para` 本身是否超过 `available_bytes`
  - **解决**：
    1. 在分段前计算 `available_bytes = max_bytes - reserved_bytes`，确保添加续页提示后不会超限
    2. 在处理段落时，增加对 `para` 本身大小的二次检查，如果 `para` 超限则进行二次分段
  - **影响**：修复了 Segment 3/8 failed 类型的 40058 错误（markdown_v2.content exceed max length 4096）

### 技术细节
- 续页提示占用：`SEGMENT_CONTINUE_PREFIX`（约18字节） + `SEGMENT_CONTINUE_SUFFIX`（约24字节） = 42字节
- 实际可用空间：3800 - 42 = 3758字节
- 与 `_segment_table()` 方法保持一致的预留空间策略
- 测试数据：25903字节文件 → 8段，最大分段3710字节，全部在4096字节限制内

---

## [0.1.1] - 2025-10-18

### 修复
- **表格分段超长问题** - 修复表格分段时未预留续页提示空间导致超过4096字节限制
- **频率控制器卡住** - 重写频率控制逻辑，使用while循环替代递归，在锁外等待避免阻塞

### 优化
- **安全阈值调整** - 将消息分段阈值从4096字节调整为3800字节，留出296字节安全余量
  - 预留空间用于：续页提示（~40字节）、表头（变长）、Markdown格式符号等
  - 避免边界情况导致超限

### 性能
- 表格分段：7166字节 → 2段，无超限错误
- 频率控制：25条消息，67.4秒，20.5条/分钟，92%成功率

---

## [0.1.0] - 2025-10-17

### 新增
- 企业微信通知器核心功能
- 支持text、markdown_v2、image三种消息格式
- 智能频率控制（20条/分钟）
- 长文本自动分段
- 表格智能分段（保留表头）
- @all功能增强（markdown_v2/image自动追加text）
- 同步/异步发送模式
- 多webhook独立管理
- 自动重试机制
- 详细日志记录

### 文档
- 完整的README
- 使用指南（USAGE_GUIDE.md）
- 测试示例
- API文档

## 0.1.2 - 2025-10-19
- 增强：跨程序频控保护 —— 当 webhook 已被其他进程/程序触发频控时，发送方可自动等待并重试（重试等待时间可控），降低偶发频控导致的失败率。

## 0.1.3 - 2025-10-19
- 新增：在同一群聊中可添加多个机器人，实现负载均衡与更高的消息吞吐。在单个 webhook 触发频控时，自动切换到其他可用机器人，进一步降低限频导致的失败率。
