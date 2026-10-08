"""
Webhook 池基类 - 通用调度逻辑

提供平台无关的消息调度能力：
- 全局消息队列（保证顺序）
- 单线程调度器（串行处理）
- 智能 webhook 选择（最空闲优先）
- 自动容错和恢复

平台特定逻辑通过抽象方法由子类实现。
"""
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Set, Tuple, Any, TYPE_CHECKING

from wecom_notifier.core.protocols import SenderProtocol, MessageConverterProtocol
from wecom_notifier.core.segmenter import MessageSegmenter, MessageSegmentOversizeError
from wecom_notifier.core.models import Message, SendResult, SegmentInfo
from wecom_notifier.core.logger import get_logger
from wecom_notifier.core.exceptions import NotificationError
from wecom_notifier.core.webhook_identity import webhook_identity

if TYPE_CHECKING:
    from wecom_notifier.webhook_resource import WebhookResource
    from wecom_notifier.core.moderation import ContentModerator


class AllWebhooksUnavailableError(NotificationError):
    """所有 webhook 都不可用"""
    pass


class WebhookPoolBase(ABC):
    """
    Webhook 池基类

    提供通用的调度逻辑，平台特定行为由子类实现。

    使用方式:
        class MyPlatformPool(WebhookPoolBase):
            def should_skip_segmentation(self, msg_type):
                return msg_type == "image"

            def should_skip_moderation(self, msg_type):
                return msg_type == "image"

            def _post_send_hook(self, message, used_webhooks):
                # 平台特定后处理
                return True
    """

    def __init__(
        self,
        resources: List["WebhookResource"],
        sender: SenderProtocol,
        segmenter: MessageSegmenter,
        converter: MessageConverterProtocol,
        content_moderator: Optional["ContentModerator"] = None
    ):
        """
        初始化 Webhook 池

        Args:
            resources: Webhook 资源列表
            sender: 实现 SenderProtocol 的发送器
            segmenter: 消息分段器
            converter: 实现 MessageConverterProtocol 的消息转换器
            content_moderator: 内容审核器（可选）
        """
        self.logger = get_logger()
        self.resources = resources
        self.sender = sender
        self.segmenter = segmenter
        self.converter = converter
        self.content_moderator = content_moderator

        if not self.resources:
            raise ValueError("Webhook pool must have at least one resource")

        # 消息队列
        self.message_queue: queue.Queue = queue.Queue()

        # 结果字典
        self.results: dict = {}

        # 停止标志
        self._stop_flag = threading.Event()

        # 调度线程
        self.scheduler_thread = threading.Thread(
            target=self._schedule_messages,
            daemon=True
        )
        self.scheduler_thread.start()

        self.logger.info(f"WebhookPoolBase initialized with {len(self.resources)} webhooks")

    def enqueue(self, message: Message) -> SendResult:
        """
        将消息加入队列

        Args:
            message: 消息对象

        Returns:
            SendResult: 发送结果对象
        """
        result = SendResult(message.id)
        self.results[message.id] = result
        self.message_queue.put(message)

        self.logger.debug(f"Message {message.id} enqueued to pool (type={message.msg_type})")
        return result

    def _schedule_messages(self):
        """调度线程 - 串行处理消息"""
        self.logger.info("WebhookPoolBase scheduler thread started")

        while not self._stop_flag.is_set():
            try:
                message = self.message_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self._process_message(message)
            except Exception as e:
                self.logger.error(
                    f"Error processing message {message.id} ({type(e).__name__})"
                )
                result = self.results.get(message.id)
                if result:
                    result.mark_failed(f"Internal error ({type(e).__name__})")
            finally:
                self.message_queue.task_done()

    def _process_message(self, message: Message):
        """
        处理单条消息（通用流程）

        流程:
        1. 分段（可由子类跳过）
        2. 审核（可由子类跳过）
        3. 发送每个分段
        4. 平台特定后处理
        """
        result = self.results.get(message.id)
        if not result:
            self.logger.error(f"Result not found for message {message.id}")
            return

        self.logger.info(f"Processing message {message.id} in pool (type={message.msg_type})")

        # 1. 分段：本地不可行计划在任何发送前显式失败。
        try:
            segments = self._get_segments(message)
        except MessageSegmentOversizeError as error:
            result.mark_failed(str(error))
            return
        total_segments = len(segments)

        self.logger.debug(f"Message {message.id} split into {total_segments} segments")

        # 2. 审核（如果启用且不跳过）
        if (self.content_moderator and
            self.content_moderator.enabled and
            not self.should_skip_moderation(message.msg_type)):

            try:
                moderated_result = self._moderate_segments(message, segments)
            except MessageSegmentOversizeError as error:
                result.mark_failed(str(error))
                return
            if moderated_result is None:
                # 被拒绝
                result.mark_failed("Content blocked by moderator")
                return
            segments = moderated_result
            total_segments = len(segments)

        # 记录使用的 webhooks
        used_webhooks: Set[str] = set()

        # 3. 发送每个分段
        for i, segment in enumerate(segments):
            # 选择最佳 webhook
            try:
                webhook = self._select_best_webhook()
            except AllWebhooksUnavailableError as e:
                self.logger.error(f"All webhooks unavailable for message {message.id}")
                result.mark_failed(str(e))
                return

            # 频率控制
            webhook.rate_limiter.acquire()

            # 转换消息参数
            msg_type, content, metadata = self._prepare_segment_params(
                message, segment, i
            )

            # 发送
            success, error = self.sender.send(webhook.url, msg_type, content, metadata)

            if success:
                webhook.mark_success()
                used_webhooks.add(webhook.url)
                self.logger.debug(
                    f"Segment {i + 1}/{total_segments} sent via "
                    f"webhook_id={webhook_identity(webhook.url)} "
                    f"for message {message.id}"
                )
            else:
                webhook.mark_failure()
                safe_error = error or "send failed"
                self.logger.warning(
                    f"Segment {i + 1}/{total_segments} failed via "
                    f"webhook_id={webhook_identity(webhook.url)}: {safe_error}"
                )

                # 重试：尝试其他 webhook
                retry_success = self._retry_segment(
                    message, segment, i, msg_type, content, metadata, used_webhooks
                )

                if not retry_success:
                    self.logger.error(
                        f"Segment {i + 1}/{total_segments} failed on all webhooks "
                        f"for message {message.id}"
                    )
                    result.mark_failed(
                        f"Segment {i + 1}/{total_segments} failed on all webhooks: "
                        f"{safe_error}"
                    )
                    return

            # 分段间延迟
            if i < total_segments - 1:
                time.sleep(message.segment_interval / 1000.0)

        # 4. 平台特定后处理
        post_success = self._post_send_hook(message, used_webhooks)
        if not post_success:
            result.mark_failed("Post-send hook failed")
            return

        # 所有分段发送成功
        self.logger.info(
            f"Message {message.id} sent successfully ({total_segments} segments, "
            f"{len(used_webhooks)} webhooks)"
        )

        result.used_webhooks = list(used_webhooks)
        result.segment_count = total_segments
        result.mark_success()

    def _get_segments(self, message: Message) -> List[SegmentInfo]:
        """
        获取消息分段

        如果子类指定跳过分段，则返回单个分段。
        """
        if self.should_skip_segmentation(message.msg_type):
            return [SegmentInfo(content=message.content, is_first=True, is_last=True)]

        return self.segmenter._segment_bounded(
            message.content,
            message.msg_type,
            self._segment_budget(message.msg_type),
        )

    def _segment_budget(self, msg_type: str) -> int:
        return self.segmenter.max_bytes

    def _moderate_segments(
        self,
        message: Message,
        segments: List[SegmentInfo]
    ) -> Optional[List[SegmentInfo]]:
        """
        审核分段内容

        Returns:
            审核后的分段列表，如果被拒绝则返回 None
        """
        moderated_segments = []

        for segment in segments:
            review_content = self.segmenter._review_content(segment)
            moderated_content = self.content_moderator.moderate(
                content=review_content,
                message_id=message.id,
                msg_type=message.msg_type
            )

            if moderated_content is None:
                # 被拒绝
                self.logger.warning(
                    f"Message {message.id} blocked by content moderator in pool"
                )
                self._send_block_alert(message, SegmentInfo(
                    review_content,
                    is_first=segment.is_first,
                    is_last=segment.is_last,
                ))
                return None

            moderated_segments.append(SegmentInfo(
                moderated_content,
                is_first=segment.is_first,
                is_last=segment.is_last,
                page_number=None,
                total_pages=None,
            ))

        return self.segmenter._segment_reviewed(
            moderated_segments,
            message.msg_type,
            self._segment_budget(message.msg_type),
        )

    def _send_block_alert(self, message: Message, segment: SegmentInfo):
        """发送审核拒绝提示"""
        alert_msg = self.content_moderator.create_block_alert(
            segment.content, message.id
        )

        try:
            webhook = self._select_best_webhook()
            webhook.rate_limiter.acquire()

            # 使用转换器准备文本消息
            msg_type, content, metadata = self.converter.prepare_send_params(
                msg_type="text",
                content=alert_msg,
                message_metadata={}
            )
            self.sender.send(webhook.url, msg_type, content, metadata)
        except Exception as e:
            self.logger.error(
                f"Failed to send block alert ({type(e).__name__})"
            )

    def _prepare_segment_params(
        self,
        message: Message,
        segment: SegmentInfo,
        segment_index: int
    ) -> Tuple[str, Any, dict]:
        """
        准备分段发送参数

        子类可覆盖此方法以自定义参数准备逻辑。
        """
        # 构建消息元数据
        message_metadata = self._build_message_metadata(message, segment_index)

        # 使用转换器
        return self.converter.prepare_send_params(
            msg_type=message.msg_type,
            content=segment.content,
            message_metadata=message_metadata
        )

    def _build_message_metadata(self, message: Message, segment_index: int) -> dict:
        """
        构建消息元数据

        子类可覆盖此方法以添加平台特定的元数据。
        """
        metadata = {
            "mention_all": message.mention_all and segment_index == 0,
        }

        # 添加平台扩展数据
        if hasattr(message, "platform_extras") and message.platform_extras:
            metadata.update(message.platform_extras)

        return metadata

    def _retry_segment(
        self,
        message: Message,
        segment: SegmentInfo,
        segment_index: int,
        msg_type: str,
        content: Any,
        metadata: dict,
        exclude_webhooks: Set[str]
    ) -> bool:
        """
        重试发送分段（尝试其他可用的 webhook）
        """
        available = [
            w for w in self.resources
            if w.is_available() and w.url not in exclude_webhooks
        ]

        if not available:
            return False

        available.sort(key=lambda w: w.get_priority_score(), reverse=True)

        for webhook in available:
            webhook.rate_limiter.acquire()
            success, error = self.sender.send(webhook.url, msg_type, content, metadata)

            if success:
                webhook.mark_success()
                exclude_webhooks.add(webhook.url)
                self.logger.info(
                    f"Segment {segment_index} retry succeeded via "
                    f"webhook_id={webhook_identity(webhook.url)}"
                )
                return True
            else:
                webhook.mark_failure()
                self.logger.warning(
                    f"Segment {segment_index} retry failed via "
                    f"webhook_id={webhook_identity(webhook.url)}"
                )

        return False

    def _select_best_webhook(self) -> "WebhookResource":
        """
        选择最佳 webhook（最空闲优先策略）

        Raises:
            AllWebhooksUnavailableError: 所有 webhook 都不可用
        """
        available = [w for w in self.resources if w.is_available()]

        if not available:
            min_cooldown = min(w.get_cooldown_remaining() for w in self.resources)

            if min_cooldown > 0:
                self.logger.warning(
                    f"All webhooks in cooldown, waiting {min_cooldown:.1f}s for recovery"
                )
                time.sleep(min_cooldown + 0.1)

                available = [w for w in self.resources if w.is_available()]

            if not available:
                raise AllWebhooksUnavailableError(
                    "All webhooks are unavailable after waiting"
                )

        best = max(available, key=lambda w: w.get_priority_score())

        if best.rate_limiter.get_available_count() == 0:
            next_times = [
                (w, w.rate_limiter.get_next_available_time())
                for w in available
            ]
            soonest = min(next_times, key=lambda x: x[1])
            wait_time = soonest[1] - time.time()

            if wait_time > 0:
                self.logger.debug(f"Waiting {wait_time:.1f}s for webhook quota")
                time.sleep(wait_time)

            return soonest[0]

        return best

    def stop(self):
        """停止池"""
        self.logger.info("Stopping WebhookPool")
        self._stop_flag.set()
        self.scheduler_thread.join(timeout=5)

    def __del__(self):
        """析构函数"""
        if hasattr(self, "_stop_flag") and not self._stop_flag.is_set():
            self.stop()

    # ===== 抽象方法：由子类实现 =====

    @abstractmethod
    def should_skip_segmentation(self, msg_type: str) -> bool:
        """
        是否跳过分段

        某些消息类型（如图片）不需要分段。

        Args:
            msg_type: 消息类型

        Returns:
            bool: True 表示跳过分段
        """
        pass

    @abstractmethod
    def should_skip_moderation(self, msg_type: str) -> bool:
        """
        是否跳过审核

        某些消息类型（如图片）不需要内容审核。

        Args:
            msg_type: 消息类型

        Returns:
            bool: True 表示跳过审核
        """
        pass

    @abstractmethod
    def _post_send_hook(self, message: Message, used_webhooks: Set[str]) -> bool:
        """
        发送后钩子（平台特定处理）

        例如：企微的 @all workaround

        Args:
            message: 消息对象
            used_webhooks: 使用过的 webhook URL 集合

        Returns:
            bool: True 表示成功，False 表示失败
        """
        pass


__all__ = ["WebhookPoolBase", "AllWebhooksUnavailableError"]
