"""
测试服务端频控重试机制

验证当webhook被其他程序触发频控时，消息能否正确重试并最终送达
"""
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
import requests

from wecom_notifier.sender import Sender, RetryConfig
from wecom_notifier.constants import ERRCODE_RATE_LIMIT, ERRCODE_SUCCESS, RATE_LIMIT_WAIT_TIME


class TestRateLimitRetry(unittest.TestCase):
    """测试服务端频控重试"""

    def setUp(self):
        """初始化测试"""
        self.webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"

    @patch('wecom_notifier.sender.requests.post')
    @patch('time.sleep')  # Mock sleep以加速测试
    def test_rate_limit_retry_success_on_second_attempt(self, mock_sleep, mock_post):
        """
        测试：第一次触发频控，第二次成功

        场景：webhook被其他程序刷爆，第一次请求被拒绝，等待65秒后重试成功
        """
        # 模拟响应：第一次返回频控错误，第二次成功
        mock_post.side_effect = [
            Mock(json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}),  # 第1次：频控
            Mock(json=lambda: {'errcode': ERRCODE_SUCCESS, 'errmsg': 'ok'})  # 第2次：成功
        ]

        sender = Sender()
        success, error = sender.send_text(self.webhook_url, "测试消息")

        # 验证结果
        self.assertTrue(success)
        self.assertIsNone(error)

        # 验证等待了65秒
        self.assertEqual(mock_sleep.call_count, 1)
        mock_sleep.assert_called_with(RATE_LIMIT_WAIT_TIME)

        # 验证发送了2次请求
        self.assertEqual(mock_post.call_count, 2)

    @patch('wecom_notifier.sender.requests.post')
    @patch('time.sleep')
    def test_rate_limit_retry_multiple_times(self, mock_sleep, mock_post):
        """
        测试：多次频控后成功

        场景：webhook频控严重，需要重试3次才成功
        """
        # 模拟响应：前3次返回频控，第4次成功
        mock_post.side_effect = [
            Mock(json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}),
            Mock(json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}),
            Mock(json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}),
            Mock(json=lambda: {'errcode': ERRCODE_SUCCESS, 'errmsg': 'ok'})
        ]

        sender = Sender()
        success, error = sender.send_text(self.webhook_url, "测试消息")

        # 验证结果
        self.assertTrue(success)
        self.assertIsNone(error)

        # 验证等待了3次，每次65秒
        self.assertEqual(mock_sleep.call_count, 3)
        for call in mock_sleep.call_args_list:
            self.assertEqual(call[0][0], RATE_LIMIT_WAIT_TIME)

        # 验证发送了4次请求
        self.assertEqual(mock_post.call_count, 4)

    @patch('wecom_notifier.sender.requests.post')
    @patch('time.sleep')
    def test_rate_limit_retry_exhausted(self, mock_sleep, mock_post):
        """
        测试：频控重试次数耗尽

        场景：webhook持续被限流，重试5次后仍然失败
        """
        # 模拟响应：始终返回频控错误
        mock_post.return_value = Mock(
            json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}
        )

        sender = Sender()
        success, error = sender.send_text(self.webhook_url, "测试消息")

        # 验证结果：失败
        self.assertFalse(success)
        self.assertIn("Rate limit", error)

        # 验证等待了5次（最大重试次数）
        self.assertEqual(mock_sleep.call_count, 5)

        # 验证发送了6次请求（初始1次 + 5次重试）
        self.assertEqual(mock_post.call_count, 6)

    @patch('wecom_notifier.sender.requests.post')
    @patch('time.sleep')
    def test_rate_limit_then_network_error(self, mock_sleep, mock_post):
        """
        测试：频控后遇到网络错误

        场景：第一次频控，等待后遇到网络超时，然后成功
        """
        mock_post.side_effect = [
            Mock(json=lambda: {'errcode': ERRCODE_RATE_LIMIT, 'errmsg': 'freq control'}),  # 频控
            requests.Timeout("timeout"),  # 网络超时
            Mock(json=lambda: {'errcode': ERRCODE_SUCCESS, 'errmsg': 'ok'})  # 成功
        ]

        sender = Sender()
        success, error = sender.send_text(self.webhook_url, "测试消息")

        # 验证结果：成功
        self.assertTrue(success)
        self.assertIsNone(error)

        # 验证sleep被调用了2次：
        # 1次频控等待（65秒）+ 1次网络错误重试（2秒）
        self.assertEqual(mock_sleep.call_count, 2)
        # 第一次调用应该是65秒（频控）
        self.assertEqual(mock_sleep.call_args_list[0][0][0], RATE_LIMIT_WAIT_TIME)
        # 第二次调用应该是2秒（网络错误重试）
        self.assertEqual(mock_sleep.call_args_list[1][0][0], 2.0)

        # 验证发送了3次请求
        self.assertEqual(mock_post.call_count, 3)

    @patch('wecom_notifier.sender.requests.post')
    def test_no_retry_for_invalid_webhook(self, mock_post):
        """
        测试：webhook无效不重试

        场景：webhook地址无效（93000错误），应该立即失败不重试
        """
        mock_post.return_value = Mock(
            json=lambda: {'errcode': 93000, 'errmsg': 'invalid webhook'}
        )

        sender = Sender()
        success, error = sender.send_text(self.webhook_url, "测试消息")

        # 验证结果：失败
        self.assertFalse(success)
        self.assertIn("Invalid webhook", error)

        # 验证只发送了1次请求（不重试）
        self.assertEqual(mock_post.call_count, 1)

    def test_rate_limit_wait_time_configuration(self):
        """
        测试：验证频控等待时间配置正确

        确保等待时间略大于60秒（企业微信的时间窗口）
        """
        self.assertGreater(RATE_LIMIT_WAIT_TIME, 60)
        self.assertLessEqual(RATE_LIMIT_WAIT_TIME, 70)  # 不应该太长


class TestRateLimiterServerFeedback(unittest.TestCase):
    """测试RateLimiter的服务端反馈机制"""

    def test_mark_server_rate_limited(self):
        """
        测试：标记服务端频控

        验证lockout机制是否正常工作
        """
        from wecom_notifier.rate_limiter import RateLimiter

        limiter = RateLimiter(max_count=20, time_window=60)

        # 标记为服务端频控
        limiter.mark_server_rate_limited(lockout_duration=2)  # 使用较短的时间便于测试

        # 验证进入锁定期
        self.assertGreater(limiter.lockout_until, time.time())

        # 等待锁定期结束
        time.sleep(2.1)

        # 验证锁定期已结束
        self.assertLessEqual(limiter.lockout_until, time.time())

    @patch('time.sleep')
    def test_acquire_during_lockout(self, mock_sleep):
        """
        测试：锁定期内acquire会等待
        """
        from wecom_notifier.rate_limiter import RateLimiter

        limiter = RateLimiter()

        # 标记为服务端频控（锁定60秒）
        limiter.mark_server_rate_limited(lockout_duration=60)

        # 尝试获取配额（应该等待）
        limiter.acquire()

        # 验证sleep被调用
        self.assertGreater(mock_sleep.call_count, 0)


if __name__ == '__main__':
    unittest.main()
