"""
快速测试 - 验证基础功能
"""
from wecom_notifier import WeComNotifier

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c"

def main():
    print("快速测试开始...")

    notifier = WeComNotifier(log_level="INFO")

    # 测试1：简单文本
    print("\n[测试1] 简单文本")
    result = notifier.send_text(
        webhook_url=WEBHOOK,
        content="[快速测试1] 这是一条简单文本消息",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else '失败 - ' + str(result.error)}")

    # 测试2：带@all
    print("\n[测试2] 带@all的文本")
    result = notifier.send_text(
        webhook_url=WEBHOOK,
        content="[快速测试2] 带@all的消息",
        mentioned_list=["@all"],
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else '失败 - ' + str(result.error)}")

    # 测试3: Markdown
    print("\n[测试3] Markdown消息")
    result = notifier.send_markdown(
        webhook_url=WEBHOOK,
        content="# [快速测试3] Markdown\n\n- 项目1\n- 项目2",
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else '失败 - ' + str(result.error)}")

    # 测试4: Markdown + @all
    print("\n[测试4] Markdown + @all")
    result = notifier.send_markdown(
        webhook_url=WEBHOOK,
        content="# [快速测试4] Markdown with @all",
        mention_all=True,
        async_send=False
    )
    print(f"结果: {'成功' if result.is_success() else '失败 - ' + str(result.error)}")

    print("\n快速测试完成！请检查企业微信中是否收到消息")

if __name__ == "__main__":
    main()
