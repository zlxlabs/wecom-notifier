#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试脚本：查看分段详情
"""
import os
from wecom_notifier.segmenter import MessageSegmenter
from wecom_notifier.constants import MSG_TYPE_MARKDOWN_V2

# 文件路径
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "llm_summary.txt")


def main():
    """主函数"""
    # 读取文件内容
    print(f"Reading file: {LOG_FILE}")
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"File size: {len(content)} chars, {len(content.encode('utf-8'))} bytes")
    print()

    # 创建分段器
    segmenter = MessageSegmenter()

    # 进行分段
    segments = segmenter.segment(content, MSG_TYPE_MARKDOWN_V2)

    print(f"Total segments: {len(segments)}")
    print("="*80)

    # 打印每个分段的信息
    for i, seg_info in enumerate(segments, 1):
        content_bytes = len(seg_info.content.encode('utf-8'))
        print(f"\nSegment {i}/{len(segments)}:")
        print(f"  - is_first: {seg_info.is_first}")
        print(f"  - is_last: {seg_info.is_last}")
        print(f"  - Size: {len(seg_info.content)} chars, {content_bytes} bytes")
        print(f"  - Within limit (4096): {'YES' if content_bytes <= 4096 else 'NO - EXCEEDS!'}")

        if content_bytes > 4096:
            print(f"  - **ERROR**: Exceeds limit by {content_bytes - 4096} bytes")
            # 打印前100和后100字符
            print(f"  - First 100 chars: {seg_info.content[:100]}")
            print(f"  - Last 100 chars: {seg_info.content[-100:]}")

    print("\n" + "="*80)
    print("Summary:")
    print(f"  - Total segments: {len(segments)}")
    print(f"  - Max segment size: {max(len(s.content.encode('utf-8')) for s in segments)} bytes")
    print(f"  - Min segment size: {min(len(s.content.encode('utf-8')) for s in segments)} bytes")

    # 检查是否有超限的
    over_limit = [i for i, s in enumerate(segments, 1) if len(s.content.encode('utf-8')) > 4096]
    if over_limit:
        print(f"  - **FAILED**: Segments exceeding 4096 bytes: {over_limit}")
    else:
        print(f"  - **PASSED**: All segments within limit")


if __name__ == "__main__":
    main()
