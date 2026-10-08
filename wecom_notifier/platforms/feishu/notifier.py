"""
飞书通知器

提供简洁的 API 发送飞书消息，支持：
- 文本消息
- 卡片消息（Markdown 内容）
- @ 功能
- 频率控制
- 签名校验（可选）
"""
import threading
import queue
import time
from typing import Optional, List, Union, Dict, Any

from wecom_notifier.core.logger import get_logger
from wecom_notifier.core.models import SendResult
from wecom_notifier.core.segmenter import MessageSegmenter, MessageSegmentOversizeError
from wecom_notifier.core.webhook_identity import webhook_identity

from .sender import FeishuSender, FeishuRetryConfig
from .rate_limiter import DualRateLimiter
from .constants import (
    MSG_TYPE_TEXT,
    MSG_TYPE_INTERACTIVE,
    MAX_BYTES_PER_MESSAGE,
    _MAX_REQUEST_BODY_BYTES,
    DEFAULT_CARD_TEMPLATE,
)


class FeishuMessage:
    """飞书消息对象"""

    def __init__(
        self,
        content: str,
        msg_type: str,
        title: Optional[str] = None,
        template: str = DEFAULT_CARD_TEMPLATE,
        mention_all: bool = False,
        mentions: Optional[List[str]] = None,
        segment_interval: int = 200  # 飞书分段间隔可以更短
    ):
        import uuid
        self.id = str(uuid.uuid4())
        self.content = content
        self.msg_type = msg_type
        self.title = title or "通知"
        self.template = template
        self.mention_all = mention_all
        self.mentions = mentions or []
        self.segment_interval = segment_interval

    def needs_mention_all_workaround(self) -> bool:
        """飞书不需要 @all workaround，直接在文本中处理"""
        return False


class FeishuNotifier:
    """
    飞书通知器

    使用示例:
        notifier = FeishuNotifier()
        webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

        # 发送文本
        result = notifier.send_text(webhook, "Hello, Feishu!")
        result.wait()

        # 发送卡片
        result = notifier.send_card(
            webhook,
            content="# 标题\\n\\n内容",
            title="通知标题"
        )
        result.wait()
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        secret: Optional[str] = None
    ):
        """
        初始化飞书通知器

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            secret: 签名密钥（如果机器人启用了签名校验）
        """
        self.logger = get_logger()

        # 核心组件
        self.segmenter = MessageSegmenter(max_bytes=MAX_BYTES_PER_MESSAGE)
        self.sender = FeishuSender(
            retry_config=FeishuRetryConfig(
                max_retries=max_retries,
                retry_delay=retry_delay
            ),
            secret=secret
        )

        # 管理器缓存（每个 webhook 一个）
        self._managers: Dict[str, "_FeishuWebhookManager"] = {}
        self._managers_lock = threading.Lock()

        self.logger.info("FeishuNotifier initialized")

    def send_text(
        self,
        webhook_url: str,
        content: str,
        mention_all: bool = False,
        mentions: Optional[List[str]] = None,
        async_send: bool = True
    ) -> SendResult:
        """
        发送文本消息

        Args:
            webhook_url: Webhook 地址
            content: 文本内容
            mention_all: 是否 @ 所有人
            mentions: 要 @ 的用户 ID 列表
            async_send: 是否异步发送

        Returns:
            SendResult: 发送结果
        """
        message = FeishuMessage(
            content=content,
            msg_type=MSG_TYPE_TEXT,
            mention_all=mention_all,
            mentions=mentions
        )

        return self._send_message(webhook_url, message, async_send)

    def send_card(
        self,
        webhook_url: str,
        content: str,
        title: str = "通知",
        template: str = DEFAULT_CARD_TEMPLATE,
        async_send: bool = True
    ) -> SendResult:
        """
        发送卡片消息（使用 Markdown 内容）

        Args:
            webhook_url: Webhook 地址
            content: Markdown 内容
            title: 卡片标题
            template: 卡片模板颜色
            async_send: 是否异步发送

        Returns:
            SendResult: 发送结果
        """
        message = FeishuMessage(
            content=content,
            msg_type=MSG_TYPE_INTERACTIVE,
            title=title,
            template=template
        )

        return self._send_message(webhook_url, message, async_send)

    def _send_message(
        self,
        webhook_url: str,
        message: FeishuMessage,
        async_send: bool = True
    ) -> SendResult:
        """
        发送消息

        Args:
            webhook_url: Webhook 地址
            message: 消息对象
            async_send: 是否异步发送

        Returns:
            SendResult: 发送结果
        """
        manager = self._get_or_create_manager(webhook_url)
        result = manager.enqueue(message)

        if not async_send:
            result.wait()

        return result

    def _get_or_create_manager(self, webhook_url: str) -> "_FeishuWebhookManager":
        """获取或创建 webhook 管理器"""
        with self._managers_lock:
            if webhook_url not in self._managers:
                self._managers[webhook_url] = _FeishuWebhookManager(
                    webhook_url=webhook_url,
                    sender=self.sender,
                    segmenter=self.segmenter
                )
            return self._managers[webhook_url]

    def stop_all(self):
        """停止所有 Webhook 管理器"""
        with self._managers_lock:
            for manager in self._managers.values():
                manager.stop()

    def __del__(self):
        """析构函数"""
        if hasattr(self, '_managers'):
            self.stop_all()


class _FeishuWebhookManager:
    """
    飞书 Webhook 管理器

    管理单个 webhook 的消息队列和发送。
    """

    def __init__(
        self,
        webhook_url: str,
        sender: FeishuSender,
        segmenter: MessageSegmenter
    ):
        self.logger = get_logger()
        self.webhook_url = webhook_url
        self.sender = sender
        self.segmenter = segmenter
        self.rate_limiter = DualRateLimiter()

        # 消息队列
        self.message_queue: queue.Queue = queue.Queue()
        self.results: Dict[str, SendResult] = {}

        # 停止标志
        self._stop_flag = threading.Event()

        # 工作线程
        self.worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self.worker_thread.start()

        self.logger.info(
            f"FeishuWebhookManager initialized "
            f"(webhook_id={webhook_identity(webhook_url)})"
        )

    def enqueue(self, message: FeishuMessage) -> SendResult:
        """将消息加入队列"""
        result = SendResult(message.id)
        self.results[message.id] = result
        self.message_queue.put(message)

        self.logger.debug(
            f"Feishu message {message.id} enqueued (type={message.msg_type})"
        )
        return result

    def _process_queue(self):
        """处理消息队列"""
        self.logger.info(
            f"Feishu worker thread started "
            f"(webhook_id={webhook_identity(self.webhook_url)})"
        )

        while not self._stop_flag.is_set():
            try:
                message = self.message_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self._process_message(message)
            except Exception as e:
                self.logger.error(
                    f"Error processing Feishu message {message.id} "
                    f"({type(e).__name__})"
                )
                result = self.results.get(message.id)
                if result:
                    result.mark_failed(f"Internal error ({type(e).__name__})")
            finally:
                self.message_queue.task_done()

    def _process_message(self, message: FeishuMessage):
        """处理单条消息"""
        result = self.results.get(message.id)
        if not result:
            self.logger.error(f"Result not found for Feishu message {message.id}")
            return

        self.logger.info(
            f"Processing Feishu message {message.id} (type={message.msg_type})"
        )

        # 处理 @ 功能
        content = message.content
        if message.msg_type == MSG_TYPE_TEXT:
            content = self._add_mentions(content, message)

        # 分段、分页标题与请求体统一预检，任一不可行计划均在首个 POST 前失败。
        try:
            plans = self._plan_segments(message, content)
        except MessageSegmentOversizeError as error:
            result.mark_failed(str(error))
            return
        total_segments = len(plans)

        self.logger.debug(
            f"Feishu message {message.id} split into {total_segments} segments"
        )

        # 发送每个分段
        for i, (segment, page_title) in enumerate(plans):
            # 频率控制
            self.rate_limiter.acquire()

            # 发送
            if message.msg_type == MSG_TYPE_TEXT:
                success, error = self.sender.send_text(
                    self.webhook_url,
                    segment.content
                )
            else:  # MSG_TYPE_INTERACTIVE
                success, error = self.sender.send_card(
                    self.webhook_url,
                    segment.content,
                    title=page_title,
                    template=message.template
                )

            if success:
                self.logger.debug(
                    f"Feishu segment {i + 1}/{total_segments} sent for message {message.id}"
                )
            else:
                safe_error = error or "send failed"
                self.logger.error(
                    f"Feishu segment {i + 1}/{total_segments} failed: {safe_error}"
                )
                result.mark_failed(safe_error)
                return

            # 分段间延迟
            if i < total_segments - 1:
                time.sleep(message.segment_interval / 1000.0)

        # 成功
        result.segment_count = total_segments
        result.mark_success()

        self.logger.info(
            f"Feishu message {message.id} sent successfully ({total_segments} segments)"
        )

    def _plan_segments(self, message: FeishuMessage, content: str):
        if message.msg_type == MSG_TYPE_TEXT:
            base_size = self.sender._text_body_size(self.webhook_url, "")
            budget = _MAX_REQUEST_BODY_BYTES - base_size
            if budget <= 0:
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: Feishu request envelope exceeds budget")
            segments = self.segmenter._segment_bounded(
                content,
                MSG_TYPE_TEXT,
                budget,
                measure=self.sender._content_wire_size,
            )
            plans = [(segment, None) for segment in segments]
            if any(self.sender._text_body_size(self.webhook_url, segment.content) > _MAX_REQUEST_BODY_BYTES
                   for segment, _ in plans):
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: Feishu text request exceeds budget")
            return plans

        page_guess = 1
        while True:
            titles = [
                message.title if page_guess == 1 else f"{message.title} ({page}/{page_guess})"
                for page in range(1, page_guess + 1)
            ]
            base_size = max(
                self.sender._card_body_size(self.webhook_url, "", title, message.template)
                for title in titles
            )
            budget = _MAX_REQUEST_BODY_BYTES - base_size
            if budget <= 0:
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: Feishu card header exceeds request budget")
            segments = self.segmenter._segment_bounded(
                content,
                "interactive",
                budget,
                measure=self.sender._content_wire_size,
            )
            total = len(segments)
            if total != page_guess:
                page_guess = total
                continue
            plans = []
            for page, segment in enumerate(segments, start=1):
                title = message.title if total == 1 else f"{message.title} ({page}/{total})"
                if self.sender._card_body_size(
                    self.webhook_url, segment.content, title, message.template
                ) > _MAX_REQUEST_BODY_BYTES:
                    raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: Feishu card request exceeds budget")
                plans.append((segment, title))
            return plans

    def _add_mentions(self, content: str, message: FeishuMessage) -> str:
        """添加 @ 标签"""
        at_tags = []

        if message.mention_all:
            at_tags.append("<at user_id=\"all\">所有人</at>")

        for user_id in message.mentions:
            if user_id == "all":
                if "<at user_id=\"all\">" not in " ".join(at_tags):
                    at_tags.append("<at user_id=\"all\">所有人</at>")
            else:
                at_tags.append(f"<at user_id=\"{user_id}\"></at>")

        if at_tags:
            return " ".join(at_tags) + " " + content

        return content

    def stop(self):
        """停止管理器"""
        self.logger.info(
            f"Stopping FeishuWebhookManager "
            f"(webhook_id={webhook_identity(self.webhook_url)})"
        )
        self._stop_flag.set()
        self.worker_thread.join(timeout=5)


__all__ = ["FeishuNotifier", "FeishuMessage"]
