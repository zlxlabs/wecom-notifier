"""
企业微信 Webhook 池

继承 WebhookPoolBase，实现企微特定的调度逻辑。
"""
from typing import List, Optional, Set, Tuple, Any, TYPE_CHECKING

from wecom_notifier.core.pool_base import WebhookPoolBase
from wecom_notifier.core.segmenter import MessageSegmenter
from wecom_notifier.core.models import SegmentInfo
from wecom_notifier.platforms.wecom.constants import (
    MSG_TYPE_TEXT, MSG_TYPE_MARKDOWN_V2, MSG_TYPE_IMAGE,
    _MAX_BYTES_PER_TEXT, MAX_BYTES_PER_MESSAGE,
)
from wecom_notifier.platforms.wecom.adapter import WeComSenderAdapter, WeComMessageConverter
from wecom_notifier.platforms.wecom.models import Message
from wecom_notifier.core.webhook_identity import webhook_identity

if TYPE_CHECKING:
    from wecom_notifier.platforms.wecom.resource import WebhookResource
    from wecom_notifier.platforms.wecom.sender import Sender
    from wecom_notifier.core.moderation import ContentModerator


class WeComWebhookPool(WebhookPoolBase):
    """
    企业微信 Webhook 池

    实现企微特定的调度行为：
    - 图片消息跳过分段和审核
    - @all workaround（markdown_v2 和 image 类型）
    - 企微特定的 mention 处理
    """

    def __init__(
        self,
        resources: List["WebhookResource"],
        sender: "Sender",
        segmenter: MessageSegmenter,
        content_moderator: Optional["ContentModerator"] = None
    ):
        """
        初始化企微 Webhook 池

        Args:
            resources: Webhook 资源列表
            sender: 企微原生 Sender（会被包装为适配器）
            segmenter: 消息分段器
            content_moderator: 内容审核器（可选）
        """
        # 保存原生 sender 引用
        self._native_sender = sender

        # 创建适配器和转换器
        adapter = WeComSenderAdapter(sender)
        converter = WeComMessageConverter()

        super().__init__(
            resources=resources,
            sender=adapter,
            segmenter=segmenter,
            converter=converter,
            content_moderator=content_moderator
        )

    def should_skip_segmentation(self, msg_type: str) -> bool:
        """
        是否跳过分段

        企微的图片消息不需要分段。
        """
        return msg_type == MSG_TYPE_IMAGE

    def _segment_budget(self, msg_type: str) -> int:
        return _MAX_BYTES_PER_TEXT if msg_type == MSG_TYPE_TEXT else MAX_BYTES_PER_MESSAGE

    def should_skip_moderation(self, msg_type: str) -> bool:
        """
        是否跳过审核

        企微的图片消息不需要内容审核。
        """
        return msg_type == MSG_TYPE_IMAGE

    def _post_send_hook(self, message: Message, used_webhooks: Set[str]) -> bool:
        """
        发送后钩子 - 处理企微的 @all workaround

        企微的 markdown_v2 和 image 类型不支持直接 @all，
        需要在发送后额外发送一条空的 text 消息来实现 @all。
        """
        if not message.needs_mention_all_workaround():
            return True

        self.logger.debug(f"Sending @all workaround for message {message.id}")

        try:
            webhook = self._select_best_webhook()
            webhook.rate_limiter.acquire()

            # 使用原生 sender 的 send_mention_all 方法
            success, error = self._native_sender.send_mention_all(webhook.url)

            if success:
                webhook.mark_success()
                used_webhooks.add(webhook.url)
                return True
            else:
                webhook.mark_failure()
                safe_error = error or "send failed"
                self.logger.error(
                    f"@all workaround failed for message {message.id} via "
                    f"webhook_id={webhook_identity(webhook.url)}: {safe_error}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"@all workaround failed with exception ({type(e).__name__})"
            )
            return False

    def _build_message_metadata(self, message: Message, segment_index: int) -> dict:
        """
        构建企微消息元数据

        只在第一个分段添加 mention 信息。
        """
        metadata = {}

        # 只在第一个分段添加 mention
        if segment_index == 0:
            if message.mention_all:
                metadata["mention_all"] = True

            # 企微特定的 mentioned_list
            if hasattr(message, "mentioned_list") and message.mentioned_list:
                metadata["mentioned_list"] = message.mentioned_list

            if hasattr(message, "mentioned_mobile_list") and message.mentioned_mobile_list:
                metadata["mentioned_mobile_list"] = message.mentioned_mobile_list

        return metadata

    def _prepare_segment_params(
        self,
        message: Message,
        segment: SegmentInfo,
        segment_index: int
    ) -> Tuple[str, Any, dict]:
        """
        准备分段发送参数

        处理企微特定的消息格式。
        """
        # 构建元数据
        metadata = self._build_message_metadata(message, segment_index)

        # 处理图片消息的特殊格式
        if message.msg_type == MSG_TYPE_IMAGE:
            content = segment.content
            # 图片内容可能是 (base64, md5) 元组
            if isinstance(content, tuple) and len(content) == 2:
                metadata["image_md5"] = content[1]
                content = content[0]

            return message.msg_type, content, metadata

        # 其他消息类型使用转换器
        return self.converter.prepare_send_params(
            msg_type=message.msg_type,
            content=segment.content,
            message_metadata=metadata
        )


__all__ = ["WeComWebhookPool"]
