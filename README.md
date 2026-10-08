# 多平台通知器 (WeComNotifier / FeishuNotifier)

一个功能完善的多平台机器人通知组件，专为 Python 项目设计，支持**企业微信**和**飞书**双平台，提供频率控制、长文本自动分段、多webhook并发管理等高级功能。

## ✨ 特性

### 🌐 多平台支持（v0.3.0+）
- **企业微信 (WeComNotifier)** - 完整支持 text、markdown_v2、image
- **飞书 (FeishuNotifier)** - 支持文本和卡片消息，双层频率控制（100次/分+5次/秒）

### 🚀 核心能力
- 🚀 **多webhook并发管理** - 每个webhook独立队列和频率控制，互不影响
- 🌟 **Webhook池负载均衡** - 突破单webhook频率限制，3个webhook可达60条/分钟，理论无上限
- ⏱️ **智能频率控制** - 企微20条/分钟，飞书100条/分钟+5条/秒双层控制
- 🔐 **跨程序频控保护** - 即使webhook被其他程序触发频控，也能自动等待并重试
- ✂️ **长通知有界分段** - 按企微消息字段与飞书完整请求体限制拆分，保留正文并分页
- 🎯 **@功能增强** - 企微支持@all workaround，飞书支持@所有人和@指定用户
- 🔄 **同步/异步模式** - 灵活选择发送模式
- 🛡️ **智能重试机制** - 网络错误（指数退避）和频率限制分别处理
- 🔒 **内容审核功能** - 敏感词检测与处理（拒绝/替换/混淆），支持1000+敏感词高效检测
- 📋 **敏感消息日志** - 自动记录包含敏感词的消息，支持日志轮转
- 📊 **详细日志记录** - 完整的调试和错误日志

## 📦 安装

### 从PyPI安装（未来发布后）

```bash
pip install wecom-notifier
```

### 从源码安装（当前）

```bash
# 克隆仓库
git clone https://github.com/yourusername/wecom-notifier.git
cd wecom-notifier

# 安装依赖
pip install -r requirements.txt

# 安装包
pip install -e .
```

### 在其他项目中使用

```bash
# 方式1：通过相对路径安装（本地开发）
pip install -e /path/to/wecom-notifier

# 方式2：通过requirements.txt
# 在你的项目的requirements.txt中添加：
-e /path/to/wecom-notifier
```

## 🚀 快速开始

### 企业微信

```python
from wecom_notifier import WeComNotifier

# 初始化通知器
notifier = WeComNotifier()

# 发送文本消息
result = notifier.send_text(
    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR-KEY",
    content="Hello, 企业微信！"
)

# 检查结果
if result.is_success():
    print("发送成功")
else:
    print(f"发送失败: {result.error}")
```

### 飞书（v0.3.0+）

```python
from wecom_notifier import FeishuNotifier

# 初始化飞书通知器
notifier = FeishuNotifier()

# 发送文本消息
result = notifier.send_text(
    webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-KEY",
    content="Hello, 飞书！"
)
result.wait()

# 发送卡片消息（支持 Markdown）
result = notifier.send_card(
    webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-KEY",
    content="## 标题\n\n这是卡片内容",
    title="通知标题"
)
result.wait()
```

### 发送Markdown消息

```python
markdown_content = """# 项目部署通知

## 更新内容
- 新增用户导出功能
- 修复登录超时问题

| 测试项 | 结果 |
|--------|------|
| 单元测试 | ✅ 通过 |
| 集成测试 | ✅ 通过 |
"""

result = notifier.send_markdown(
    webhook_url=WEBHOOK_URL,
    content=markdown_content,
    mention_all=True,  # 自动追加@all
    async_send=False   # 同步等待
)
```

### 发送图片

```python
# 通过文件路径
result = notifier.send_image(
    webhook_url=WEBHOOK_URL,
    image_path="report.png",
    mention_all=True
)

# 或通过base64
result = notifier.send_image(
    webhook_url=WEBHOOK_URL,
    image_base64="your-base64-string",
    mention_all=True
)
```

### @特定用户

```python
result = notifier.send_text(
    webhook_url=WEBHOOK_URL,
    content="紧急通知！",
    mentioned_list=["user1", "user2", "@all"],  # @指定用户或所有人
    mentioned_mobile_list=["13800138000"]  # 也可以通过手机号@
)
```

## 📖 高级用法

### 并发发送

```python
notifier = WeComNotifier()

# 异步发送多条消息
results = []
for i in range(10):
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content=f"消息 {i}",
        async_send=True  # 异步发送，立即返回
    )
    results.append(result)

# 等待所有消息发送完成
for result in results:
    result.wait()  # 阻塞直到完成
    print(f"状态: {'成功' if result.is_success() else '失败'}")
```

### 多Webhook管理

#### 方式1：向不同群组发送

```python
notifier = WeComNotifier()

webhooks = {
    "group1": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY1",
    "group2": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY2",
}

# 向不同群组发送消息（自动管理频率限制）
for name, url in webhooks.items():
    notifier.send_text(
        webhook_url=url,
        content=f"发送到 {name}"
    )
```

#### 方式2：Webhook池 - 突破频率限制（新功能）

```python
notifier = WeComNotifier()

# 在同一个群聊中添加多个机器人，获取多个webhook地址
webhook_pool = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY1",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY2",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY3"
]

# 传入列表，系统自动负载均衡
result = notifier.send_text(
    webhook_url=webhook_pool,  # 传入列表
    content="批量数据推送..." * 100,
    async_send=False
)

# 查看使用情况
print(f"使用的webhooks: {len(result.used_webhooks)}")
print(f"分段数: {result.segment_count}")
```

**性能提升**：
- 单webhook：20条/分钟
- 3个webhook池：60条/分钟
- 10个webhook池：200条/分钟
- **理论无上限**（添加更多webhook）

### 自定义配置

```python
notifier = WeComNotifier(
    max_retries=5,        # 最大重试次数
    retry_delay=3.0       # 重试延迟（秒）
)
```

### 日志配置

**重要变更（v0.2.0+）**：本库不再自动配置日志，由用户完全控制。

#### Webhook 凭据与诊断日志

本库的企微、飞书日志使用稳定的 `webhook_id` 识别实例，不记录 webhook URL 或其前缀；HTTP 请求仍使用调用方提供的原始 URL。库产生的 `SendResult.error` 与发送失败日志不包含第三方提供的自由文本错误回显，只保留可定位的错误类别/API 错误码。异常日志不输出原始异常文本或堆栈，以免 loguru 的诊断变量再次带出凭据。

上述保护只覆盖本库主动生成的日志和错误。应用自己的日志、第三方 HTTP/监控库或自定义 sink 若自行记录 URL、请求/响应或异常，仍由应用负责安全配置；不要把 webhook 地址传入应用日志。若凭据曾出现在日志或其他输出中，请使用方立即轮换对应 webhook key，并按自身日志保留策略清理历史副本；本库无法收回已经泄露的凭据。

#### 方式1：使用库提供的快速配置（推荐新手）

```python
from wecom_notifier import WeComNotifier, setup_logger

# 在创建 notifier 之前配置日志
setup_logger(log_level="INFO")  # 输出到控制台

# 或同时输出到文件
setup_logger(
    log_level="DEBUG",
    add_console=True,
    add_file=True,
    log_file="wecom.log"
)

notifier = WeComNotifier()
```

#### 方式2：在应用层统一配置（推荐生产环境）

```python
from loguru import logger
from wecom_notifier import WeComNotifier

# 配置应用的全局日志（包括本库）
logger.add(
    "app.log",
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    # 可选：只记录本库的日志
    filter=lambda record: record["extra"].get("library") == "wecom_notifier"
)

notifier = WeComNotifier()
```

#### 方式3：完全静默（不输出日志）

```python
from wecom_notifier import WeComNotifier, disable_logger

disable_logger()  # 完全禁用本库日志
notifier = WeComNotifier()
```

#### 动态调整日志级别

```python
from loguru import logger

# 方式1：禁用/启用
from wecom_notifier import disable_logger, enable_logger
disable_logger()  # 禁用
enable_logger()   # 重新启用

# 方式2：通过环境变量
# export LOGURU_LEVEL=DEBUG

# 方式3：移除所有 handler 重新配置
logger.remove()
logger.add(sys.stdout, level="WARNING")
```

### 超长文本处理

```python
# 自动分段发送
long_text = "\n".join([f"第 {i} 行" for i in range(1000)])

result = notifier.send_text(
    webhook_url=WEBHOOK_URL,
    content=long_text,
    async_send=False
)
# text 按 UTF-8 字节数不超过 2048；markdown_v2 使用不超过 3800 字节缓冲预算
# 自动补充页码，最终预算包含页码与格式保护字符
```

### 表格智能分段

```python
# 对于超长Markdown表格，会保留表头分段
table_markdown = """
| 姓名 | 年龄 | 地址 |
|------|------|------|
""" + "\n".join([f"| 用户{i} | {20+i} | 城市{i} |" for i in range(100)])

result = notifier.send_markdown(
    webhook_url=WEBHOOK_URL,
    content=table_markdown
)
# 可容纳的表格续页重复表头，并添加续页提示
```

超长 Markdown 表头或单行无法完整容纳时，会按文本切分而不是删正文；代码块跨页时补齐独立行围栏，并在每页闭围栏前加一个 LF 以保证语法闭合，该 LF 计入预算。需要恢复代码正文时，仅移除这条明确的分页边界 LF，不全局归一化其他空白；缩进与输入换行保留。飞书自定义机器人的 20 KB 限制作用于完整请求体，包含卡片标题、包装、签名和正文；发送前会按实际 requests JSON 序列化结果预检每页。企微 text/markdown_v2 的官方字段限制分别为 2048/4096 UTF-8 字节，详见 [平台限制与计量口径](docs/sessions/261008-notifier-rootfix/platform-limits.md)。

如果本地无法生成符合预算的发送计划，`SendResult.success` 为 `False`，`error` 带 `MESSAGE_SEGMENT_OVERSIZE`，且不会发出请求。若网络或平台在多段发送中途拒绝，之前被接受的段不会回滚，整体结果仍失败。分段完整送达才报告成功。

### 内容审核功能（可选）

**适用场景：需要对发送内容进行敏感词检测和处理**

#### 功能特性

- ✅ **高性能检测** - AC自动机算法，支持1000+敏感词，检测时间< 1ms
- ✅ **三种策略** - 拒绝发送（Block）、替换（Replace）、拼音混淆（PinyinReverse）
- ✅ **灵活配置** - 从URL加载敏感词，支持本地缓存，启动时自动更新
- ✅ **自动日志** - 记录包含敏感词的消息到JSON Lines文件，便于审计追溯
- ✅ **大小写不敏感** - 自动处理大小写变体
- ✅ **部分匹配** - 子串匹配，覆盖更全面

#### 快速开始

```python
notifier = WeComNotifier(
    enable_content_moderation=True,  # 启用内容审核
    moderation_config={
        "sensitive_word_urls": [
            "http://example.com/sensitive_words1.txt",
            "http://example.com/sensitive_words2.txt"
        ],
        "strategy": "replace",  # block | replace | pinyin_reverse
    }
)

# 发送消息时会自动审核
result = notifier.send_text(
    webhook_url=WEBHOOK_URL,
    content="包含敏感词的消息内容"
)
```

#### 三种审核策略

**1. Block策略 - 拒绝发送**
```python
moderation_config={
    "strategy": "block",  # 检测到敏感词直接拒绝
}

# 包含敏感词的消息会被拒绝
# 自动发送提示消息：⚠️ 敏感内容已拦截
```

**2. Replace策略 - 替换为[敏感词]**
```python
moderation_config={
    "strategy": "replace",  # 替换为固定字符串
}

# 原文："这是关于梭哈买房的讨论"
# 发送："这是关于[敏感词]的讨论"
```

**3. PinyinReverse策略 - 拼音/字母倒置**
```python
moderation_config={
    "strategy": "pinyin_reverse",  # 混淆处理
}

# 中文：拼音首字母倒置
# "梭哈结婚" → "hsjh"（suo ha jie hun → h s j h → hsjh）

# 英文：字母倒置
# "test" → "tset"
```

#### 敏感词文件格式

```txt
# sensitive_words.txt
# 这是注释行，会被忽略

梭哈买房
供养者思维
力工梭哈

# 支持中英文
test word
another
```

**格式要求**：
- 每行一个词
- 自动去除空行和首尾空格
- 支持 `#` 开头的注释行

#### 敏感消息日志

启用审核后，包含敏感词的消息会自动记录到日志文件：

```python
moderation_config={
    "sensitive_word_urls": [...],
    "strategy": "replace",

    # 日志配置（可选，默认启用）
    "log_sensitive_messages": True,  # 是否记录敏感消息
    "log_file": ".wecom_cache/moderation.log",  # 日志文件路径
    "log_max_bytes": 10 * 1024 * 1024,  # 单个文件最大10MB
    "log_backup_count": 5,  # 保留5个备份文件
}
```

**日志格式（JSON Lines）**：
```json
{"timestamp": "2025-10-29 17:53:39.140", "message_id": "2b81f971-xxx", "strategy": "replace", "msg_type": "text", "detected_words": ["梭哈结婚"], "original_content": "这是第一条关于梭哈结婚的测试消息"}
{"timestamp": "2025-10-29 17:53:55.844", "message_id": "8a76eda2-xxx", "strategy": "block", "msg_type": "text", "detected_words": ["供养者思维", "梭哈买房"], "original_content": "这是关于梭哈买房和供养者思维的讨论"}
```

**查询日志**：
```bash
# 查看所有敏感消息
cat .wecom_cache/moderation.log

# 查找特定消息ID
grep "2b81f971" .wecom_cache/moderation.log

# 使用jq查询（需安装jq）
cat .wecom_cache/moderation.log | jq 'select(.strategy == "block")'
```

#### 完整配置示例

```python
from wecom_notifier import WeComNotifier

notifier = WeComNotifier(
    # 基础配置
    max_retries=3,
    retry_delay=2.0,
    log_level="INFO",

    # 启用内容审核
    enable_content_moderation=True,
    moderation_config={
        # 敏感词来源（必需）
        "sensitive_word_urls": [
            "http://example.com/words1.txt",
            "http://example.com/words2.txt"
        ],

        # 审核策略（必需）
        "strategy": "replace",  # block | replace | pinyin_reverse

        # 缓存配置（可选）
        "cache_dir": ".wecom_cache",  # 默认值
        "url_timeout": 10,  # 默认10秒

        # 日志配置（可选）
        "log_sensitive_messages": True,  # 默认True
        "log_file": ".wecom_cache/moderation.log",  # 默认路径
        "log_max_bytes": 10 * 1024 * 1024,  # 默认10MB
        "log_backup_count": 5,  # 默认5个备份
    }
)

# 正常使用，审核过程对用户透明
result = notifier.send_text(
    webhook_url=WEBHOOK_URL,
    content="你的消息内容"
)
```

#### 注意事项

1. **默认不启用** - 需显式设置 `enable_content_moderation=True`
2. **启动时加载** - 敏感词在系统启动时从URL加载，失败时使用缓存
3. **审核时机** - 在消息分段后、发送前进行审核
4. **日志安全** - 日志文件包含敏感信息，请注意权限控制和定期清理
5. **性能影响** - AC自动机算法性能优异，对发送速度几乎无影响

## 🏗️ 架构设计

### 多平台架构（v0.3.0+）

```
wecom_notifier/
├── core/                    # 平台无关核心
│   ├── protocols.py         # 协议定义 (SenderProtocol, RateLimiterProtocol)
│   ├── pool_base.py         # 通用调度基类
│   ├── segmenter.py         # 消息分段器
│   ├── rate_limiter.py      # 频率控制器
│   └── moderation/          # 内容审核模块
├── platforms/
│   ├── wecom/               # 企业微信实现
│   │   ├── notifier.py      # WeComNotifier
│   │   ├── sender.py        # HTTP 发送器
│   │   └── ...
│   └── feishu/              # 飞书实现
│       ├── notifier.py      # FeishuNotifier
│       ├── sender.py        # HTTP 发送器（含签名）
│       ├── rate_limiter.py  # 双层频率控制器
│       └── ...
└── *.py                     # 向后兼容重导出层
```

### 企微单Webhook模式

```
WeComNotifier (主类)
    ↓
WebhookManager (每个webhook一个实例)
    ↓
├── RateLimiter (频率控制：20条/分钟)
├── MessageSegmenter (智能分段)
└── Sender (HTTP发送 + 重试)
```

### 企微Webhook池模式

```
WeComNotifier (主类)
    ↓
WebhookPool (webhook池管理器)
    ↓
├── WebhookResource 1~N (各自独立频控)
├── Scheduler (单线程调度器 - 保证顺序)
├── MessageSegmenter (智能分段)
└── Sender (HTTP发送 + 重试)
```

### 飞书架构

```
FeishuNotifier (主类)
    ↓
_FeishuWebhookManager (每个webhook一个实例)
    ↓
├── DualRateLimiter (双层频控：100条/分钟 + 5条/秒)
├── MessageSegmenter (智能分段)
└── FeishuSender (HTTP发送 + 签名校验)
```

**关键设计**：
- **协议抽象**：SenderProtocol、RateLimiterProtocol 实现平台解耦
- **全局RateLimiter共享**：同一webhook在单/池模式下共享频控
- **单线程串行处理**：严格保证消息顺序
- **向后完全兼容**：所有 v0.2.x 代码无需修改

### 核心特性说明

#### 1. 频率控制（双层保护）

本组件采用**双层频率控制**机制，确保即使webhook被其他程序触发频控，消息也能最终送达：

**本地预防性控制**：
- 使用滑动窗口算法，默认限制20条/分钟
- 每个webhook独立队列和限制
- 自动阻塞等待，避免触发服务端限制

**服务端频控智能重试**：
- 如果收到企业微信的频控错误（45009），说明webhook可能被其他程序刷爆
- 自动等待65秒后重试（足够让频控窗口过期）
- 最多重试5次，总计等待约5分钟
- 与网络错误重试分开处理（网络错误使用指数退避）

**示例场景**：
假设你的webhook被另一个监控程序每分钟发送20条消息，已达到频控上限。
当你的程序尝试发送消息时：
1. 第一条消息会触发服务端频控（45009错误）
2. 自动等待65秒（让频控窗口过期）
3. 重试发送，成功
4. 后续消息通过本地频控器，以20条/分钟的速率顺利发送

**发送边界**：按既有频控/重试策略发送；库不承诺远端必达或多段原子性。中途失败时 `SendResult` 为失败，已接受的前段不会回滚。

#### 2. 智能分段
- **文本**: 按行分割，尽量填满每段
- **Markdown**:
  - 可容纳的链接、图片、代码块按原文保留；超长不可分行按文本切分
  - 可容纳的表格续页重复表头；超长单行按文本降级
  - 跨页代码块补齐独立行围栏，添加并计费一条边界 LF 与页码提示

#### 3. 消息顺序保证
- 同一消息的分段连续发送
- 不同消息按入队顺序处理
- 多webhook互不影响

#### 4. 错误处理
- 网络错误：自动重试（指数退避）
- Webhook无效：立即失败并返回错误
- 本地计划非法：首次 HTTP 前失败；远端分段失败：立即停止并报告失败，不宣称已发送前段被撤回

## 📋 API 参考

### WeComNotifier（企业微信）

#### 初始化参数

```python
WeComNotifier(
    max_retries=3,         # HTTP请求最大重试次数
    retry_delay=2.0        # 重试延迟（秒）
)
```

**注意**：v0.2.0+ 已移除 `log_level` 参数，请使用 `setup_logger()` 函数配置日志。

#### send_text()

```python
send_text(
    webhook_url: str,                    # Webhook地址
    content: str,                        # 文本内容
    mentioned_list: List[str] = None,    # @的用户ID列表
    mentioned_mobile_list: List[str] = None,  # @的手机号列表
    async_send: bool = True              # 是否异步发送
) -> SendResult
```

#### send_markdown()

```python
send_markdown(
    webhook_url: str,      # Webhook地址
    content: str,          # Markdown内容
    mention_all: bool = False,  # 是否@所有人
    async_send: bool = True     # 是否异步发送
) -> SendResult
```

#### send_image()

```python
send_image(
    webhook_url: str,              # Webhook地址
    image_path: str = None,        # 图片文件路径
    image_base64: str = None,      # 图片base64编码（二选一）
    mention_all: bool = False,     # 是否@所有人
    async_send: bool = True        # 是否异步发送
) -> SendResult
```

### FeishuNotifier（飞书，v0.3.0+）

#### 初始化参数

```python
FeishuNotifier(
    max_retries=3,         # HTTP请求最大重试次数
    retry_delay=2.0,       # 重试延迟（秒）
    secret=None            # 签名密钥（如机器人启用签名校验）
)
```

#### send_text()

```python
send_text(
    webhook_url: str,              # Webhook地址
    content: str,                  # 文本内容
    mention_all: bool = False,     # 是否@所有人
    mentions: List[str] = None,    # 要@的用户ID列表
    async_send: bool = True        # 是否异步发送
) -> SendResult
```

#### send_card()

```python
send_card(
    webhook_url: str,              # Webhook地址
    content: str,                  # Markdown内容
    title: str = "通知",           # 卡片标题
    template: str = "blue",        # 卡片模板颜色
    async_send: bool = True        # 是否异步发送
) -> SendResult
```

**飞书卡片模板颜色**：blue, wathet, turquoise, green, yellow, orange, red, carmine, violet, purple, indigo, grey

### SendResult

```python
result.message_id        # 消息ID
result.is_success()      # 是否成功
result.error             # 错误信息（如果失败）
result.wait(timeout)     # 等待发送完成（异步模式）
```

## 🔍 常见问题

### Q: 如何在多个项目中共享此组件？

**A:** 有以下几种方式：

1. **本地开发模式**（推荐用于开发）：
   ```bash
   pip install -e /path/to/wecom-notifier
   ```

2. **发布到PyPI**（推荐用于生产）：
   ```bash
   # 构建
   python setup.py sdist bdist_wheel
   # 上传
   twine upload dist/*
   # 在其他项目中安装
   pip install wecom-notifier
   ```

3. **Git子模块**：
   ```bash
   git submodule add https://github.com/yourusername/wecom-notifier.git
   pip install -e ./wecom-notifier
   ```

### Q: 如何更新其他项目中的此组件？

**A:**
- 如果使用 `pip install -e`：组件代码自动同步
- 如果从PyPI安装：`pip install --upgrade wecom-notifier`
- 如果使用git子模块：`git submodule update --remote`

### Q: 消息发送顺序会乱吗？

**A:** 不会。同一消息的分段保证连续发送，不会被其他消息插入。

### Q: 如果超过20条/分钟会怎样？

**A:** 本地频率控制器会自动等待，确保不超过20条/分钟的速率。

### Q: 如果webhook已经被其他程序刷爆了怎么办？

**A:** 组件会自动处理：
1. 检测到服务端频控错误（45009）
2. 等待65秒让频控窗口过期
3. 自动重试（最多5次）
4. 确保消息最终送达

**核心设计理念**：不管webhook之前是什么状态（即使被其他程序触发频控），只要调用本组件，消息就一定会成功发送（最多等待约5分钟）。

### Q: 如何突破单webhook的频率限制？

**A:** 使用**Webhook池**功能（v2.0新增）

```python
notifier = WeComNotifier()

# 在同一个群聊中添加多个机器人webhook
webhook_pool = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY1",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY2",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY3"
]

# 传入列表即可，系统自动负载均衡
notifier.send_text(webhook_url=webhook_pool, content="消息")
```

**性能提升**：
- 1个webhook：20条/分钟
- 3个webhook：60条/分钟
- 10个webhook：200条/分钟

**关键特性**：
- ✅ 严格保证消息顺序
- ✅ 智能负载均衡（最空闲优先）
- ✅ 自动容错恢复
- ✅ 完全向后兼容

### Q: 可以创建多个 WeComNotifier 实例吗？

**A:** 技术上可以，但**强烈不推荐**针对同一个 webhook 创建多个实例。

**推荐做法（单例模式）**：
```python
# 在应用启动时创建一个全局实例
notifier = WeComNotifier()

# 在整个应用中复用这个实例
notifier.send_text(webhook_url, "消息1")
notifier.send_text(webhook_url, "消息2")
```

**不推荐做法**：
```python
# ❌ 每次都创建新实例
def send_msg():
    notifier = WeComNotifier()  # 会创建新的工作线程
    notifier.send_text(webhook_url, "消息")
```

**原因**：
- 每个实例会为每个 webhook 创建独立的工作线程和频控器
- 多个实例无法协调频率限制，容易触发服务端频控
- 造成资源浪费和消息顺序混乱

详见 [USAGE_GUIDE.md](USAGE_GUIDE.md) 的最佳实践部分。

### Q: 支持哪些Python版本？

**A:** Python 3.7+

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

- 项目主页: https://github.com/yourusername/wecom-notifier
- 问题反馈: https://github.com/yourusername/wecom-notifier/issues

## 🙏 致谢

感谢企业微信开放平台提供的API文档。
