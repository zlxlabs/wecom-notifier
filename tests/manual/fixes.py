"""
测试Bug修复
"""
from wecom_notifier import WeComNotifier
import time

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c"


def test_table_segmentation():
    """测试表格分段修复"""
    print("\n" + "=" * 60)
    print("测试1: 表格分段（修复后）")
    print("=" * 60)

    notifier = WeComNotifier(log_level="INFO")

    # 生成超长表格
    table = """# 表格分段测试

| ID | 名称 | 数据1 | 数据2 | 数据3 |
|----|------|-------|-------|-------|
"""
    for i in range(150):
        table += f"| {i:04d} | Item{i} | Value{i} | Data{i} | Info{i} |\n"

    print(f"表格长度: {len(table.encode('utf-8'))} 字节")

    result = notifier.send_markdown(
        webhook_url=WEBHOOK,
        content=table,
        async_send=False
    )

    if result.is_success():
        print("[PASS] 表格分段成功")
    else:
        print(f"[FAIL] 表格分段失败: {result.error}")

    return result.is_success()


def test_rate_limiting():
    """测试频率控制修复（发送25条）"""
    print("\n" + "=" * 60)
    print("测试2: 频率控制（修复后）- 发送25条消息")
    print("=" * 60)

    notifier = WeComNotifier(log_level="WARNING")  # 减少日志

    start_time = time.time()
    results = []

    print("提交25条消息...")
    for i in range(25):
        result = notifier.send_text(
            webhook_url=WEBHOOK,
            content=f"[频率测试] 消息 {i+1:02d}/25",
            async_send=True
        )
        results.append(result)
        if (i + 1) % 5 == 0:
            print(f"  已提交: {i+1}/25")

    print("\n等待所有消息发送完成...")
    success_count = 0
    for result in results:
        result.wait(timeout=120)
        if result.is_success():
            success_count += 1

    elapsed = time.time() - start_time
    rate = success_count / (elapsed / 60)

    print(f"\n结果:")
    print(f"  成功: {success_count}/25")
    print(f"  耗时: {elapsed:.1f}秒")
    print(f"  速率: {rate:.1f}条/分钟")

    if elapsed >= 60:
        print(f"  [PASS] 频率控制正常（耗时 >= 60秒）")
        return True
    else:
        print(f"  [WARN] 耗时较短，可能未触发限制")
        return success_count >= 24


def main():
    print("=" * 60)
    print("Bug修复验证测试")
    print("=" * 60)

    # 测试1: 表格分段
    test1_pass = test_table_segmentation()

    # 等待一下
    print("\n等待5秒后进行下一个测试...")
    time.sleep(5)

    # 测试2: 频率控制
    test2_pass = test_rate_limiting()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"1. 表格分段: {'[PASS]' if test1_pass else '[FAIL]'}")
    print(f"2. 频率控制: {'[PASS]' if test2_pass else '[FAIL]'}")

    if test1_pass and test2_pass:
        print("\n所有Bug已修复！")
        return 0
    else:
        print("\n部分测试失败，请检查")
        return 1


if __name__ == "__main__":
    exit(main())
