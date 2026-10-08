"""
敏感消息日志记录功能测试

验证敏感消息是否正确记录到日志文件
"""
import json
import os
import time
from wecom_notifier import WeComNotifier

# 测试配置
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=5df8967d-0180-435f-ac18-12ada9d40256"
SENSITIVE_WORD_URL = "https://raw.githubusercontent.com/konsheng/Sensitive-lexicon/refs/heads/main/Vocabulary/%E6%96%B0%E6%80%9D%E6%83%B3%E5%90%AF%E8%92%99.txt"
LOG_FILE = ".wecom_cache/moderation_test.log"


def read_log_file():
    """读取日志文件内容"""
    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    logs = []
    for line in lines:
        try:
            logs.append(json.loads(line.strip()))
        except:
            pass

    return logs


def test_logging_enabled():
    """测试日志记录功能（启用）"""
    print("\n" + "=" * 60)
    print("测试1: 日志记录功能（启用）")
    print("=" * 60)

    # 清空旧日志
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "replace",
            "log_sensitive_messages": True,
            "log_file": LOG_FILE,
        }
    )

    print("\n[测试1.1] 发送包含敏感词的消息...")
    result1 = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是第一条关于梭哈结婚的测试消息",
        async_send=False
    )
    print(f"结果: {'成功' if result1.is_success() else f'失败 - {result1.error}'}")
    print(f"消息ID: {result1.message_id}")

    time.sleep(2)

    print("\n[测试1.2] 发送另一条包含敏感词的消息...")
    result2 = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是第二条关于供养者思维的测试消息",
        async_send=False
    )
    print(f"结果: {'成功' if result2.is_success() else f'失败 - {result2.error}'}")
    print(f"消息ID: {result2.message_id}")

    time.sleep(2)

    print("\n[测试1.3] 发送正常消息（不应记录）...")
    result3 = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是一条完全正常的消息，没有任何问题",
        async_send=False
    )
    print(f"结果: {'成功' if result3.is_success() else f'失败 - {result3.error}'}")

    notifier.stop_all()

    # 检查日志文件
    print("\n" + "-" * 60)
    print("检查日志文件...")
    logs = read_log_file()

    print(f"日志文件路径: {LOG_FILE}")
    print(f"记录条数: {len(logs)}")

    if len(logs) == 2:
        print("[OK] 正确记录了2条敏感消息")

        for i, log in enumerate(logs, 1):
            print(f"\n记录 {i}:")
            print(f"  消息ID: {log['message_id']}")
            print(f"  时间戳: {log['timestamp']}")
            print(f"  策略: {log['strategy']}")
            print(f"  消息类型: {log['msg_type']}")
            print(f"  检测到的敏感词: {log['detected_words']}")
            print(f"  原始内容: {log['original_content'][:50]}...")
    else:
        print(f"[ERROR] 预期2条记录，实际{len(logs)}条")


def test_logging_disabled():
    """测试日志记录功能（禁用）"""
    print("\n" + "=" * 60)
    print("测试2: 日志记录功能（禁用）")
    print("=" * 60)

    # 使用不同的日志文件
    log_file_2 = ".wecom_cache/moderation_test2.log"
    if os.path.exists(log_file_2):
        try:
            os.remove(log_file_2)
        except:
            pass

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "replace",
            "log_sensitive_messages": False,  # 禁用日志
        }
    )

    print("\n[测试] 发送包含敏感词的消息（不应记录）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是关于梭哈结婚的测试消息",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()

    # 检查日志文件
    print("\n" + "-" * 60)
    print("检查日志文件...")

    if not os.path.exists(log_file_2):
        print(f"[OK] 日志文件未创建（符合预期）")
    else:
        print(f"[ERROR] 日志文件不应该被创建")


def test_block_strategy_logging():
    """测试Block策略的日志记录"""
    print("\n" + "=" * 60)
    print("测试3: Block策略的日志记录")
    print("=" * 60)

    # 使用不同的日志文件
    log_file_3 = ".wecom_cache/moderation_test3.log"
    if os.path.exists(log_file_3):
        try:
            os.remove(log_file_3)
        except:
            pass

    notifier = WeComNotifier(
        log_level="INFO",
        enable_content_moderation=True,
        moderation_config={
            "sensitive_word_urls": [SENSITIVE_WORD_URL],
            "strategy": "block",
            "log_sensitive_messages": True,
            "log_file": log_file_3,
        }
    )

    print("\n[测试] 发送包含敏感词的消息（应被拒绝并记录）...")
    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content="这是关于梭哈买房和供养者思维的讨论",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else f'失败 - {result.error}'}")

    notifier.stop_all()

    # 检查日志文件
    print("\n" + "-" * 60)
    print("检查日志文件...")

    # 读取log_file_3
    if not os.path.exists(log_file_3):
        print(f"[ERROR] 日志文件未创建")
        return

    with open(log_file_3, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    logs = []
    for line in lines:
        try:
            logs.append(json.loads(line.strip()))
        except:
            pass

    if len(logs) == 1:
        print("[OK] 记录了1条被拒绝的消息")
        log = logs[0]
        print(f"  策略: {log['strategy']}")
        print(f"  检测到的敏感词数量: {len(log['detected_words'])}")
        print(f"  原始内容: {log['original_content']}")
    else:
        print(f"[ERROR] 预期1条记录，实际{len(logs)}条")


def main():
    """主测试函数"""
    print("开始敏感消息日志记录功能测试...")

    try:
        # 测试1：日志记录启用
        test_logging_enabled()
        time.sleep(3)

        # 测试2：日志记录禁用
        test_logging_disabled()
        time.sleep(3)

        # 测试3：Block策略
        test_block_strategy_logging()

        print("\n" + "=" * 60)
        print("[OK] 所有测试完成！")
        print("=" * 60)

        # 显示最终日志文件信息
        if os.path.exists(LOG_FILE):
            file_size = os.path.getsize(LOG_FILE)
            print(f"\n最终日志文件: {LOG_FILE}")
            print(f"文件大小: {file_size} 字节")

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
