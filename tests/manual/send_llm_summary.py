#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：发送 llm_summary.txt 到企业微信
"""
import os
import sys
from wecom_notifier import WeComNotifier

# Webhook URL
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dd2cc41e-0388-4b04-9385-71efed5ea76c"

# 文件路径
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "llm_summary.txt")


def main():
    """主函数"""
    # 检查文件是否存在
    if not os.path.exists(LOG_FILE):
        print(f"[ERROR] File not found: {LOG_FILE}")
        return 1

    # 读取文件内容
    print(f"[INFO] Reading file: {LOG_FILE}")
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"[INFO] File size: {len(content)} chars, {len(content.encode('utf-8'))} bytes")

    # 创建通知器
    print("[INFO] Initializing WeComNotifier...")
    notifier = WeComNotifier(log_level="DEBUG")

    # 发送 Markdown 消息
    print("[INFO] Sending to WeCom...")
    result = notifier.send_markdown(
        webhook_url=WEBHOOK_URL,
        content=content,
        mention_all=False,
        async_send=False  # 同步发送，等待完成
    )

    # 等待完成
    print("[INFO] Waiting for completion...")
    result.wait(timeout=300)  # 最多等待5分钟

    # 检查结果
    print("\n" + "="*60)
    if result.is_success():
        print("[SUCCESS] Message sent successfully!")
        print(f"Message ID: {result.message_id}")
        if hasattr(result, 'segment_count'):
            print(f"Segment count: {result.segment_count}")
        if hasattr(result, 'used_webhooks'):
            print(f"Used webhooks: {len(result.used_webhooks)}")
    else:
        print("[FAILED] Message send failed!")
        print(f"Error: {result.error}")
        return 1

    print("="*60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
