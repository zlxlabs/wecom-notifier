"""
企业微信通知器完整功能测试

测试所有核心功能，确保符合预期
"""
import time
from wecom_notifier import WeComNotifier

# 测试用的两个Webhook地址
WEBHOOK_1 = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c"
WEBHOOK_2 = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=f1fa66dd-a1b0-4893-af75-5dab9d993182"


def print_test_header(test_name):
    """打印测试标题"""
    print("\n" + "=" * 80)
    print(f"  测试: {test_name}")
    print("=" * 80)


def print_result(result, test_desc=""):
    """打印测试结果"""
    if result.is_success():
        print(f"✅ {test_desc} - 发送成功 (消息ID: {result.message_id})")
    else:
        print(f"❌ {test_desc} - 发送失败: {result.error}")
    return result.is_success()


def test_1_basic_text():
    """测试1：基础文本消息"""
    print_test_header("测试1：基础文本消息")

    notifier = WeComNotifier()

    # 测试1.1：简单文本
    print("\n[1.1] 发送简单文本消息")
    result = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【测试1.1】这是一条简单的文本消息",
        async_send=False
    )
    print_result(result, "简单文本")

    time.sleep(2)

    # 测试1.2：带@all的文本
    print("\n[1.2] 发送带@all的文本消息")
    result = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【测试1.2】这是一条@所有人的消息",
        mentioned_list=["@all"],
        async_send=False
    )
    print_result(result, "带@all的文本")

    print("\n测试1完成！请在企业微信中查看是否收到两条消息。")
    input("按回车继续下一个测试...")


def test_2_markdown():
    """测试2：Markdown消息"""
    print_test_header("测试2：Markdown消息")

    notifier = WeComNotifier()

    # 测试2.1：普通Markdown
    print("\n[2.1] 发送普通Markdown消息")
    markdown_content = """# 【测试2.1】Markdown测试

## 基本格式测试
- **加粗文本**
- *斜体文本*

## 列表测试
1. 第一项
2. 第二项
3. 第三项

## 链接测试
[点击访问百度](https://www.baidu.com)

## 代码测试
`print("Hello World")`
"""

    result = notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content=markdown_content,
        async_send=False
    )
    print_result(result, "普通Markdown")

    time.sleep(3)

    # 测试2.2：带@all的Markdown（会额外发送一条text消息）
    print("\n[2.2] 发送带@all的Markdown消息（会额外发送@all消息）")
    result = notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content="# 【测试2.2】带@all的Markdown\n\n这条消息后面会跟一条@all的text消息",
        mention_all=True,
        async_send=False
    )
    print_result(result, "带@all的Markdown")

    print("\n测试2完成！")
    print("应该收到3条消息：")
    print("  1. 普通Markdown消息")
    print("  2. 带@all的Markdown消息")
    print("  3. 空内容的@all text消息")
    input("按回车继续下一个测试...")


def test_3_long_text_segmentation():
    """测试3：长文本自动分段"""
    print_test_header("测试3：长文本自动分段")

    notifier = WeComNotifier()

    # 生成一个超长文本（超过4096字节）
    print("\n[3.1] 发送超长文本（会自动分段）")
    long_text = "【测试3.1】长文本自动分段测试\n\n"
    long_text += "\n".join([f"第 {i:04d} 行：这是一行测试内容，用于验证长文本分段功能是否正常工作。" * 3 for i in range(1, 101)])

    print(f"文本长度: {len(long_text.encode('utf-8'))} 字节")
    print("预计会分成多段发送...")

    result = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=long_text,
        async_send=False
    )
    print_result(result, "超长文本")

    print("\n测试3完成！")
    print("应该收到多条消息，每条带有'（续上页）'或'（未完待续）'标记")
    input("按回车继续下一个测试...")


def test_4_table_segmentation():
    """测试4：Markdown表格分段"""
    print_test_header("测试4：Markdown表格分段")

    notifier = WeComNotifier()

    print("\n[4.1] 发送超长表格（会保留表头分段）")

    # 生成超长表格
    table_markdown = """# 【测试4.1】表格分段测试

## 用户数据表

| 序号 | 姓名 | 年龄 | 城市 | 部门 | 职位 |
|------|------|------|------|------|------|
"""

    # 添加大量数据行
    for i in range(1, 151):
        table_markdown += f"| {i:04d} | 用户{i} | {20 + i % 50} | 城市{i % 30} | 部门{i % 10} | 职位{i % 5} |\n"

    print(f"表格长度: {len(table_markdown.encode('utf-8'))} 字节")
    print("预计会分成多段，每段都保留表头...")

    result = notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content=table_markdown,
        async_send=False
    )
    print_result(result, "超长表格")

    print("\n测试4完成！")
    print("应该收到多条消息，每条都有表头，且带有续页标记")
    input("按回车继续下一个测试...")


def test_5_concurrent_sending():
    """测试5：并发发送"""
    print_test_header("测试5：并发发送")

    notifier = WeComNotifier()

    print("\n[5.1] 异步并发发送10条消息")
    print("这些消息会排队发送，观察它们的顺序...")

    results = []
    for i in range(1, 11):
        result = notifier.send_text(
            webhook_url=WEBHOOK_1,
            content=f"【测试5.1】并发消息 {i:02d}/10",
            async_send=True  # 异步发送
        )
        results.append((i, result))
        print(f"  消息 {i} 已提交到队列")

    # 等待所有消息发送完成
    print("\n等待所有消息发送完成...")
    success_count = 0
    for i, result in results:
        result.wait(timeout=60)
        if result.is_success():
            success_count += 1
            print(f"  ✅ 消息 {i} 发送成功")
        else:
            print(f"  ❌ 消息 {i} 发送失败: {result.error}")

    print(f"\n成功发送: {success_count}/10")

    print("\n测试5完成！")
    print("应该收到10条消息，顺序应该是1-10")
    input("按回车继续下一个测试...")


def test_6_multiple_webhooks():
    """测试6：多Webhook管理"""
    print_test_header("测试6：多Webhook管理")

    notifier = WeComNotifier()

    print("\n[6.1] 同时向两个webhook发送消息")
    print("观察两个群组是否都收到消息...")

    # 向webhook 1发送
    result1 = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content="【测试6.1】发送到Webhook 1",
        async_send=False
    )
    print_result(result1, "Webhook 1")

    time.sleep(1)

    # 向webhook 2发送
    result2 = notifier.send_text(
        webhook_url=WEBHOOK_2,
        content="【测试6.1】发送到Webhook 2",
        async_send=False
    )
    print_result(result2, "Webhook 2")

    print("\n测试6完成！")
    print("两个webhook应该各收到一条消息")
    input("按回车继续下一个测试...")


def test_7_rate_limiting():
    """测试7：频率控制"""
    print_test_header("测试7：频率控制")

    notifier = WeComNotifier()

    print("\n[7.1] 快速发送25条消息（超过20条/分钟限制）")
    print("观察系统是否会自动限速，避免超过频率限制...")

    start_time = time.time()

    results = []
    for i in range(1, 26):
        result = notifier.send_text(
            webhook_url=WEBHOOK_1,
            content=f"【测试7.1】频率测试 {i:02d}/25",
            async_send=True
        )
        results.append((i, result))
        print(f"  提交消息 {i}")

    print("\n等待所有消息发送完成（这将需要一些时间）...")

    success_count = 0
    for i, result in results:
        result.wait(timeout=120)
        if result.is_success():
            success_count += 1

    elapsed = time.time() - start_time

    print(f"\n✅ 成功发送: {success_count}/25")
    print(f"⏱️  总耗时: {elapsed:.2f} 秒")
    print(f"📊 平均速率: {success_count / (elapsed / 60):.2f} 条/分钟")

    if elapsed >= 60:
        print("✅ 频率控制正常工作（超过60秒，说明有限速）")
    else:
        print("⚠️  注意：如果时间小于60秒，可能频率控制有问题")

    print("\n测试7完成！")
    input("按回车继续下一个测试...")


def test_8_message_order():
    """测试8：消息分段顺序"""
    print_test_header("测试8：消息分段顺序")

    notifier = WeComNotifier()

    print("\n[8.1] 发送两条长消息，验证分段顺序")
    print("消息A和消息B各自的分段应该是连续的...")

    # 生成两条长消息
    message_a = "【消息A】\n" + "\n".join([f"A行{i}" * 50 for i in range(60)])
    message_b = "【消息B】\n" + "\n".join([f"B行{i}" * 50 for i in range(60)])

    # 异步发送
    result_a = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=message_a,
        async_send=True
    )

    result_b = notifier.send_text(
        webhook_url=WEBHOOK_1,
        content=message_b,
        async_send=True
    )

    print("等待发送完成...")
    result_a.wait()
    result_b.wait()

    print_result(result_a, "消息A")
    print_result(result_b, "消息B")

    print("\n测试8完成！")
    print("应该收到的顺序：A1, A2, ..., B1, B2, ...")
    print("不应该出现：A1, B1, A2, B2这种交错")
    input("按回车继续下一个测试...")


def test_9_error_handling():
    """测试9：错误处理"""
    print_test_header("测试9：错误处理")

    notifier = WeComNotifier()

    print("\n[9.1] 测试无效webhook（应该失败）")
    result = notifier.send_text(
        webhook_url="https://invalid-webhook-url.com/test",
        content="测试消息",
        async_send=False
    )

    if not result.is_success():
        print(f"✅ 正确处理了无效webhook错误: {result.error}")
    else:
        print("❌ 错误：无效webhook不应该发送成功")

    print("\n测试9完成！")
    input("按回车继续下一个测试...")


def test_10_complex_markdown():
    """测试10：复杂Markdown"""
    print_test_header("测试10：复杂Markdown格式")

    notifier = WeComNotifier()

    complex_markdown = """# 【测试10】完整Markdown功能测试

## 1. 标题层级
### 三级标题
#### 四级标题
##### 五级标题

## 2. 文本格式
这是**加粗文本**
这是*斜体文本*

## 3. 列表功能
### 无序列表
- 列表项1
- 列表项2
  - 子列表项2.1
  - 子列表项2.2

### 有序列表
1. 第一项
2. 第二项
3. 第三项

## 4. 链接和图片
[点击访问GitHub](https://github.com)

## 5. 引用
> 一级引用
>> 二级引用
>>> 三级引用

## 6. 代码
行内代码: `print("hello")`

代码块:
```
def hello():
    print("Hello World")
```

## 7. 分割线

---

## 8. 表格
| 功能 | 状态 | 说明 |
|------|:----:|-----:|
| 文本 | ✅ | 支持 |
| Markdown | ✅ | 支持 |
| 图片 | ✅ | 支持 |
"""

    result = notifier.send_markdown(
        webhook_url=WEBHOOK_1,
        content=complex_markdown,
        async_send=False
    )

    print_result(result, "复杂Markdown")

    print("\n测试10完成！")
    print("应该看到一条格式丰富的Markdown消息")
    input("按回车继续...")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("  企业微信通知器 - 完整功能测试")
    print("=" * 80)
    print("\n测试Webhook地址:")
    print(f"  Webhook 1: {WEBHOOK_1}")
    print(f"  Webhook 2: {WEBHOOK_2}")
    print("\n提示：")
    print("  - 请确保这两个webhook是有效的")
    print("  - 测试过程中会发送多条消息，请注意查看企业微信")
    print("  - 某些测试会有延迟，请耐心等待")
    print("\n" + "=" * 80)

    input("\n按回车开始测试...")

    tests = [
        ("基础文本消息", test_1_basic_text),
        ("Markdown消息", test_2_markdown),
        ("长文本自动分段", test_3_long_text_segmentation),
        ("表格分段", test_4_table_segmentation),
        ("并发发送", test_5_concurrent_sending),
        ("多Webhook管理", test_6_multiple_webhooks),
        ("频率控制", test_7_rate_limiting),
        ("消息分段顺序", test_8_message_order),
        ("错误处理", test_9_error_handling),
        ("复杂Markdown", test_10_complex_markdown),
    ]

    for i, (name, test_func) in enumerate(tests, 1):
        try:
            test_func()
        except KeyboardInterrupt:
            print("\n\n用户中断测试")
            break
        except Exception as e:
            print(f"\n❌ 测试出错: {e}")
            import traceback
            traceback.print_exc()
            input("按回车继续...")

    print("\n" + "=" * 80)
    print("  所有测试完成！")
    print("=" * 80)
    print("\n测试总结:")
    print("  ✅ 如果所有功能都正常工作，恭喜！")
    print("  ❌ 如果有失败，请检查错误信息并修复")
    print("\n建议:")
    print("  - 检查企业微信中收到的所有消息")
    print("  - 验证消息顺序、格式、@all功能等")
    print("  - 确认频率控制是否生效")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
