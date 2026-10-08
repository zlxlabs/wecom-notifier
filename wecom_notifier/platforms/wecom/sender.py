"""
企业微信 HTTP 发送器
"""
import base64
import hashlib
import time
from typing import Dict, Any, Tuple, Optional
import requests

from wecom_notifier.core.logger import get_logger
from wecom_notifier.core.webhook_identity import webhook_identity
from .exceptions import (
    NetworkError,
    WebhookInvalidError,
    RateLimitError,
    WeComError,
    InvalidParameterError
)
from .constants import (
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_BACKOFF_FACTOR,
    ERRCODE_SUCCESS,
    ERRCODE_WEBHOOK_INVALID,
    ERRCODE_RATE_LIMIT,
    RATE_LIMIT_MAX_RETRIES,
    RATE_LIMIT_WAIT_TIME,
    MSG_TYPE_TEXT,
    MSG_TYPE_MARKDOWN_V2,
    MSG_TYPE_IMAGE
)


class RetryConfig:
    """重试配置"""

    def __init__(
            self,
            max_retries: int = DEFAULT_MAX_RETRIES,
            retry_delay: float = DEFAULT_RETRY_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor


class Sender:
    """企业微信 HTTP 发送器"""

    def __init__(
            self,
            retry_config: Optional[RetryConfig] = None,
            timeout: int = DEFAULT_TIMEOUT
    ):
        """
        初始化发送器

        Args:
            retry_config: 重试配置
            timeout: HTTP请求超时时间
        """
        self.logger = get_logger()
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout

    def send_text(
            self,
            webhook_url: str,
            content: str,
            mentioned_list: Optional[list] = None,
            mentioned_mobile_list: Optional[list] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        发送文本消息

        Args:
            webhook_url: Webhook地址
            content: 文本内容
            mentioned_list: @的用户列表
            mentioned_mobile_list: @的手机号列表

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msgtype": MSG_TYPE_TEXT,
            "text": {
                "content": content
            }
        }

        if mentioned_list:
            data["text"]["mentioned_list"] = mentioned_list
        if mentioned_mobile_list:
            data["text"]["mentioned_mobile_list"] = mentioned_mobile_list

        return self._send_request(webhook_url, data)

    def send_markdown(
            self,
            webhook_url: str,
            content: str
    ) -> Tuple[bool, Optional[str]]:
        """
        发送Markdown v2消息

        Args:
            webhook_url: Webhook地址
            content: Markdown内容

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msgtype": MSG_TYPE_MARKDOWN_V2,
            "markdown_v2": {
                "content": content
            }
        }

        return self._send_request(webhook_url, data)

    def send_image(
            self,
            webhook_url: str,
            image_base64: str,
            image_md5: str
    ) -> Tuple[bool, Optional[str]]:
        """
        发送图片消息

        Args:
            webhook_url: Webhook地址
            image_base64: 图片base64编码
            image_md5: 图片MD5值

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msgtype": MSG_TYPE_IMAGE,
            "image": {
                "base64": image_base64,
                "md5": image_md5
            }
        }

        return self._send_request(webhook_url, data)

    def send_mention_all(self, webhook_url: str) -> Tuple[bool, Optional[str]]:
        """
        发送@all消息（用于markdown_v2和image的workaround）

        Args:
            webhook_url: Webhook地址

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        return self.send_text(webhook_url, "", mentioned_list=["@all"])

    def _send_request(self, webhook_url: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        发送HTTP请求（带智能重试）

        重试策略：
        1. 网络错误（超时、连接失败）：指数退避，最多重试3次
        2. 服务端频控（企微返回45009）：等待65秒，最多重试5次
        3. 其他错误（webhook无效等）：立即失败

        Args:
            webhook_url: Webhook地址
            data: 请求数据

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        network_retry_count = 0  # 网络错误重试计数
        rate_limit_retry_count = 0  # 频控重试计数
        last_error = None

        while True:
            try:
                attempt_desc = f"network_retry={network_retry_count}, rate_limit_retry={rate_limit_retry_count}"
                self.logger.debug(
                    f"Sending request to webhook_id={webhook_identity(webhook_url)} "
                    f"({attempt_desc})"
                )

                response = requests.post(
                    webhook_url,
                    json=data,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )

                # 企微API返回格式: {"errcode": 0, "errmsg": "ok"}
                result = response.json()

                errcode = result.get('errcode')
                safe_errcode = errcode if type(errcode) is int else "unknown"

                if errcode == ERRCODE_SUCCESS:
                    self.logger.info(f"Message sent successfully")
                    return True, None

                # 处理不同错误码
                if errcode == ERRCODE_WEBHOOK_INVALID:
                    error = WebhookInvalidError(
                        f"Invalid webhook (code {safe_errcode})"
                    )
                    self.logger.error(
                        f"Webhook invalid (code {safe_errcode}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

                elif errcode == ERRCODE_RATE_LIMIT:
                    # 服务端频控：可能是其他程序触发的，需要等待足够长的时间
                    error = RateLimitError(
                        f"Rate limit exceeded (code {safe_errcode})"
                    )
                    self.logger.warning(
                        f"Server-side rate limit exceeded (code {safe_errcode}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )

                    if rate_limit_retry_count < RATE_LIMIT_MAX_RETRIES:
                        rate_limit_retry_count += 1
                        self.logger.warning(
                            f"Webhook may have been rate-limited by other programs. "
                            f"Waiting {RATE_LIMIT_WAIT_TIME}s before retry "
                            f"(rate_limit_retry {rate_limit_retry_count}/{RATE_LIMIT_MAX_RETRIES})"
                        )
                        time.sleep(RATE_LIMIT_WAIT_TIME)
                        # 重置网络重试计数（新的一轮尝试）
                        network_retry_count = 0
                        continue
                    else:
                        self.logger.error(
                            f"Rate limit retry exhausted ({RATE_LIMIT_MAX_RETRIES} times, "
                            f"waited {RATE_LIMIT_MAX_RETRIES * RATE_LIMIT_WAIT_TIME}s total)"
                        )
                        return False, str(error)

                else:
                    error = WeComError(f"API error {safe_errcode}")
                    self.logger.error(
                        f"API error {safe_errcode} for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

            except requests.Timeout:
                last_error = NetworkError("Request timeout")
                self.logger.warning(
                    f"Request timeout for webhook_id={webhook_identity(webhook_url)}"
                )

            except requests.ConnectionError:
                last_error = NetworkError("Connection failed")
                self.logger.warning(
                    f"Connection failed for webhook_id={webhook_identity(webhook_url)}"
                )

            except Exception as e:
                last_error = WeComError(f"Unexpected error ({type(e).__name__})")
                self.logger.error(
                    f"Unexpected error ({type(e).__name__}) for "
                    f"webhook_id={webhook_identity(webhook_url)}"
                )
                return False, str(last_error)

            # 处理网络错误重试
            if isinstance(last_error, NetworkError):
                if network_retry_count < self.retry_config.max_retries:
                    network_retry_count += 1
                    delay = self.retry_config.retry_delay * (self.retry_config.backoff_factor ** (network_retry_count - 1))
                    self.logger.info(
                        f"Network error, retrying in {delay}s "
                        f"(network_retry {network_retry_count}/{self.retry_config.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(f"Network retry exhausted ({self.retry_config.max_retries} times)")
                    return False, str(last_error)

            # 其他未处理的错误
            self.logger.error(f"Unhandled error: {last_error}")
            return False, str(last_error)

    @staticmethod
    def prepare_image(image_path: Optional[str] = None, image_base64: Optional[str] = None) -> Tuple[str, str]:
        """
        准备图片数据（base64和MD5）

        Args:
            image_path: 图片文件路径
            image_base64: 图片base64编码（二选一）

        Returns:
            Tuple[str, str]: (base64编码, MD5值)

        Raises:
            InvalidParameterError: 参数错误
        """
        if image_path:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        elif image_base64:
            try:
                image_data = base64.b64decode(image_base64)
            except Exception as e:
                raise InvalidParameterError(f"Invalid base64 data: {e}")
        else:
            raise InvalidParameterError("Either image_path or image_base64 must be provided")

        # 计算MD5
        md5 = hashlib.md5(image_data).hexdigest()

        return image_base64, md5


__all__ = ["Sender", "RetryConfig"]
