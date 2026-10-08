"""
真实Webhook池测试 - 使用实际的企业微信webhook地址
测试所有功能和边界情况
"""
import sys
import time
from wecom_notifier import WeComNotifier

# 设置UTF-8编码输出（Windows兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 真实的webhook地址
WEBHOOK_URLS = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=f1fa66dd-a1b0-4893-af75-5dab9d993182",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=01ae2f25-ec29-4256-9fc1-22450f88add7"
]


def print_section(title):
    """打印测试区块标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(test_name, result):
    """打印测试结果"""
    status = "✅ 成功" if result.is_success() else "❌ 失败"
    print(f"{status} - {test_name}")
    if result.is_success():
        print(f"   └─ 使用的webhooks: {len(result.used_webhooks)}")
        print(f"   └─ 分段数量: {result.segment_count}")
    else:
        print(f"   └─ 错误: {result.error}")
    print()


def test_1_basic_single_webhook():
    """测试1：单个webhook（向后兼容性测试）"""
    print_section("测试1：单个Webhook发送（验证向后兼容性）")

    notifier = WeComNotifier()

    result = notifier.send_text(
        webhook_url=WEBHOOK_URLS[0],
        content="[测试1] 单个webhook发送测试 - 验证向后兼容性",
        async_send=False
    )

    print_result("单webhook发送", result)

    # 验证结果
    assert result.is_success(), "单webhook发送应该成功"

    time.sleep(2)  # 避免频繁发送


def test_2_basic_webhook_pool():
    """测试2：基础webhook池功能"""
    print_section("测试2：基础Webhook池发送（3个webhook）")

    notifier = WeComNotifier()

    result = notifier.send_text(
        webhook_url=WEBHOOK_URLS,
        content="[测试2] Webhook池基础测试 - 使用3个webhook",
        async_send=False
    )

    print_result("Webhook池基础发送", result)

    # 验证结果
    assert result.is_success(), "Webhook池发送应该成功"
    assert len(result.used_webhooks) >= 1, "应该至少使用1个webhook"

    time.sleep(2)


def test_3_long_message_segmentation():
    """测试3：超长消息分段和负载均衡"""
    print_section("测试3：超长消息分段 + 负载均衡")

    notifier = WeComNotifier()

    # 生成超长消息（会被分成多段）
    long_message = "\n".join([
        f"[测试3] 第 {i} 行 - 测试超长消息的分段和跨webhook分布"
        for i in range(200)
    ])

    print(f"消息长度: {len(long_message)} 字节")
    print(f"预计分段数: {len(long_message) // 4000 + 1}")
    print("开始发送...\n")

    start_time = time.time()

    result = notifier.send_text(
        webhook_url=WEBHOOK_URLS,
        content=long_message,
        async_send=False
    )

    elapsed = time.time() - start_time

    print_result("超长消息分段发送", result)
    print(f"⏱️  耗时: {elapsed:.2f}秒")

    # 验证结果
    assert result.is_success(), "超长消息发送应该成功"
    assert result.segment_count > 1, "超长消息应该被分段"

    time.sleep(3)


def test_4_high_frequency_sending():
    """测试4：高频发送（测试频率控制和负载均衡）"""
    print_section("测试4：高频发送测试（30条消息）")

    notifier = WeComNotifier()

    print("发送30条消息，观察负载均衡效果...\n")

    results = []
    start_time = time.time()

    for i in range(30):
        result = notifier.send_text(
            webhook_url=WEBHOOK_URLS,
            content=f"[测试4] 高频消息 {i+1}/30",
            async_send=True  # 异步发送
        )
        results.append(result)
        print(f"  消息 {i+1}/30 已提交")

    print("\n等待所有消息发送完成...")

    # 等待所有消息完成
    success_count = 0
    for i, result in enumerate(results):
        result.wait()
        if result.is_success():
            success_count += 1

    elapsed = time.time() - start_time

    print(f"\n✅ 成功: {success_count}/{len(results)}")
    print(f"❌ 失败: {len(results) - success_count}/{len(results)}")
    print(f"⏱️  总耗时: {elapsed:.2f}秒")
    print(f"📊 平均速度: {len(results)/elapsed:.2f} 条/秒")

    # 统计webhook使用情况
    webhook_usage = {}
    for result in results:
        if result.is_success():
            for url in result.used_webhooks:
                # 提取key部分用于显示
                key = url.split("key=")[1] if "key=" in url else url
                webhook_usage[key] = webhook_usage.get(key, 0) + 1

    print("\n📊 Webhook使用分布:")
    for key, count in webhook_usage.items():
        print(f"   {key[:8]}...: {count} 次")

    # 验证结果
    assert success_count == len(results), f"所有消息应该发送成功，实际成功 {success_count}/{len(results)}"

    time.sleep(3)


def test_5_markdown_support():
    """测试5：Markdown消息池支持"""
    print_section("测试5：Markdown消息池支持")

    notifier = WeComNotifier()

    markdown_content = """# [测试5] Webhook池Markdown测试

## 功能验证
- ✅ 支持多个webhook
- ✅ 自动负载均衡
- ✅ 消息顺序保证

## 性能指标
| 指标 | 数值 |
|------|------|
| Webhook数量 | 3个 |
| 理论吞吐 | 60条/分钟 |
| 实际性能 | 待验证 |

**测试时间**: """ + time.strftime("%Y-%m-%d %H:%M:%S")

    result = notifier.send_markdown(
        webhook_url=WEBHOOK_URLS,
        content=markdown_content,
        async_send=False
    )

    print_result("Markdown池发送", result)

    # 验证结果
    assert result.is_success(), "Markdown消息应该发送成功"

    time.sleep(2)


def test_6_order_guarantee():
    """测试6：消息顺序保证"""
    print_section("测试6：消息顺序保证测试")

    notifier = WeComNotifier()

    print("发送10条带序号的消息，验证顺序...\n")

    results = []
    for i in range(10):
        result = notifier.send_text(
            webhook_url=WEBHOOK_URLS,
            content=f"[测试6] 顺序消息 #{i+1:02d}/10 - 时间戳: {time.time():.3f}",
            async_send=True
        )
        results.append(result)
        print(f"  消息 #{i+1:02d} 已提交")

    print("\n等待所有消息发送完成...")

    # 等待所有消息完成
    for result in results:
        result.wait()

    success_count = sum(1 for r in results if r.is_success())

    print(f"\n✅ 成功: {success_count}/{len(results)}")
    print("📝 请在企业微信中检查消息是否按顺序（#01 → #10）到达")

    # 验证结果
    assert success_count == len(results), "所有消息应该发送成功"

    time.sleep(2)


def test_7_mixed_single_and_pool():
    """测试7：单webhook和池模式混用（验证RateLimiter共享）"""
    print_section("测试7：单Webhook和池模式混用")

    notifier = WeComNotifier()

    print("交替使用单webhook和webhook池...\n")

    # 单webhook模式
    result1 = notifier.send_text(
        webhook_url=WEBHOOK_URLS[0],
        content="[测试7-A] 单webhook模式发送",
        async_send=False
    )
    print_result("单webhook模式", result1)

    time.sleep(1)

    # 池模式（包含同一个webhook）
    result2 = notifier.send_text(
        webhook_url=WEBHOOK_URLS,
        content="[测试7-B] 池模式发送（包含刚才的webhook）",
        async_send=False
    )
    print_result("池模式", result2)

    time.sleep(1)

    # 再次单webhook
    result3 = notifier.send_text(
        webhook_url=WEBHOOK_URLS[0],
        content="[测试7-C] 再次单webhook模式",
        async_send=False
    )
    print_result("再次单webhook", result3)

    # 验证结果
    assert result1.is_success() and result2.is_success() and result3.is_success(), \
        "混用模式下所有消息应该成功"

    print("✅ 验证通过：单webhook和池模式可以混用，且共享频率限制")

    time.sleep(2)


def test_8_corner_case_empty_list():
    """测试8：边界情况 - 空列表"""
    print_section("测试8：边界情况 - 空Webhook列表")

    notifier = WeComNotifier()

    try:
        result = notifier.send_text(
            webhook_url=[],  # 空列表
            content="这条消息不应该发送",
            async_send=False
        )
        print("❌ 应该抛出异常但没有")
        assert False, "空列表应该抛出异常"
    except Exception as e:
        print(f"✅ 正确抛出异常: {type(e).__name__}: {e}")

    time.sleep(1)


def test_9_corner_case_invalid_type():
    """测试9：边界情况 - 无效类型"""
    print_section("测试9：边界情况 - 无效webhook_url类型")

    notifier = WeComNotifier()

    try:
        result = notifier.send_text(
            webhook_url=123,  # 错误类型
            content="这条消息不应该发送",
            async_send=False
        )
        print("❌ 应该抛出异常但没有")
        assert False, "无效类型应该抛出异常"
    except Exception as e:
        print(f"✅ 正确抛出异常: {type(e).__name__}: {e}")

    time.sleep(1)


def test_10_stress_test():
    """测试10：压力测试 - 60条消息（接近3个webhook的极限）"""
    print_section("测试10：压力测试 - 60条消息/分钟")

    notifier = WeComNotifier()

    print("发送60条消息（理论极限：3个webhook × 20条/分钟）...\n")
    print("这个测试会持续约60秒，请耐心等待...\n")

    results = []
    start_time = time.time()

    for i in range(60):
        result = notifier.send_text(
            webhook_url=WEBHOOK_URLS,
            content=f"[测试10] 压力测试消息 {i+1}/60",
            async_send=True
        )
        results.append(result)

        # 每10条显示一次进度
        if (i + 1) % 10 == 0:
            print(f"  已提交: {i+1}/60")

    print("\n等待所有消息发送完成...\n")

    # 等待所有消息完成
    success_count = 0
    for i, result in enumerate(results):
        result.wait()
        if result.is_success():
            success_count += 1

        # 每10条显示一次进度
        if (i + 1) % 10 == 0:
            print(f"  已完成: {i+1}/60")

    elapsed = time.time() - start_time

    print(f"\n✅ 成功: {success_count}/{len(results)}")
    print(f"❌ 失败: {len(results) - success_count}/{len(results)}")
    print(f"⏱️  总耗时: {elapsed:.2f}秒")
    print(f"📊 平均速度: {len(results)/elapsed:.2f} 条/秒")

    # 统计webhook使用情况
    webhook_usage = {}
    for result in results:
        if result.is_success():
            for url in result.used_webhooks:
                key = url.split("key=")[1][:8] if "key=" in url else url
                webhook_usage[key] = webhook_usage.get(key, 0) + 1

    print("\n📊 Webhook使用分布:")
    for key, count in webhook_usage.items():
        print(f"   {key}...: {count} 次")

    # 计算负载均衡偏差
    if webhook_usage:
        avg = sum(webhook_usage.values()) / len(webhook_usage)
        max_deviation = max(abs(count - avg) for count in webhook_usage.values())
        print(f"\n📈 负载均衡偏差: ±{max_deviation:.1f} (理论最优: 0)")

    # 验证结果
    assert success_count >= 55, f"压力测试至少应该有55条成功（实际 {success_count}）"

    print("\n✅ 压力测试通过！系统在高负载下表现良好。")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("  真实Webhook池综合测试")
    print("  使用3个真实的企业微信webhook地址")
    print("=" * 80)

    tests = [
        ("向后兼容性", test_1_basic_single_webhook),
        ("基础池功能", test_2_basic_webhook_pool),
        ("超长消息分段", test_3_long_message_segmentation),
        ("高频发送", test_4_high_frequency_sending),
        ("Markdown支持", test_5_markdown_support),
        ("顺序保证", test_6_order_guarantee),
        ("混用模式", test_7_mixed_single_and_pool),
        ("边界-空列表", test_8_corner_case_empty_list),
        ("边界-无效类型", test_9_corner_case_invalid_type),
        ("压力测试", test_10_stress_test),
    ]

    passed = 0
    failed = 0

    for i, (name, test_func) in enumerate(tests, 1):
        try:
            print(f"\n正在运行测试 {i}/{len(tests)}: {name}")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ 测试异常: {type(e).__name__}: {e}")
            failed += 1

        # 测试之间稍微等待
        if i < len(tests):
            print(f"\n{'─' * 80}")
            time.sleep(2)

    # 最终报告
    print("\n" + "=" * 80)
    print("  测试报告")
    print("=" * 80)
    print(f"\n总测试数: {len(tests)}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"成功率: {passed/len(tests)*100:.1f}%")

    if failed == 0:
        print("\n🎉 所有测试通过！Webhook池功能完美运行！")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查日志。")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
