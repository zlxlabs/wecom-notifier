"""端到端锁定有界消息计划与真实 requests PreparedRequest 边界。"""
import json
import re

import pytest
import requests

from wecom_notifier.core.segmenter import MessageSegmenter
from wecom_notifier.platforms.feishu.notifier import FeishuNotifier
from wecom_notifier.platforms.wecom.notifier import WeComNotifier


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {"errcode": 0, "code": 0, "msg": "ok"}


def _capture_prepared(monkeypatch):
    prepared = []

    def send(_session, request, **_kwargs):
        assert isinstance(request, requests.PreparedRequest)
        prepared.append(request)
        return _Response()

    monkeypatch.setattr(requests.sessions.Session, "send", send)
    return prepared


def _without_page_markers(contents):
    return "".join(content.partition("\n")[2] if content.startswith("(Page ") else content
                   for content in contents)


def _request_payload(request):
    body = request.body
    assert isinstance(body, bytes)
    return json.loads(body.decode("utf-8"))


def test_original_base_exposes_long_wecom_text_line_over_budget():
    content = "URL-BEGIN https://example.invalid/" + "x" * 5000 + " URL-END"
    segments = MessageSegmenter(max_bytes=4096).segment(content, "text")
    assert len(segments) > 1
    assert all(len(segment.content.encode("utf-8")) <= 4096 for segment in segments)
    assert "URL-BEGIN" in "".join(segment.content for segment in segments)
    assert "URL-END" in "".join(segment.content for segment in segments)


def test_long_table_row_and_code_block_are_bounded_without_losing_body():
    segmenter = MessageSegmenter(max_bytes=4096)
    table = "| h |\n| --- |\n| ROW-BEGIN " + "表" * 5000 + " ROW-END |"
    code = "标题相邻\n```python\n    CODE-BEGIN\n" + "    print('中文')\n" * 500 + "    CODE-END\n```"

    for original, msg_type in ((table, "markdown_v2"), (code, "markdown_v2")):
        segments = segmenter.segment(original, msg_type)
        assert len(segments) > 1
        assert all(len(segment.content.encode("utf-8")) <= 4096 for segment in segments)
        combined = "".join(segment.content for segment in segments)
        for marker in ("ROW-BEGIN", "ROW-END", "CODE-BEGIN", "CODE-END"):
            if marker in original:
                assert marker in combined


def test_feishu_interactive_large_chinese_card_splits_at_prepared_body(monkeypatch):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire", lambda _limiter: None)
    notifier = FeishuNotifier(max_retries=0, secret="test-signature-secret")
    content = "CARD-BEGIN\n" + "通知内容🙂" * 5000 + "\nCARD-END"
    title = "标题" * 40

    result = notifier.send_card(
        "https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        content,
        title=title,
        async_send=False,
    )
    notifier.stop_all()

    assert result.success is True
    assert prepared, "public send_card did not issue a prepared HTTP request"
    assert len(prepared) > 1
    payloads = [_request_payload(request) for request in prepared]
    cards = [payload["card"] for payload in payloads]
    assert all(len(request.body) <= 20000 for request in prepared)
    assert all(payload.get("timestamp") and payload.get("sign") for payload in payloads)
    assert all(card["header"]["title"]["content"] == f"{title} ({index}/{len(cards)})"
               for index, card in enumerate(cards, start=1))
    assert "CARD-BEGIN" in "".join(card["body"]["elements"][0]["content"] for card in cards)
    card_contents = [card["body"]["elements"][0]["content"] for card in cards]
    assert "CARD-END" in "".join(card_contents)
    assert _without_page_markers(card_contents) == content


def test_public_feishu_text_uses_the_prepared_request_limit(monkeypatch):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire", lambda _limiter: None)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.time.sleep", lambda _delay: None)
    notifier = FeishuNotifier(max_retries=0)
    content = "FEISHU-TEXT-BEGIN🙂" + "文本" * 5000 + "FEISHU-TEXT-END"
    result = notifier.send_text(
        "https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        content,
        async_send=False,
    )
    notifier.stop_all()
    assert result.success is True
    assert prepared
    assert len(prepared) > 1
    texts = [_request_payload(request)["content"]["text"] for request in prepared]
    assert all(len(request.body) <= 20000 for request in prepared)
    assert "FEISHU-TEXT-BEGIN" in "".join(texts)
    assert "FEISHU-TEXT-END" in "".join(texts)
    assert _without_page_markers(texts) == content


def test_public_wecom_requests_obey_each_official_content_budget(monkeypatch):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(max_retries=0)
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake"
    cases = [
        ("text", "URL-BEGIN https://example.invalid/" + "x" * 5000 + " URL-END", 2048),
        ("markdown", "| 表头 |\n| --- |\n| ROW-BEGIN " + "表" * 3500 + " ROW-END |", 4096),
        ("markdown", "标题相邻\n```python\n    CODE-BEGIN\n" + "    print('中文')\n" * 500 + "    CODE-END\n```", 4096),
    ]
    for kind, content, limit in cases:
        before = len(prepared)
        if kind == "text":
            result = notifier.send_text(url, content, async_send=False)
        else:
            result = notifier.send_markdown(url, content, async_send=False)
        assert result.success is True
        calls = prepared[before:]
        assert calls
        payloads = [_request_payload(request) for request in calls]
        field = "text" if kind == "text" else "markdown_v2"
        texts = [payload[field]["content"] for payload in payloads]
        assert all(len(text.encode("utf-8")) <= limit for text in texts)
        assert all(len(request.body) > 0 for request in calls)
        for marker in ("URL-BEGIN", "URL-END", "ROW-BEGIN", "ROW-END", "CODE-BEGIN", "CODE-END"):
            if marker in content:
                assert marker in "".join(texts)
        if kind == "text" or "ROW-BEGIN" in content:
            assert _without_page_markers(texts) == content
    notifier.stop_all()


def test_wecom_pool_entry_uses_text_budget(monkeypatch):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.core.pool_base.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(max_retries=0)
    content = "POOL-BEGIN" + "池" * 1500 + "POOL-END"
    result = notifier.send_text(
        ["https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-pool"],
        content,
        async_send=False,
    )
    notifier.stop_all()
    assert result.success is True
    assert prepared
    texts = [_request_payload(request)["text"]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= 2048 for text in texts)
    assert "POOL-BEGIN" in "".join(texts) and "POOL-END" in "".join(texts)


def test_moderation_expansion_is_resegmented_before_http(monkeypatch, tmp_path):
    prepared = _capture_prepared(monkeypatch)
    class _Words:
        text = "扩张词"
        @staticmethod
        def raise_for_status():
            return None
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Words())
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(
        max_retries=0,
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": ["https://words.invalid/list"],
            "strategy": "replace",
            "cache_dir": str(tmp_path),
            "log_sensitive_messages": False,
        },
    )
    result = notifier.send_text(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-review",
        "扩张词" * 227,
        async_send=False,
    )
    notifier.stop_all()
    assert result.success is True
    assert len(prepared) > 1
    texts = [_request_payload(request)["text"]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= 2048 for text in texts)
    assert "[敏感词]" in "".join(texts)


def test_moderation_block_still_fails_and_sends_the_existing_alert(monkeypatch, tmp_path):
    prepared = _capture_prepared(monkeypatch)

    class _Words:
        text = "唯一禁词"
        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Words())
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(
        max_retries=0,
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": ["https://words.invalid/block-list"],
            "strategy": "block",
            "cache_dir": str(tmp_path),
            "log_sensitive_messages": False,
        },
    )
    result = notifier.send_text(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-block",
        "唯一禁词",
        async_send=False,
    )
    notifier.stop_all()

    assert result.success is False
    assert result.error == "Content blocked by moderator"
    assert len(prepared) == 1
    alert_content = _request_payload(prepared[0])["text"]["content"]
    assert "敏感内容已拦截" in alert_content
    assert "唯一禁词" not in alert_content


def test_feishu_oversize_title_fails_before_first_post(monkeypatch):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire", lambda _limiter: None)
    notifier = FeishuNotifier(max_retries=0)
    result = notifier.send_card(
        "https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        "内容",
        title="题" * 4000,
        async_send=False,
    )
    notifier.stop_all()
    assert result.success is False
    assert "MESSAGE_SEGMENT_OVERSIZE" in result.error
    assert prepared == []


def test_segment_api_failure_after_first_card_is_reported_not_rolled_back(monkeypatch):
    prepared = []
    responses = [_Response(), _Response()]
    responses[1].json = lambda: {"code": 9499, "msg": "invalid"}

    def send(_session, request, **_kwargs):
        prepared.append(request)
        return responses[len(prepared) - 1]

    monkeypatch.setattr(requests.sessions.Session, "send", send)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire", lambda _limiter: None)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.time.sleep", lambda _delay: None)
    notifier = FeishuNotifier(max_retries=0)
    result = notifier.send_card(
        "https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        "失败测试" * 900,
        async_send=False,
    )
    notifier.stop_all()
    assert len(prepared) == 2
    assert result.success is False
    assert result.error


def test_markdown_preserves_blank_lines_indentation_and_closes_each_code_page():
    original = "正文\n\n\n标题相邻\n```python\n    CODE-BEGIN\n" + "    print('内容')\n" * 300 + "    CODE-END\n```"
    segments = MessageSegmenter(max_bytes=512).segment(original, "markdown_v2")
    assert len(segments) > 1
    assert all(len(segment.content.encode("utf-8")) <= 512 for segment in segments)
    code_segments = [segment.content for segment in segments if "```" in segment.content]
    assert len(code_segments) > 1
    assert all(segment.count("```") == 2 for segment in code_segments)
    assert "正文\n\n\n标题相邻\n```python\n    CODE-BEGIN\n" in code_segments[0]
    assert "    CODE-END\n\n```" in code_segments[-1]


def test_small_table_rows_repeat_header_on_each_continuation_page():
    content = "| 列 | 数值 |\n| --- | --- |\n" + "".join(f"| 行-{index} | {index} |\n" for index in range(100))
    segments = MessageSegmenter(max_bytes=128).segment(content, "markdown_v2")
    assert len(segments) > 1
    assert all(len(segment.content.encode("utf-8")) <= 128 for segment in segments)
    for segment in segments[1:]:
        assert "| 列 | 数值 |\n| --- | --- |" in segment.content
    for index in range(100):
        assert f"行-{index}" in "".join(segment.content for segment in segments)


def test_plain_text_reconstruction_preserves_blank_lines_and_unicode():
    original = "前缀\n\n\n缩进    🙂" + "文" * 100 + "\n尾行"
    segments = MessageSegmenter(max_bytes=48).segment(original, "text")
    reconstructed = "".join(
        re.sub(r"^\(Page \d+/\d+\)\n", "", segment.content)
        for segment in segments
    )
    assert reconstructed == original


def test_page_number_digit_growth_and_tiny_budget_are_bounded():
    segments = MessageSegmenter(max_bytes=48).segment("x" * 1000, "text")
    assert len(segments) > 10
    assert all(len(segment.content.encode("utf-8")) <= 48 for segment in segments)
    assert [segment.page_number for segment in segments] == list(range(1, len(segments) + 1))
    assert all(segment.total_pages == len(segments) for segment in segments)
    assert all(segment.content.startswith(f"(Page {index}/{len(segments)})\n")
               for index, segment in enumerate(segments, start=1))


def test_impossibly_small_segment_budget_fails_instead_of_looping():
    with pytest.raises(ValueError):
        MessageSegmenter(max_bytes=1).segment("🙂", "text")


@pytest.mark.parametrize("platform", ["wecom", "feishu"])
def test_ordinary_inline_link_stays_whole_when_a_long_markdown_line_splits(monkeypatch, platform):
    prepared = _capture_prepared(monkeypatch)
    link = "[useful](https://example.invalid/path)"
    if platform == "wecom":
        prefix = "x" * (3800 - len("(Page 1/2)\n".encode("utf-8")) - 1)
        monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
        monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
        monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
        notifier = WeComNotifier(max_retries=0)
        content = prefix + link + "z" * 300
        result = notifier.send_markdown(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-link",
            content,
            async_send=False,
        )
        texts = [_request_payload(request)["markdown_v2"]["content"] for request in prepared]
    else:
        prefix = "x" * 19750
        monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.time.sleep", lambda _delay: None)
        monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire", lambda _limiter: None)
        notifier = FeishuNotifier(max_retries=0)
        content = prefix + link + "z" * 300
        result = notifier.send_card(
            "https://open.feishu.cn/open-apis/bot/v2/hook/fake-link",
            content,
            async_send=False,
        )
        texts = [
            _request_payload(request)["card"]["body"]["elements"][0]["content"]
            for request in prepared
        ]
        budget = 20000
    notifier.stop_all()

    assert result.success is True
    assert len(prepared) > 1
    assert sum(link in text for text in texts) == 1
    for index, text in enumerate(texts, start=1):
        marker = f"(Page {index}/{len(texts)})\n"
        assert text.startswith(marker)
    assert "".join(text[len(f"(Page {index}/{len(texts)})\n"):]
                   for index, text in enumerate(texts, start=1)) == content
    if platform == "wecom":
        assert all(len(text.encode("utf-8")) <= 3800 for text in texts)
    else:
        assert all(len(request.body) <= budget for request in prepared)


@pytest.mark.parametrize("entry", ["single", "pool"])
def test_reviewed_multipage_text_gets_one_global_pagination_and_count(monkeypatch, tmp_path, entry):
    prepared = _capture_prepared(monkeypatch)

    class _Words:
        text = "扩张词"
        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: _Words())
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.pool_base.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(
        max_retries=0,
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": ["https://words.invalid/multipage-list"],
            "strategy": "replace",
            "cache_dir": str(tmp_path / entry),
            "log_sensitive_messages": False,
        },
    )
    reviewed_inputs = []
    reviewed_outputs = []
    moderate = notifier.content_moderator.moderate
    def record_review(**kwargs):
        reviewed_inputs.append(kwargs["content"])
        result = moderate(**kwargs)
        reviewed_outputs.append(result)
        return result
    notifier.content_moderator.moderate = record_review

    content = "用户页码：(Page 7/9)\n" + "扩张词" * 850 + "\n用户页码：(Page 2/3)\nUSER-BODY-END"
    urls = (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-multipage-single"
        if entry == "single"
        else [
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-multipage-pool-a",
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-multipage-pool-b",
        ]
    )
    result = notifier.send_text(urls, content, async_send=False)
    notifier.stop_all()

    assert result.success is True
    assert len(reviewed_inputs) > 1
    assert len(reviewed_inputs) == len(reviewed_outputs)
    assert "".join(reviewed_inputs) == content
    assert len(prepared) > len(reviewed_inputs)
    texts = [_request_payload(request)["text"]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= 2048 for text in texts)
    recovered = []
    for page, text in enumerate(texts, start=1):
        system_marker = f"(Page {page}/{len(texts)})\n"
        assert text.startswith(system_marker)
        recovered.append(text[len(system_marker):])
    reviewed_body = "".join(reviewed_outputs)
    assert "".join(recovered) == reviewed_body
    assert "用户页码：(Page 7/9)\n" in reviewed_body
    assert "用户页码：(Page 2/3)\nUSER-BODY-END" in reviewed_body
    if entry == "pool":
        assert result.segment_count == len(texts)


@pytest.mark.parametrize(
    "code_body",
    ["x" * 9000, "a\n" * 4500],
    ids=["single-long-line", "many-short-lines"],
)
def test_split_code_fences_are_standalone_and_restore_only_boundary_newlines(
    monkeypatch, code_body
):
    prepared = _capture_prepared(monkeypatch)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
    notifier = WeComNotifier(max_retries=0)
    source = "标题相邻\n```text\n" + code_body + "\n```\nAFTER-CODE\n普通段落\n"
    result = notifier.send_markdown(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-code-boundary",
        source,
        async_send=False,
    )
    notifier.stop_all()

    assert result.success is True
    assert len(prepared) > 1
    texts = [_request_payload(request)["markdown_v2"]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= 3800 for text in texts)
    recovered_body = []
    code_page_count = 0
    after_code_pages = []
    for page, text in enumerate(texts, start=1):
        system_marker = f"(Page {page}/{len(texts)})\n"
        assert text.startswith(system_marker)
        text = text[len(system_marker):]
        match = re.search(r"```text\n(.*?)\n```(?:\n|$)", text, re.DOTALL)
        if match:
            code_page_count += 1
            recovered_body.append(match.group(1))
            assert text.count("```") == 2
        if "AFTER-CODE" in text:
            assert "```" not in text
            after_code_pages.append(text)
    assert code_page_count > 1
    assert "".join(recovered_body) == code_body + "\n"
    assert after_code_pages
    assert "普通段落\n" in "".join(after_code_pages)
