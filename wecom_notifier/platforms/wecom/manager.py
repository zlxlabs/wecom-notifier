"""
企业微信 Webhook 管理器 - 管理单个 webhook 的消息队列和发送
"""
import queue
import threading
import time
from typing import Optional, TYPE_CHECKING

from wecom_notifier.core.logger import get_logger
from wecom_notifier.core.webhook_identity import webhook_identity
from wecom_notifier.core.models import SendResult, SegmentInfo
from wecom_notifier.core.rate_limiter import RateLimiter
from wecom_notifier.core.segmenter import MessageSegmenter, MessageSegmentOversizeError

from .sender import Sender
from .models import Message
from .constants import (
    MSG_TYPE_TEXT, MSG_TYPE_MARKDOWN_V2, MSG_TYPE_IMAGE,
    _MAX_BYTES_PER_TEXT, MAX_BYTES_PER_MESSAGE,
)

if TYPE_CHECKING:
    from wecom_notifier.core.moderation import ContentModerator


class WebhookManager:
    """
    企业微信 Webhook 管理器

    为每个webhook维护独立的消息队列、频率限制器和发送线程
    """

    def __init__(
            self,
            webhook_url: str,
            sender: Sender,
            segmenter: MessageSegmenter,
            rate_limiter: RateLimiter,
            content_moderator: Optional["ContentModerator"] = None
    ):
        """
        初始化Webhook管理器

        Args:
            webhook_url: Webhook地址
            sender: HTTP发送器
            segmenter: 消息分段器
            rate_limiter: 频率限制器
            content_moderator: 内容审核器（可选）
        """
        self.logger = get_logger()
        self.webhook_url = webhook_url
        self.sender = sender
        self.segmenter = segmenter
        self.rate_limiter = rate_limiter
        self.content_moderator = content_moderator

        # 消息队列
        self.message_queue = queue.Queue()

        # 结果字典，用于存储SendResult
        self.results = {}

        # 停止标志（必须在启动线程前初始化）
        self._stop_flag = threading.Event()

        # 工作线程
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

        self.logger.info(
            f"WebhookManager initialized (webhook_id={webhook_identity(webhook_url)})"
        )

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

        self.logger.debug(f"Message {message.id} enqueued (type={message.msg_type})")
        return result

    def _process_queue(self):
        """处理消息队列的工作线程"""
        self.logger.info(
            f"Worker thread started (webhook_id={webhook_identity(self.webhook_url)})"
        )

        while not self._stop_flag.is_set():
            try:
                # 从队列获取消息（超时1秒，以便检查停止标志）
                message = self.message_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                # 处理消息
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
        处理单条消息

        Args:
            message: 消息对象
        """
        result = self.results.get(message.id)
        if not result:
            self.logger.error(f"Result not found for message {message.id}")
            return

        self.logger.info(f"Processing message {message.id} (type={message.msg_type})")

        # 分段：本地不可能计划在首次 HTTP 前失败，并反映到 SendResult。
        try:
            segments = self._get_segments(message)
        except MessageSegmentOversizeError as error:
            result.mark_failed(str(error))
            return
        total_segments = len(segments)

        self.logger.debug(f"Message {message.id} split into {total_segments} segments")

        # 审核分段（如果启用）
        if self.content_moderator and self.content_moderator.enabled:
            moderated_segments = []
            for segment in segments:
                # 跳过图片类型的审核
                if message.msg_type == MSG_TYPE_IMAGE:
                    moderated_segments.append(segment)
                    continue

                # 审核文本内容（传入message_id和msg_type）
                moderated_content = self.content_moderator.moderate(
                    content=segment.content,
                    message_id=message.id,
                    msg_type=message.msg_type
                )

                if moderated_content is None:
                    # 被拒绝，发送敏感词提示
                    self.logger.warning(f"Message {message.id} blocked by content moderator")
                    alert_msg = self.content_moderator.create_block_alert(segment.content, message.id)

                    # 发送提示消息
                    self.rate_limiter.acquire()
                    self.sender.send_text(self.webhook_url, alert_msg)

                    result.mark_failed("Content blocked by moderator")
                    return

                # 使用审核后的内容
                moderated_segment = SegmentInfo(
                    content=moderated_content,
                    is_first=segment.is_first,
                    is_last=segment.is_last,
                    page_number=segment.page_number,
                    total_pages=segment.total_pages
                )
                moderated_segments.append(moderated_segment)

            try:
                segments = self._resegment_moderated(message, moderated_segments)
            except MessageSegmentOversizeError as error:
                result.mark_failed(str(error))
                return
            total_segments = len(segments)

        # 发送每个分段
        for i, segment in enumerate(segments):
            # 频率控制
            self.rate_limiter.acquire()

            # 发送
            success, error = self._send_segment(message, segment.content, i)

            if not success:
                # 发送失败，立即停止
                safe_error = error or "send failed"
                self.logger.error(
                    f"Segment {i + 1}/{total_segments} failed for message "
                    f"{message.id}: {safe_error}"
                )
                result.mark_failed(
                    f"Segment {i + 1}/{total_segments} failed: {safe_error}"
                )
                return

            self.logger.debug(f"Segment {i + 1}/{total_segments} sent successfully for message {message.id}")

            # 分段间延迟（最后一个分段不需要延迟）
            if i < total_segments - 1:
                time.sleep(message.segment_interval / 1000.0)

        # 处理@all workaround（针对markdown_v2和image）
        if message.needs_mention_all_workaround():
            self.logger.debug(f"Sending @all workaround for message {message.id}")

            self.rate_limiter.acquire()
            success, error = self.sender.send_mention_all(self.webhook_url)

            if not success:
                safe_error = error or "send failed"
                self.logger.error(
                    f"@all workaround failed for message {message.id}: {safe_error}"
                )
                result.mark_failed(f"@all workaround failed: {safe_error}")
                return

        # 所有分段发送成功
        self.logger.info(f"Message {message.id} sent successfully ({total_segments} segments)")
        result.mark_success()

    def _get_segments(self, message: Message):
        """
        获取消息分段

        Args:
            message: 消息对象

        Returns:
            List[SegmentInfo]: 分段列表
        """
        # 对于图片类型，不需要分段
        if message.msg_type == MSG_TYPE_IMAGE:
            return [SegmentInfo(message.content, is_first=True, is_last=True)]

        return self.segmenter._segment_bounded(
            message.content,
            message.msg_type,
            self._segment_budget(message.msg_type),
        )

    @staticmethod
    def _segment_budget(msg_type: str) -> int:
        return _MAX_BYTES_PER_TEXT if msg_type == MSG_TYPE_TEXT else MAX_BYTES_PER_MESSAGE

    def _resegment_moderated(self, message: Message, segments):
        if message.msg_type == MSG_TYPE_IMAGE:
            return segments
        bounded = []
        for segment in segments:
            reviewed = self.segmenter._segment_bounded(
                segment.content,
                message.msg_type,
                self._segment_budget(message.msg_type),
            )
            if len(reviewed) == 1 and reviewed[0].content == segment.content:
                bounded.append(SegmentInfo(
                    segment.content,
                    is_first=segment.is_first,
                    is_last=segment.is_last,
                    page_number=segment.page_number,
                    total_pages=segment.total_pages,
                ))
            else:
                bounded.extend(reviewed)
        return bounded

    def _send_segment(self, message: Message, content: str, segment_index: int) -> tuple:
        """
        发送单个分段

        Args:
            message: 消息对象
            content: 分段内容
            segment_index: 分段索引

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        if message.msg_type == MSG_TYPE_TEXT:
            return self.sender.send_text(
                self.webhook_url,
                content,
                mentioned_list=message.mentioned_list if segment_index == 0 else None,
                mentioned_mobile_list=message.mentioned_mobile_list if segment_index == 0 else None
            )

        elif message.msg_type == MSG_TYPE_MARKDOWN_V2:
            return self.sender.send_markdown(self.webhook_url, content)

        elif message.msg_type == MSG_TYPE_IMAGE:
            # 图片内容应该是 (base64, md5) 元组
            if isinstance(content, tuple) and len(content) == 2:
                base64_data, md5_value = content
                return self.sender.send_image(self.webhook_url, base64_data, md5_value)
            else:
                # content 应该是已经准备好的图片数据
                return self.sender.send_image(self.webhook_url, content[0], content[1])

        else:
            return False, f"Unsupported message type: {message.msg_type}"

    def stop(self):
        """停止管理器"""
        self.logger.info(
            f"Stopping WebhookManager (webhook_id={webhook_identity(self.webhook_url)})"
        )
        self._stop_flag.set()
        self.worker_thread.join(timeout=5)

    def __del__(self):
        """析构函数"""
        if hasattr(self, '_stop_flag') and not self._stop_flag.is_set():
            self.stop()


__all__ = ["WebhookManager"]
