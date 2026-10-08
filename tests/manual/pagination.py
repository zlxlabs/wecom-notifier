"""
测试页码功能
"""
import sys
import io

# 设置标准输出编码为UTF-8（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from wecom_notifier import WeComNotifier

# Webhook地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=01ae2f25-ec29-4256-9fc1-22450f88add7"

def test_single_segment():
    """测试单段内容（不应显示页码）"""
    print("\n" + "="*60)
    print("测试 1: 单段内容（不显示页码）")
    print("="*60)

    notifier = WeComNotifier()

    content = "这是一条简短的测试消息，不会分段。"

    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content=content,
        async_send=False
    )

    if result.is_success():
        print("✅ 发送成功")
    else:
        print(f"❌ 发送失败: {result.error}")

    return result


def test_multi_segment_text():
    """测试多段文本内容（应显示页码）"""
    print("\n" + "="*60)
    print("测试 2: 多段文本内容（应显示页码）")
    print("="*60)

    notifier = WeComNotifier()

    # 生成足够长的内容，确保分段
    lines = []
    for i in range(200):
        lines.append(f"第 {i+1} 行：这是测试数据，用于验证长文本分段功能。")

    content = "\n".join(lines)

    result = notifier.send_text(
        webhook_url=WEBHOOK_URL,
        content=content,
        async_send=False
    )

    if result.is_success():
        print(f"✅ 发送成功，分段数: {result.segment_count}")
    else:
        print(f"❌ 发送失败: {result.error}")

    return result


def test_multi_segment_markdown():
    """测试多段Markdown内容（应显示页码）"""
    print("\n" + "="*60)
    print("测试 3: 多段Markdown内容（应显示页码）")
    print("="*60)

    notifier = WeComNotifier()

    # 生成长Markdown表格
    markdown_content = """# 测试报告

## 数据统计表

| 序号 | 名称 | 数值 | 状态 |
|------|------|------|------|
"""

    # 添加足够多的表格行
    for i in range(150):
        markdown_content += f"| {i+1} | 项目{i+1} | {1000+i} | ✅ 正常 |\n"

    markdown_content += "\n## 总结\n这是一个测试Markdown长文本分段的示例。"

    result = notifier.send_markdown(
        webhook_url=WEBHOOK_URL,
        content=markdown_content,
        async_send=False
    )

    if result.is_success():
        print(f"✅ 发送成功，分段数: {result.segment_count}")
    else:
        print(f"❌ 发送失败: {result.error}")

    return result


if __name__ == "__main__":
    print("\n🚀 开始测试页码功能...")

    # 测试1: 单段（不显示页码）
    result1 = test_single_segment()

    # 等待一下，避免频率限制
    import time
    time.sleep(3)

    # 测试2: 多段文本（显示页码）
    result2 = test_multi_segment_text()

    # 等待一下
    time.sleep(3)

    # 测试3: 多段Markdown（显示页码）
    result3 = test_multi_segment_markdown()

    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    print(f"测试1（单段文本）: {'✅ 成功' if result1.is_success() else '❌ 失败'}")
    print(f"测试2（多段文本）: {'✅ 成功' if result2.is_success() else '❌ 失败'}")
    print(f"测试3（多段Markdown）: {'✅ 成功' if result3.is_success() else '❌ 失败'}")
    print("\n🎉 所有测试完成！请检查企业微信群聊查看页码效果。")
