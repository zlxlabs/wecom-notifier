"""
企业微信 Webhook 资源 - 管理单个 webhook 的状态和容错
"""
import time
from wecom_notifier.core.rate_limiter import RateLimiter
from wecom_notifier.core.webhook_identity import webhook_identity


class WebhookResource:
    """
    Webhook资源

    管理单个webhook的：
    - 频率限制
    - 错误计数和冷却
    - 可用性判断
    """

    # 冷却策略配置
    COOLDOWN_BASE = 10  # 基础冷却时间（秒）
    COOLDOWN_MAX = 60   # 最大冷却时间（秒）

    def __init__(self, url: str, rate_limiter: RateLimiter):
        """
        初始化Webhook资源

        Args:
            url: Webhook地址
            rate_limiter: 频率限制器（全局共享）
        """
        self.url = url
        self.rate_limiter = rate_limiter

        # 错误跟踪
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

    def is_available(self) -> bool:
        """
        判断webhook是否可用

        考虑因素：
        1. 是否在冷却期（因为连续失败）
        2. 是否有可用配额（通过rate_limiter检查）

        Returns:
            bool: 是否可用
        """
        # 检查是否在冷却期
        if self.consecutive_failures > 0:
            cooldown = self._calculate_cooldown()
            elapsed = time.time() - self.last_failure_time

            if elapsed < cooldown:
                # 仍在冷却期
                return False

        # 不在冷却期，可用
        return True

    def _calculate_cooldown(self) -> float:
        """
        计算冷却时间（指数退避）

        Returns:
            float: 冷却时间（秒）
        """
        # 指数退避：10秒、20秒、40秒... 最多60秒
        cooldown = min(
            self.COOLDOWN_MAX,
            self.COOLDOWN_BASE * (2 ** (self.consecutive_failures - 1))
        )
        return cooldown

    def get_cooldown_remaining(self) -> float:
        """
        获取剩余冷却时间

        Returns:
            float: 剩余冷却时间（秒），如果不在冷却期则返回0
        """
        if self.consecutive_failures == 0:
            return 0.0

        cooldown = self._calculate_cooldown()
        elapsed = time.time() - self.last_failure_time
        remaining = max(0.0, cooldown - elapsed)

        return remaining

    def mark_success(self):
        """标记发送成功，重置失败计数"""
        if self.consecutive_failures > 0:
            # 从失败中恢复
            self.consecutive_failures = 0
            self.last_failure_time = 0.0

    def mark_failure(self):
        """标记发送失败，增加失败计数并进入冷却期"""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

    def get_priority_score(self) -> float:
        """
        获取优先级分数（用于选择最佳webhook）

        分数越高越优先。考虑因素：
        1. 可用配额数量（主要因素）
        2. 是否在冷却期（次要因素）

        Returns:
            float: 优先级分数
        """
        if not self.is_available():
            # 不可用的webhook分数为负数（冷却剩余时间）
            return -self.get_cooldown_remaining()

        # 可用配额数量作为分数
        available_count = self.rate_limiter.get_available_count()

        return float(available_count)

    def __repr__(self):
        available = "可用" if self.is_available() else "冷却中"
        cooldown = self.get_cooldown_remaining()
        quota = self.rate_limiter.get_available_count()

        if cooldown > 0:
            return (
                f"<WebhookResource webhook_id={webhook_identity(self.url)} "
                f"status={available} cooldown={cooldown:.1f}s>"
            )
        else:
            return (
                f"<WebhookResource webhook_id={webhook_identity(self.url)} "
                f"status={available} quota={quota}>"
            )


__all__ = ["WebhookResource"]
