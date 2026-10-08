"""
内容审核功能测试

测试三种审核策略：
1. block - 拒绝发送
2. replace - 替换为[敏感词]
3. pinyin_reverse - 拼音/字母倒置
"""
import time
from wecom_notifier import WeComNotifier

# 测试配置
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=5df8967d-0180-435f-ac18-12ada9d40256"
SENSITIVE_WORD_URL = "https://raw.githubusercontent.com/konsheng/Sensitive-lexicon/refs/heads/main/Vocabulary/%E6%96%B0%E6%80%9D%E6%83%B3%E5%90%AF%E8%92%99.txt"


def test_block_strategy():
    """测试拒绝发送策略"""
    print("\n" + "=" * 60)
    print("测试策略1: Block - 拒绝发送")
    print("=" * 60)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "block",
        }
    )

    # 测试1：包含敏感词的消息（应该被拒绝）
    print("\n[测试1] 发送包含敏感词的消息（应被拒绝）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条关于梭哈结婚的讨论，谈到了供养者思维的问题",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    time.sleep(2)

    # 测试2：正常消息（应该通过）
    print("\n[测试2] 发送正常消息（应通过）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条正常的测试消息，没有任何问题",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()
    print("\n[OK] Block 策略测试完成")


def test_replace_strategy():
    """测试替换策略"""
    print("\n" + "=" * 60)
    print("测试策略2: Replace - 替换为[敏感词]")
    print("=" * 60)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "replace",
        }
    )

    # 测试：包含敏感词的消息（应该被替换）
    print("\n[测试] 发送包含敏感词的消息（应被替换）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条关于梭哈买房和供养者思维的讨论，系统会自动替换敏感词",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()
    print("\n[OK] Replace 策略测试完成")


def test_pinyin_reverse_strategy():
    """测试拼音倒置策略"""
    print("\n" + "=" * 60)
    print("测试策略3: Pinyin Reverse - 拼音/字母倒置")
    print("=" * 60)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "pinyin_reverse",
        }
    )

    # 测试：包含敏感词的消息（应该被倒置）
    print("\n[测试] 发送包含敏感词的消息（应被倒置）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条关于梭哈结婚和供养者思维的消息，中文会转拼音首字母倒置",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()
    print("\n[OK] Pinyin Reverse 策略测试完成")


def test_markdown_moderation():
    """测试Markdown消息的审核"""
    print("\n" + "=" * 60)
    print("测试Markdown消息审核")
    print("=" * 60)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "replace",
        }
    )

    # 测试：Markdown消息
    print("\n[测试] 发送包含敏感词的Markdown消息...")
    markdown_content = """# 测试报告

## 内容
- 这是关于梭哈买房的讨论
- 另一行涉及供养者思维的内容

**重要**: 系统会自动处理敏感词
"""
    result = notifier.send_markdown(
        webhook_url=WEBHOOK_URL,
        content=markdown_content,
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()
    print("\n[OK] Markdown 审核测试完成")


def test_disabled_moderation():
    """测试关闭审核功能"""
    print("\n" + "=" * 60)
    print("测试关闭审核功能")
    print("=" * 60)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=False  # 关闭审核
    )

    # 测试：包含敏感词的消息（应该正常发送）
    print("\n[测试] 发送包含敏感词的消息（审核已关闭，应正常发送）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条关于梭哈结婚和供养者思维的消息，审核功能已关闭",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()
    print("\n[OK] 关闭审核测试完成")


def main():
    """主测试函数"""
    print("开始内容审核功能测试...")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"敏感词URL: {SENSITIVE_WORD_URL}")

    try:
        # 测试1：Block策略
        test_block_strategy()
        time.sleep(3)

        # 测试2：Replace策略
        test_replace_strategy()
        time.sleep(3)

        # 测试3：Pinyin Reverse策略
        test_pinyin_reverse_strategy()
        time.sleep(3)

        # 测试4：Markdown消息
        test_markdown_moderation()
        time.sleep(3)

        # 测试5：关闭审核
        test_disabled_moderation()

        print("\n" + "=" * 60)
        print("[OK] 所有测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
