import time


def main():
    from wecom_notifier import WeComNotifier
    import wecom_notifier.sender as sender_mod
    import wecom_notifier.rate_limiter as rl_mod
    import wecom_notifier.notifier as notifier_mod

    # Metrics for validation
    call_count = {"total": 0}

    class FakeResponse:
        def __init__(self, data=None):
            self._data = data or {"errcode": 0, "errmsg": "ok"}
            self.status_code = 200
            self.text = "ok"

        def json(self):
            return self._data

    def fake_post(url, json=None, timeout=None, headers=None):
        call_count["total"] += 1
        if "invalid" in url:
            return FakeResponse({"errcode": 400, "errmsg": "invalid url"})
        return FakeResponse()

    # Monkeypatch HTTP
    sender_mod.requests.post = fake_post

    # Fast RateLimiter for testing: 2 req/sec
    class FastRateLimiter(rl_mod.RateLimiter):
        def __init__(self):
            super().__init__(max_count=2, time_window=1)

    rl_mod.RateLimiter = FastRateLimiter
    notifier_mod.RateLimiter = FastRateLimiter

    notifier = WeComNotifier(log_level="ERROR")
    webhook_ok_1 = "https://example.com/webhook-1"
    webhook_ok_2 = "https://example.com/webhook-2"

    # 1. Text
    res_text = notifier.send_text(webhook_url=webhook_ok_1, content="Hello", async_send=False)
    print("text:", res_text.is_success(), res_text.error)

    # 2. Markdown + @all workaround
    start_calls = call_count["total"]
    res_md = notifier.send_markdown(webhook_url=webhook_ok_1, content="# T\n- x", mention_all=True, async_send=False)
    extra_calls = call_count["total"] - start_calls
    print("markdown:", res_md.is_success(), res_md.error, f"extra_calls={extra_calls}")

    # 3. Image via base64 (1x1 PNG)
    png_1x1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )
    res_img = notifier.send_image(webhook_url=webhook_ok_1, image_base64=png_1x1, mention_all=False, async_send=False)
    print("image:", res_img.is_success(), res_img.error)

    # 4. Segmentation should produce >1 HTTP call
    long_text = "A" * 4200 + "B" * 1000
    start_calls = call_count["total"]
    t0 = time.time()
    res_seg = notifier.send_text(webhook_url=webhook_ok_1, content=long_text, async_send=False)
    dt = time.time() - t0
    seg_calls = call_count["total"] - start_calls
    print("segmented_text:", res_seg.is_success(), f"calls={seg_calls}", f"elapsed={dt:.2f}s")

    # 5. Concurrent (5 async)
    results = []
    for i in range(5):
        results.append(
            notifier.send_text(webhook_url=webhook_ok_1, content=f"C{i}", async_send=True)
        )
    ok = 0
    for r in results:
        r.wait(timeout=10)
        ok += 1 if r.is_success() else 0
    print("concurrent:", ok == 5, f"ok={ok}/5")

    # 6. Multi-webhook
    r1 = notifier.send_text(webhook_url=webhook_ok_1, content="A", async_send=False)
    r2 = notifier.send_text(webhook_url=webhook_ok_2, content="B", async_send=False)
    print("multi_webhook:", r1.is_success() and r2.is_success())

    # 7. Rate limiting (3 texts with 2/sec gate -> >=1s)
    t0 = time.time()
    rs = []
    for i in range(3):
        rs.append(notifier.send_text(webhook_url=webhook_ok_1, content=f"R{i}", async_send=True))
    for r in rs:
        r.wait(timeout=5)
    elapsed = time.time() - t0
    print("rate_limit:", elapsed >= 1.0, f"elapsed={elapsed:.2f}s")

    # 8. Error handling (invalid URL should fail)
    r_err = notifier.send_text(webhook_url="https://invalid-url.com", content="X", async_send=False)
    print("error_handling:", not r_err.is_success(), r_err.error is not None)


if __name__ == "__main__":
    main()

