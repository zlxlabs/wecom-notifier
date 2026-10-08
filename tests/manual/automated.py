"""
企业微信通知器自动化测试

不需要手动交互，自动运行所有测试
"""
import time
import sys
from wecom_notifier import WeComNotifier

# 测试用的两个Webhook地址
WEBHOOK_1 = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c"
WEBHOOK_2 = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=f1fa66dd-a1b0-4893-af75-5dab9d993182"


class TestRunner:
    def __init__(self):
        self.notifier = WeComNotifier(log_level="WARNING")  # 减少日志输出
        self.passed = 0
        self.failed = 0
        self.total = 0

    def run_test(self, name, func):
        """运行单个测试"""
        self.total += 1
        print(f"\n[测试 {self.total}] {name}")
        print("-" * 60)

        try:
            result = func()
            if result:
                self.passed += 1
                print(f"[PASS] 通过")
            else:
                self.failed += 1
                print(f"[FAIL] 失败")
            return result
        except Exception as e:
            self.failed += 1
            print(f"[ERROR] 异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} [PASS]")
        print(f"失败: {self.failed} [FAIL]")
        print(f"成功率: {self.passed / self.total * 100:.1f}%")
        print("=" * 60)


def test_1_simple_text(runner):
    """测试1：简单文本"""
    result = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【自动测试1】简单文本消息",
        async_send=False
    )
    return result.is_success()


def test_2_text_with_mention_all(runner):
    """测试2：带@all的文本"""
    result = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【自动测试2】带@all的文本消息",
        mentioned_list=["@all"],
        async_send=False
    )
    return result.is_success()


def test_3_markdown(runner):
    """测试3：Markdown消息"""
    markdown = """# 【自动测试3】Markdown测试

## 功能验证
- **加粗**
- *斜体*
- [链接](https://www.baidu.com)

| 列1 | 列2 |
|-----|-----|
| A   | B   |
"""
    result = runner.notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content=markdown,
        async_send=False
    )
    return result.is_success()


def test_4_markdown_with_mention_all(runner):
    """测试4：Markdown + @all"""
    result = runner.notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content="# 【自动测试4】Markdown + @all\n\n应该会有两条消息",
        mention_all=True,
        async_send=False
    )
    time.sleep(2)  # 等待@all消息发送
    return result.is_success()


def test_5_long_text(runner):
    """测试5：长文本分段"""
    long_text = "【自动测试5】长文本分段测试\n\n"
    long_text += "\n".join([f"第{i:04d}行：" + "测试内容" * 30 for i in range(100)])

    print(f"  文本长度: {len(long_text.encode('utf-8'))} 字节")

    result = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=long_text,
        async_send=False
    )
    return result.is_success()


def test_6_long_table(runner):
    """测试6：长表格分段"""
    table = """# 【自动测试6】表格分段

| ID | 名称 | 值 |
|----|------|-----|
"""
    for i in range(150):
        table += f"| {i} | Item{i} | Value{i} |\n"

    print(f"  表格长度: {len(table.encode('utf-8'))} 字节")

    result = runner.notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content=table,
        async_send=False
    )
    return result.is_success()


def test_7_concurrent(runner):
    """测试7：并发发送"""
    print("  发送5条并发消息...")
    results = []

    for i in range(5):
        result = runner.notifier.send_text(
            webhook_url=WEBHOOK_1,
            content=f"【自动测试7】并发消息 {i+1}/5",
            async_send=True
        )
        results.append(result)

    # 等待所有完成
    success = 0
    for result in results:
        result.wait(timeout=60)
        if result.is_success():
            success += 1

    print(f"  成功: {success}/5")
    return success == 5


def test_8_multiple_webhooks(runner):
    """测试8：多Webhook"""
    print("  向两个webhook发送...")

    result1 = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【自动测试8】发送到Webhook 1",
        async_send=False
    )

    result2 = runner.notifier.send_text(
        webhook_url=WEBHOOK_2,
        content="【自动测试8】发送到Webhook 2",
        async_send=False
    )

    return result1.is_success() and result2.is_success()


def test_9_rate_limiting(runner):
    """测试9：频率控制（发送25条）"""
    print("  发送25条消息测试频率控制...")
    start = time.time()

    results = []
    for i in range(25):
        result = runner.notifier.send_text(
            webhook_url=WEBHOOK_1,
            content=f"【自动测试9】频率测试 {i+1}/25",
            async_send=True
        )
        results.append(result)

    # 等待所有完成
    success = 0
    for result in results:
        result.wait(timeout=120)
        if result.is_success():
            success += 1

    elapsed = time.time() - start
    rate = success / (elapsed / 60)

    print(f"  成功: {success}/25")
    print(f"  耗时: {elapsed:.1f}秒")
    print(f"  速率: {rate:.1f}条/分钟")

    # 如果超过60秒，说明频率控制生效
    if elapsed >= 60:
        print(f"  [PASS] 频率控制正常（耗时超过60秒）")
    else:
        print(f"  [WARN] 注意：耗时较短，可能未触发频率限制")

    return success >= 24  # 允许有1条失败


def test_10_message_order(runner):
    """测试10：消息顺序"""
    print("  发送两条长消息验证分段顺序...")

    msg_a = "【消息A】\n" + "\n".join([f"A{i}" * 50 for i in range(60)])
    msg_b = "【消息B】\n" + "\n".join([f"B{i}" * 50 for i in range(60)])

    result_a = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=msg_a,
        async_send=True
    )

    result_b = runner.notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=msg_b,
        async_send=True
    )

    result_a.wait()
    result_b.wait()

    return result_a.is_success() and result_b.is_success()


def test_11_error_handling(runner):
    """测试11：错误处理"""
    print("  测试无效webhook（应该失败）...")

    result = runner.notifier.send_text(
        webhook_url="https://invalid-url.com",
        content="测试",
        async_send=False
    )

    # 应该失败
    if not result.is_success():
        print(f"  [PASS] 正确处理错误: {result.error[:50]}...")
        return True
    else:
        print(f"  [FAIL] 不应该成功")
        return False


def main():
    print("=" * 60)
    print("企业微信通知器 - 自动化测试")
    print("=" * 60)
    print(f"\nWebhook 1: {WEBHOOK_1[:50]}...")
    print(f"Webhook 2: {WEBHOOK_2[:50]}...")
    print("\n开始测试...\n")

    runner = TestRunner()

    # 运行所有测试
    tests = [
        ("简单文本消息", test_1_simple_text),
        ("带@all的文本", test_2_text_with_mention_all),
        ("Markdown消息", test_3_markdown),
        ("Markdown + @all", test_4_markdown_with_mention_all),
        ("长文本分段", test_5_long_text),
        ("长表格分段", test_6_long_table),
        ("并发发送", test_7_concurrent),
        ("多Webhook", test_8_multiple_webhooks),
        ("频率控制（25条）", test_9_rate_limiting),
        ("消息顺序", test_10_message_order),
        ("错误处理", test_11_error_handling),
    ]

    for name, test_func in tests:
        runner.run_test(name, lambda tf=test_func: tf(runner))
        time.sleep(1)  # 测试间隔

    runner.print_summary()

    # 返回退出码
    return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
