"""
飞书 HTTP 发送器

负责实际的 HTTP 请求发送，支持：
- 文本消息
- 卡片消息（interactive）
- 签名校验（可选）
"""
import base64
import hashlib
import hmac
import time
from typing import Dict, Any, Tuple, Optional

import requests

from wecom_notifier.core.logger import get_logger
from wecom_notifier.core.webhook_identity import webhook_identity
from .constants import (
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_BACKOFF_FACTOR,
    CODE_SUCCESS,
    CODE_BAD_REQUEST,
    CODE_RATE_LIMIT,
    CODE_KEYWORD_FAILED,
    CODE_IP_FAILED,
    CODE_SIGN_FAILED,
    RATE_LIMIT_MAX_RETRIES,
    RATE_LIMIT_WAIT_TIME,
    MSG_TYPE_TEXT,
    MSG_TYPE_INTERACTIVE,
    DEFAULT_CARD_TEMPLATE,
)
from .exceptions import (
    FeishuError,
    FeishuNetworkError,
    FeishuRateLimitError,
    FeishuKeywordError,
    FeishuIPError,
    FeishuSignError,
    FeishuBadRequestError,
)


class FeishuRetryConfig:
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


class FeishuSender:
    """飞书 HTTP 发送器"""

    def __init__(
        self,
        retry_config: Optional[FeishuRetryConfig] = None,
        timeout: int = DEFAULT_TIMEOUT,
        secret: Optional[str] = None
    ):
        """
        初始化发送器

        Args:
            retry_config: 重试配置
            timeout: HTTP 请求超时时间
            secret: 签名密钥（如果机器人启用了签名校验）
        """
        self.logger = get_logger()
        self.retry_config = retry_config or FeishuRetryConfig()
        self.timeout = timeout
        self.secret = secret

    def _gen_sign(self, timestamp: int) -> str:
        """
        生成签名

        Args:
            timestamp: 时间戳（秒）

        Returns:
            str: 签名字符串
        """
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def send_text(
        self,
        webhook_url: str,
        content: str
    ) -> Tuple[bool, Optional[str]]:
        """
        发送文本消息

        Args:
            webhook_url: Webhook 地址
            content: 文本内容（支持 <at> 标签）

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msg_type": MSG_TYPE_TEXT,
            "content": {
                "text": content
            }
        }

        return self._send_request(webhook_url, data)

    def send_card(
        self,
        webhook_url: str,
        content: str,
        title: str = "通知",
        template: str = DEFAULT_CARD_TEMPLATE
    ) -> Tuple[bool, Optional[str]]:
        """
        发送卡片消息（使用 Markdown 内容）

        Args:
            webhook_url: Webhook 地址
            content: Markdown 内容
            title: 卡片标题
            template: 卡片模板颜色

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msg_type": MSG_TYPE_INTERACTIVE,
            "card": {
                "schema": "2.0",
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": template
                },
                "body": {
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": content
                        }
                    ]
                }
            }
        }

        return self._send_request(webhook_url, data)

    def send_raw_card(
        self,
        webhook_url: str,
        card: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        发送原始卡片消息

        Args:
            webhook_url: Webhook 地址
            card: 完整的卡片结构

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        data = {
            "msg_type": MSG_TYPE_INTERACTIVE,
            "card": card
        }

        return self._send_request(webhook_url, data)

    def _send_request(
        self,
        webhook_url: str,
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        发送 HTTP 请求（带智能重试）

        重试策略：
        1. 网络错误（超时、连接失败）：指数退避，最多重试 3 次
        2. 服务端频控（11232）：等待 65 秒，最多重试 5 次
        3. 其他错误（签名失败、关键词失败等）：立即失败

        Args:
            webhook_url: Webhook 地址
            data: 请求数据

        Returns:
            Tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        # 如果配置了签名，添加签名信息
        if self.secret:
            timestamp = int(time.time())
            data["timestamp"] = str(timestamp)
            data["sign"] = self._gen_sign(timestamp)

        network_retry_count = 0
        rate_limit_retry_count = 0
        last_error = None

        while True:
            try:
                attempt_desc = (
                    f"network_retry={network_retry_count}, "
                    f"rate_limit_retry={rate_limit_retry_count}"
                )
                self.logger.debug(
                    f"Sending Feishu request to "
                    f"webhook_id={webhook_identity(webhook_url)} ({attempt_desc})"
                )

                response = requests.post(
                    webhook_url,
                    json=data,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )

                result = response.json()
                code = result.get("code", result.get("StatusCode"))
                safe_code = code if type(code) is int else "unknown"

                if code == CODE_SUCCESS:
                    self.logger.info("Feishu message sent successfully")
                    return True, None

                # 处理不同错误码
                if code == CODE_BAD_REQUEST:
                    error = FeishuBadRequestError(f"Bad request (code {safe_code})")
                    self.logger.error(
                        f"Feishu bad request (code {safe_code}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

                elif code == CODE_RATE_LIMIT:
                    error = FeishuRateLimitError(
                        f"Rate limit exceeded (code {safe_code})"
                    )
                    self.logger.warning(
                        f"Feishu rate limit exceeded (code {safe_code}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )

                    if rate_limit_retry_count < RATE_LIMIT_MAX_RETRIES:
                        rate_limit_retry_count += 1
                        self.logger.warning(
                            f"Waiting {RATE_LIMIT_WAIT_TIME}s before retry "
                            f"(rate_limit_retry {rate_limit_retry_count}/{RATE_LIMIT_MAX_RETRIES})"
                        )
                        time.sleep(RATE_LIMIT_WAIT_TIME)
                        network_retry_count = 0
                        continue
                    else:
                        self.logger.error(
                            f"Rate limit retry exhausted ({RATE_LIMIT_MAX_RETRIES} times)"
                        )
                        return False, str(error)

                elif code == CODE_KEYWORD_FAILED:
                    error = FeishuKeywordError(
                        f"Keyword check failed (code {safe_code})"
                    )
                    self.logger.error(
                        f"Feishu keyword check failed (code {safe_code}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

                elif code == CODE_IP_FAILED:
                    error = FeishuIPError(f"IP not allowed (code {safe_code})")
                    self.logger.error(
                        f"Feishu IP not allowed (code {safe_code}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

                elif code == CODE_SIGN_FAILED:
                    error = FeishuSignError(f"Sign match failed (code {safe_code})")
                    self.logger.error(
                        f"Feishu sign failed (code {safe_code}) for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

                else:
                    error = FeishuError(f"API error {safe_code}")
                    self.logger.error(
                        f"Feishu API error {safe_code} for "
                        f"webhook_id={webhook_identity(webhook_url)}"
                    )
                    return False, str(error)

            except requests.Timeout:
                last_error = FeishuNetworkError("Request timeout")
                self.logger.warning(
                    f"Feishu request timeout for "
                    f"webhook_id={webhook_identity(webhook_url)}"
                )

            except requests.ConnectionError:
                last_error = FeishuNetworkError("Connection failed")
                self.logger.warning(
                    f"Feishu connection failed for "
                    f"webhook_id={webhook_identity(webhook_url)}"
                )

            except Exception as e:
                last_error = FeishuError(
                    f"Unexpected error ({type(e).__name__})"
                )
                self.logger.error(
                    f"Feishu unexpected error ({type(e).__name__}) for "
                    f"webhook_id={webhook_identity(webhook_url)}"
                )
                return False, str(last_error)

            # 处理网络错误重试
            if isinstance(last_error, FeishuNetworkError):
                if network_retry_count < self.retry_config.max_retries:
                    network_retry_count += 1
                    delay = self.retry_config.retry_delay * (
                        self.retry_config.backoff_factor ** (network_retry_count - 1)
                    )
                    self.logger.info(
                        f"Network error, retrying in {delay}s "
                        f"(network_retry {network_retry_count}/{self.retry_config.max_retries})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(
                        f"Network retry exhausted ({self.retry_config.max_retries} times)"
                    )
                    return False, str(last_error)

            self.logger.error(f"Unhandled error: {last_error}")
            return False, str(last_error)


__all__ = ["FeishuSender", "FeishuRetryConfig"]
