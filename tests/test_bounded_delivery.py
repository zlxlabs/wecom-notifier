"""端到端锁定有界消息计划与真实 requests PreparedRequest 边界。"""
import json
import re

import pytest
import requests

from wecom_notifier.core.segmenter import MessageSegmenter
from wecom_notifier.platforms.feishu.constants import DEFAULT_CARD_TEMPLATE
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


def _patch_notifier_waits(monkeypatch, platform):
    if platform == "wecom":
        monkeypatch.setattr("wecom_notifier.platforms.wecom.manager.time.sleep", lambda _delay: None)
        monkeypatch.setattr("wecom_notifier.platforms.wecom.sender.time.sleep", lambda _delay: None)
        monkeypatch.setattr("wecom_notifier.core.rate_limiter.RateLimiter.acquire", lambda _limiter: None)
        return
    monkeypatch.setattr("wecom_notifier.platforms.feishu.notifier.time.sleep", lambda _delay: None)
    monkeypatch.setattr("wecom_notifier.platforms.feishu.sender.time.sleep", lambda _delay: None)
    monkeypatch.setattr(
        "wecom_notifier.platforms.feishu.notifier.DualRateLimiter.acquire",
        lambda _limiter: None,
    )


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


def _assert_global_pages(texts):
    assert texts
    stripped = []
    for index, text in enumerate(texts, start=1):
        marker = f"(Page {index}/{len(texts)})\n"
        assert text.startswith(marker)
        stripped.append(text[len(marker):])
    return stripped


@pytest.mark.parametrize(
    "channel,prefix_len,follow,tail,budget",
    [
        ("wecom_text", 2048 - 3, "\n中", "z" * 2500, 2048),
        ("wecom_markdown", 3800 - 3, "\n中", "z" * 300, 3800),
        ("wecom_markdown", 3800 - 2, "\n中", "z" * 300, 3800),
        ("wecom_markdown", 3800 - 1, "y", "z" * 300, 3800),
        ("feishu_card", None, "\n🙂", "z" * 80, 20000),
    ],
    ids=[
        "wecom-text-remainder-2",
        "wecom-md-remainder-2-chinese",
        "wecom-md-remainder-1-chinese",
        "wecom-md-remainder-1-ascii-fits",
        "feishu-card-remainder-2-emoji-wire",
    ],
)
def test_unicode_advances_page_when_remainder_is_below_character_cost(
    monkeypatch, channel, prefix_len, follow, tail, budget
):
    prepared = _capture_prepared(monkeypatch)
    if channel == "feishu_card":
        _patch_notifier_waits(monkeypatch, "feishu")
        notifier = FeishuNotifier(max_retries=0, secret="test-signature-secret")
        url = "https://open.feishu.cn/open-apis/bot/v2/hook/fake-unicode-frontier"
        title = "标题"
        empty = notifier.sender._card_body_size(url, "", title, DEFAULT_CARD_TEMPLATE)
        content_budget = budget - empty
        assert content_budget > 12
        content = "x" * (content_budget - 3) + follow + tail
        result = notifier.send_card(url, content, title=title, async_send=False)
        notifier.stop_all()
        assert result.success is True
        assert result.error is None
        assert prepared
        assert len(prepared) > 1
        texts = [_request_payload(request)["card"]["body"]["elements"][0]["content"]
                 for request in prepared]
        assert all(len(request.body) <= budget for request in prepared)
        assert all(len(request.body) > 0 for request in prepared)
        assert "".join(_assert_global_pages(texts)) == content
        return

    _patch_notifier_waits(monkeypatch, "wecom")
    notifier = WeComNotifier(max_retries=0)
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-unicode-frontier"
    content = "x" * prefix_len + follow + tail
    if channel == "wecom_text":
        result = notifier.send_text(url, content, async_send=False)
        field = "text"
    else:
        result = notifier.send_markdown(url, content, async_send=False)
        field = "markdown_v2"
    notifier.stop_all()
    assert result.success is True
    assert result.error is None
    assert prepared
    assert len(prepared) > 1
    texts = [_request_payload(request)[field]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= budget for text in texts)
    assert all(len(text.encode("utf-8")) > 0 for text in texts)
    assert "".join(_assert_global_pages(texts)) == content


def test_single_markdown_character_larger_than_empty_page_still_fails():
    with pytest.raises(ValueError, match="one character exceeds budget"):
        MessageSegmenter(max_bytes=2).segment("中", "markdown_v2")


_SMALL_PYTHON_BLOCK = "```python\n    print(\"small block\")\n```\n"


@pytest.mark.parametrize("platform", ["wecom", "feishu"])
def test_whole_fit_code_block_moves_intact_when_current_page_has_no_room(
    monkeypatch, platform
):
    prepared = _capture_prepared(monkeypatch)
    code = _SMALL_PYTHON_BLOCK
    assert len(code.encode("utf-8")) == 39
    if platform == "wecom":
        _patch_notifier_waits(monkeypatch, "wecom")
        notifier = WeComNotifier(max_retries=0)
        content = "x" * 3768 + "\n" + code + "AFTER-CODE\n"
        result = notifier.send_markdown(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-small-code",
            content,
            async_send=False,
        )
        texts = [_request_payload(request)["markdown_v2"]["content"] for request in prepared]
        budget_ok = all(len(text.encode("utf-8")) <= 3800 for text in texts)
    else:
        _patch_notifier_waits(monkeypatch, "feishu")
        notifier = FeishuNotifier(max_retries=0, secret="test-signature-secret")
        url = "https://open.feishu.cn/open-apis/bot/v2/hook/fake-small-code"
        title = "标题"
        empty = notifier.sender._card_body_size(url, "", title, DEFAULT_CARD_TEMPLATE)
        content_budget = 20000 - empty
        marker_cost = notifier.sender._content_wire_size("(Page 1/2)\n")
        content = "x" * (content_budget - marker_cost - 20) + "\n" + code + "AFTER-CODE\n"
        result = notifier.send_card(url, content, title=title, async_send=False)
        texts = [_request_payload(request)["card"]["body"]["elements"][0]["content"]
                 for request in prepared]
        budget_ok = all(len(request.body) <= 20000 for request in prepared)
    notifier.stop_all()

    assert result.success is True
    assert result.error is None
    assert prepared
    assert len(prepared) > 1
    assert budget_ok
    stripped = _assert_global_pages(texts)
    assert "".join(stripped) == content
    fence_counts = [text.count("```") for text in stripped]
    assert all(count in (0, 2) for count in fence_counts)
    code_pages = [text for text in stripped if code in text]
    assert len(code_pages) == 1
    assert not code_pages[0].startswith("x")
    after_pages = [text for text in stripped if "AFTER-CODE" in text]
    assert after_pages
    assert all(text[:text.index("AFTER-CODE")].count("```") % 2 == 0 for text in after_pages)


@pytest.mark.parametrize(
    "with_prefix,code_body",
    [
        (True, "中文\n\n    indent\n" * 500),
        (True, "🙂\n\n\tcode\n" * 500),
        (False, "中文\n\n    indent\n" * 500),
    ],
    ids=["prefix-remainder-below-chinese", "prefix-remainder-below-emoji", "empty-current-chinese"],
)
def test_oversize_code_first_slice_remainder_below_body_char_still_splits(
    monkeypatch, with_prefix, code_body
):
    prepared = _capture_prepared(monkeypatch)
    _patch_notifier_waits(monkeypatch, "wecom")
    notifier = WeComNotifier(max_retries=0)
    prefix = ("x" * 3783 + "\n") if with_prefix else ""
    source = prefix + "```python\n" + code_body + "\n```\nAFTER-CODE\n普通段落\n"
    result = notifier.send_markdown(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake-code-first-slice",
        source,
        async_send=False,
    )
    notifier.stop_all()

    assert result.success is True
    assert result.error is None
    assert prepared
    assert len(prepared) > 1
    texts = [_request_payload(request)["markdown_v2"]["content"] for request in prepared]
    assert all(len(text.encode("utf-8")) <= 3800 for text in texts)
    recovered_body = []
    code_page_count = 0
    after_code_pages = []
    stripped_pages = []
    for page, text in enumerate(texts, start=1):
        marker = f"(Page {page}/{len(texts)})\n"
        assert text.startswith(marker)
        body = text[len(marker):]
        stripped_pages.append(body)
        match = re.search(r"```python\n(.*?)\n```(?:\n|$)", body, re.DOTALL)
        if match:
            code_page_count += 1
            recovered_body.append(match.group(1))
            assert body.count("```") == 2
            assert re.search(r"(?:^|\n)```python\n", body)
            assert re.search(r"\n```(?:\n|$)", body)
        if "AFTER-CODE" in body:
            assert "```" not in body
            after_code_pages.append(body)
    assert code_page_count > 1
    assert "".join(recovered_body) == code_body + "\n"
    assert "    indent" in "".join(recovered_body) or "\tcode" in "".join(recovered_body)
    assert "\n\n" in "".join(recovered_body)
    assert after_code_pages
    assert "普通段落\n" in "".join(after_code_pages)
    if with_prefix:
        assert any(page.startswith("x") and "```" not in page for page in stripped_pages)
