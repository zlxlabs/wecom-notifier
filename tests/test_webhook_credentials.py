"""入口级回归：授权 webhook URL 不得进入本库诊断输出。"""
import collections
import io
import re

import pytest
from loguru import logger as loguru_logger

from wecom_notifier.platforms.feishu.notifier import FeishuNotifier
from wecom_notifier.platforms.wecom.notifier import WeComNotifier


WECom_URLS = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=FAKE-WECOM-ALPHA-6f24",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=FAKE-WECOM-BRAVO-9a31",
]
FEISHU_URLS = [
    "https://open.feishu.cn/open-apis/bot/v2/hook/FAKE-FEISHU-ALPHA-2c88",
    "https://open.feishu.cn/open-apis/bot/v2/hook/FAKE-FEISHU-BRAVO-7d15",
]


@pytest.fixture
def diagnostic_output():
    """真实 loguru sink，启用 diagnose/backtrace 模拟用户自配日志配置。"""
    output = io.StringIO()
    handler_id = loguru_logger.add(
        output,
        format="{level} {message}\n{exception}",
        level="DEBUG",
        diagnose=True,
        backtrace=True,
    )
    try:
        yield output
    finally:
        loguru_logger.remove(handler_id)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def _assert_credentials_absent(output, urls):
    text = output.getvalue() if hasattr(output, "getvalue") else output
    for url in urls:
        credential = url.rsplit("/", 1)[-1].split("key=")[-1]
        assert url not in text
        assert credential not in text
        assert credential[:12] not in text
    return text


def test_public_success_logs_distinct_stable_identity_and_posts_original_urls(
    diagnostic_output, monkeypatch
):
    posted_urls = []

    def post(url, **kwargs):
        posted_urls.append(url)
        payload = {"errcode": 0, "errmsg": "ok"} if "qyapi" in url else {"code": 0, "msg": "ok"}
        return _Response(payload)

    import wecom_notifier.platforms.wecom.sender as wecom_sender_module
    import wecom_notifier.platforms.feishu.sender as feishu_sender_module

    monkeypatch.setattr(wecom_sender_module.requests, "post", post)
    monkeypatch.setattr(feishu_sender_module.requests, "post", post)
    wecom = WeComNotifier(max_retries=0, retry_delay=0)
    feishu = FeishuNotifier(max_retries=0, retry_delay=0)
    try:
        results = [
            wecom.send_text(url, "ok", async_send=False) for url in WECom_URLS
        ] + [
            feishu.send_text(url, "ok", async_send=False) for url in FEISHU_URLS
        ]
        assert all(result.is_success() for result in results)
        assert posted_urls == WECom_URLS + FEISHU_URLS
    finally:
        wecom.stop_all()
        feishu.stop_all()

    text = _assert_credentials_absent(diagnostic_output, WECom_URLS + FEISHU_URLS)
    identities = re.findall(r"webhook_id=(wh-[0-9a-f]{16})", text)
    counts = collections.Counter(identities)
    assert len(counts) == 4
    assert all(count >= 2 for count in counts.values())


@pytest.mark.parametrize("platform", ["wecom", "wecom-pool", "feishu"])
def test_api_error_echo_is_not_returned_or_logged(
    platform, diagnostic_output, monkeypatch
):
    url = WECom_URLS[0] if platform.startswith("wecom") else FEISHU_URLS[0]
    secret = url.rsplit("/", 1)[-1].split("key=")[-1]
    echoed = "remote diagnostic echoed " + url + "; key=" + secret

    def post(actual_url, **kwargs):
        assert actual_url == url
        payload = (
            {"errcode": 999, "errmsg": echoed}
            if platform.startswith("wecom")
            else {"code": 999, "msg": echoed}
        )
        return _Response(payload)

    if platform.startswith("wecom"):
        import wecom_notifier.platforms.wecom.sender as sender_module
        monkeypatch.setattr(sender_module.requests, "post", post)
        notifier = WeComNotifier(max_retries=0, retry_delay=0)
        send_url = [url] if platform == "wecom-pool" else url
    else:
        import wecom_notifier.platforms.feishu.sender as sender_module
        monkeypatch.setattr(sender_module.requests, "post", post)
        notifier = FeishuNotifier(max_retries=0, retry_delay=0)
        send_url = url

    try:
        result = notifier.send_text(send_url, "failure", async_send=False)
        assert result.success is False
        assert result.error
        assert "999" in result.error
        assert secret not in result.error
        assert secret[:12] not in result.error
        assert url not in result.error
        assert "remote diagnostic echoed" not in result.error
    finally:
        notifier.stop_all()

    text = _assert_credentials_absent(diagnostic_output, [url])
    assert "remote diagnostic echoed" not in text


@pytest.mark.parametrize("platform", ["wecom", "feishu"])
def test_connection_error_does_not_leak_url_in_logs_or_result(
    platform, diagnostic_output, monkeypatch
):
    url = WECom_URLS[1] if platform == "wecom" else FEISHU_URLS[1]
    secret = url.rsplit("/", 1)[-1].split("key=")[-1]

    def post(actual_url, **kwargs):
        raise __import__("requests").ConnectionError("connection failed for " + actual_url)

    if platform == "wecom":
        import wecom_notifier.platforms.wecom.sender as sender_module
        monkeypatch.setattr(sender_module.requests, "post", post)
        notifier = WeComNotifier(max_retries=0, retry_delay=0)
    else:
        import wecom_notifier.platforms.feishu.sender as sender_module
        monkeypatch.setattr(sender_module.requests, "post", post)
        notifier = FeishuNotifier(max_retries=0, retry_delay=0)

    try:
        result = notifier.send_text(url, "failure", async_send=False)
        assert result.success is False
        assert result.error
        assert "Connection" in result.error or "Network" in result.error
        assert secret not in result.error
        assert secret[:12] not in result.error
        assert url not in result.error
        assert "connection failed for" not in result.error
    finally:
        notifier.stop_all()

    _assert_credentials_absent(diagnostic_output, [url])


def test_worker_exceptions_are_sanitized_for_single_feishu_and_wecom_pool(
    diagnostic_output, monkeypatch
):
    wecom_url = WECom_URLS[0]
    feishu_url = FEISHU_URLS[0]
    pool_urls = WECom_URLS

    def fail_with_url(url, *args, **kwargs):
        raise RuntimeError("worker failure for " + url)

    wecom = WeComNotifier(max_retries=0, retry_delay=0)
    feishu = FeishuNotifier(max_retries=0, retry_delay=0)
    monkeypatch.setattr(wecom.sender, "send_text", fail_with_url)
    monkeypatch.setattr(feishu.sender, "send_text", fail_with_url)
    try:
        single_result = wecom.send_text(wecom_url, "failure", async_send=False)
        feishu_result = feishu.send_text(feishu_url, "failure", async_send=False)
        pool_result = wecom.send_text(pool_urls, "failure", async_send=False)
        assert single_result.success is False
        assert feishu_result.success is False
        assert pool_result.success is False
        assert "RuntimeError" in single_result.error
        assert "RuntimeError" in feishu_result.error
        assert "RuntimeError" in pool_result.error
        for result in (single_result, feishu_result, pool_result):
            credentials = (
                "FAKE-WECOM-ALPHA-6f24", "FAKE-WECOM-BRAVO-9a31",
                "FAKE-FEISHU-ALPHA-2c88", "FAKE-FEISHU-BRAVO-7d15",
            )
            assert all(secret not in result.error for secret in credentials)
            assert all(secret[:12] not in result.error for secret in credentials)
            assert "worker failure for" not in result.error
    finally:
        wecom.stop_all()
        feishu.stop_all()

    text = _assert_credentials_absent(
        diagnostic_output, WECom_URLS + FEISHU_URLS
    )
    assert "worker failure for" not in text
