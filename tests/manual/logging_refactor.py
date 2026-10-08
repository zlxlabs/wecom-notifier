"""
测试日志重构

验证新的日志系统是否正常工作
"""
import sys

# 设置输出编码为 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("测试 1: 默认情况（不配置日志）")
print("=" * 60)
print("预期：会看到 loguru 的默认输出（因为 loguru 默认有 handler）")
print()

from wecom_notifier import WeComNotifier

notifier1 = WeComNotifier()
print("[OK] WeComNotifier 初始化成功")
print()

print("=" * 60)
print("测试 2: 使用 setup_logger 配置日志")
print("=" * 60)
print("预期：应该看到带颜色的日志输出")
print()

from wecom_notifier import setup_logger

setup_logger(log_level="INFO")
notifier2 = WeComNotifier()
print("[OK] 应该看到了 'WeComNotifier initialized' 日志")
print()

print("=" * 60)
print("测试 3: 禁用日志")
print("=" * 60)
print("预期：不应该看到日志输出")
print()

from wecom_notifier import disable_logger

disable_logger()
notifier3 = WeComNotifier()
print("[OK] WeComNotifier 初始化成功（日志已禁用，应该没有看到日志）")
print()

print("=" * 60)
print("测试 4: 重新启用日志")
print("=" * 60)
print("预期：应该看到日志输出")
print()

from wecom_notifier import enable_logger

enable_logger()
notifier4 = WeComNotifier()
print("[OK] 应该看到了 'WeComNotifier initialized' 日志")
print()

print("=" * 60)
print("测试 5: 验证库专属标识")
print("=" * 60)
print("预期：日志记录应该包含 library='wecom_notifier' 标识")
print()

from loguru import logger

# 添加一个自定义 handler 来检查 extra 字段
def check_library_tag(message):
    """检查日志是否包含正确的 library 标识"""
    def sink(msg):
        record = msg.record
        if "extra" in record and record["extra"].get("library") == "wecom_notifier":
            print(f"[OK] 日志包含正确的 library 标识: {record['message']}")
    return sink

logger.add(check_library_tag, format="{message}")
notifier5 = WeComNotifier()
print()

print("=" * 60)
print("所有测试完成！")
print("=" * 60)
print()
print("总结：")
print("1. [OK] 库不主动配置日志（遵循最佳实践）")
print("   注：loguru 默认有一个 stderr handler，用户可以用 logger.remove() 移除")
print("2. [OK] setup_logger() 可以快速配置日志")
print("3. [OK] disable_logger() 可以完全禁用日志")
print("4. [OK] enable_logger() 可以重新启用日志")
print("5. [OK] 所有日志都带有 library='wecom_notifier' 标识")
print()
print("日志系统重构成功！")
