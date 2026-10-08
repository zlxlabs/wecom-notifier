"""
消息分段器。

不变式：最终每段(含页码和结构换行)按调用者计量方式不超预算，输入字符不丢、不拆 UTF-8 字符；
分页数字增长重新计费；可容纳表格页重复表头、普通链接整体保留，超大结构按纯文本降级；
长代码段补齐成对独立行围栏并保留原缩进/换行。MESSAGE_SEGMENT_OVERSIZE 明确失败，
由 tests/test_bounded_delivery.py 的极小预算、结构和实际请求边界测试锁定。
"""
import re
from typing import List
from .models import SegmentInfo
from .constants import (
    MSG_TYPE_TEXT,
    MSG_TYPE_MARKDOWN,
    MARKDOWN_TABLE_ROW_PATTERN,
    PAGE_INDICATOR_FORMAT,
    MAX_PAGE_INDICATOR_BYTES
)

# 默认最大字节数（可被平台覆盖）
DEFAULT_MAX_BYTES = 3800
_INLINE_LINK_PATTERN = re.compile(r"!?\[[^\]]+\]\([^)]+\)")


class MessageSegmentOversizeError(ValueError):
    """本地计划无法满足预算；调用方应将错误写入 SendResult。"""


class MessageSegmenter:
    """消息分段器"""

    def __init__(self, max_bytes: int = DEFAULT_MAX_BYTES):
        """
        初始化分段器

        Args:
            max_bytes: 每条消息的最大字节数
        """
        self.max_bytes = max_bytes

    def segment(self, content: str, msg_type: str) -> List[SegmentInfo]:
        """按实例预算分段，保持既有公开调用签名。"""
        return self._segment_bounded(content, msg_type, self.max_bytes)

    def _segment_bounded(self, content: str, msg_type: str, budget: int, measure=None) -> List[SegmentInfo]:
        """最终预算计量入口；页码、表头、围栏都在 budget 内。"""
        return self._segment_contents([content], msg_type, budget, measure)

    def _review_content(self, segment: SegmentInfo) -> str:
        """只剥除元数据确认且前缀逐字相符的本库分页标记。"""
        content = segment.content
        if segment.page_number is None or segment.total_pages is None:
            return content
        marker = PAGE_INDICATOR_FORMAT.format(
            current=segment.page_number,
            total=segment.total_pages,
        )
        return content[len(marker):] if content.startswith(marker) else content

    def _segment_reviewed(
        self, segments: List[SegmentInfo], msg_type: str, budget: int, measure=None
    ) -> List[SegmentInfo]:
        """去掉仅由页码元数据确认的本库前缀，再对审核结果统一分页。"""
        contents = [self._review_content(segment) for segment in segments]
        return self._segment_contents(["".join(contents)], msg_type, budget, measure)

    def _segment_contents(self, contents: List[str], msg_type: str, budget: int, measure=None) -> List[SegmentInfo]:
        """对多个已审核原分段共享一个最终页数；不改变审核边界或次数。"""
        measure = measure or (lambda value: len(value.encode("utf-8")))
        if budget <= 0:
            raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: budget must be positive")
        if not contents:
            return []

        page_guess = 1
        while True:
            prefix_budget = 0
            if page_guess > 1:
                prefix_budget = max(
                    measure(PAGE_INDICATOR_FORMAT.format(current=page, total=page_guess))
                    for page in (1, page_guess)
                )
            payload_budget = budget - prefix_budget
            if payload_budget <= 0:
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: page indicator exceeds budget")
            chunks = []
            for content in contents:
                if msg_type == MSG_TYPE_TEXT:
                    chunks.extend(self._bounded_text_chunks(content, payload_budget, measure))
                elif msg_type in (MSG_TYPE_MARKDOWN, "markdown_v2", "interactive"):
                    chunks.extend(self._bounded_markdown_chunks(content, payload_budget, measure))
                else:
                    if measure(content) > payload_budget:
                        raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: unsupported message type")
                    chunks.append(content)
            if len(chunks) == page_guess:
                return self._mark_segments(chunks, budget, measure)
            page_guess = len(chunks)

    def _size(self, value: str, measure) -> int:
        return measure(value)

    def _bounded_text_chunks(self, text: str, limit: int, measure) -> List[str]:
        """按原始换行边界优先切分；超长物理行再按 Unicode 字符拆。"""
        lines = text.splitlines(keepends=True)
        if not lines:
            return [text]
        chunks, current = [], ""
        for line in lines:
            if self._size(current + line, measure) <= limit:
                current += line
                continue
            if current:
                chunks.append(current)
                current = ""
            for part in self._split_unicode(line, limit, measure):
                if self._size(part, measure) > limit:
                    raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: one character exceeds budget")
                if self._size(current + part, measure) <= limit:
                    current += part
                else:
                    chunks.append(current)
                    current = part
        if current or not chunks:
            chunks.append(current)
        return chunks

    @staticmethod
    def _split_unicode(text: str, limit: int, measure=None) -> List[str]:
        """按完整 Unicode code point 切分，任何单字符不跨段、不丢失。"""
        size = measure or (lambda value: len(value.encode("utf-8")))
        parts, current, current_size = [], "", 0
        for char in text:
            char_size = size(char)
            if char_size > limit:
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: one character exceeds budget")
            if current and current_size + char_size > limit:
                parts.append(current)
                current = char
                current_size = char_size
            else:
                current += char
                current_size += char_size
        if current:
            parts.append(current)
        return parts or [""]

    def _append_markdown_text(self, text: str, current: str, limit: int, measure):
        """普通 Markdown 行优先保持可容纳的行内链接为一个不可拆单位。"""
        emitted = []

        def append_fragment(fragment):
            nonlocal current
            while fragment:
                capacity = limit - self._size(current, measure)
                if capacity <= 0:
                    emitted.append(current)
                    current = ""
                    continue
                if self._size(fragment[0], measure) > capacity:
                    if current:
                        emitted.append(current)
                        current = ""
                        continue
                part = self._split_unicode(fragment, capacity, measure)[0]
                current += part
                fragment = fragment[len(part):]
                if fragment:
                    emitted.append(current)
                    current = ""

        position = 0
        for match in _INLINE_LINK_PATTERN.finditer(text):
            append_fragment(text[position:match.start()])
            link = match.group(0)
            if self._size(link, measure) <= limit:
                if current and self._size(current + link, measure) > limit:
                    emitted.append(current)
                    current = ""
                current += link
            else:
                append_fragment(link)
            position = match.end()
        append_fragment(text[position:])
        return emitted, current

    def _bounded_markdown_chunks(self, text: str, limit: int, measure) -> List[str]:
        """保留普通行；表格超页重复表头；长代码块拆分后补齐代码围栏。"""
        lines = text.splitlines(keepends=True)
        if not lines:
            return [text]
        chunks, current = [], ""

        def flush():
            nonlocal current
            if current:
                chunks.append(current)
                current = ""

        def append_plain(value: str):
            nonlocal current
            emitted, current = self._append_markdown_text(value, current, limit, measure)
            chunks.extend(emitted)

        i = 0
        while i < len(lines):
            line = lines[i]
            fence = re.match(r"^\s*(`{3,}|~{3,})", line)
            if fence:
                marker = fence.group(1)
                close_index = next((j for j in range(i + 1, len(lines))
                                    if re.match(r"^\s*" + re.escape(marker[0]) +
                                                r"{" + str(len(marker)) + r",}\s*(?:\n)?$", lines[j])), None)
                if close_index is not None:
                    opening = line
                    closing = lines[close_index]
                    body = "".join(lines[i + 1:close_index])
                    whole = opening + body + closing
                    if self._size(whole, measure) <= limit:
                        if current and self._size(current + whole, measure) > limit:
                            flush()
                        current += whole
                    else:
                        boundary_newline = "\n"
                        overhead = self._size(opening + boundary_newline + closing, measure)
                        inner_limit = limit - overhead
                        if inner_limit <= 0:
                            raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: code fences exceed budget")
                        first_limit = inner_limit
                        if current:
                            first_limit = limit - self._size(
                                current + opening + boundary_newline + closing, measure
                            )
                            if first_limit <= 0 or (
                                body and self._size(body[0], measure) > first_limit
                            ):
                                flush()
                                first_limit = inner_limit
                        first_parts = self._split_unicode(body, first_limit, measure)
                        first = current + opening + first_parts[0] + boundary_newline + closing
                        if self._size(first, measure) > limit:
                            raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: code block cannot fit")
                        chunks.append(first)
                        current = ""
                        remaining = body[len(first_parts[0]):]
                        for part in self._split_unicode(remaining, inner_limit, measure):
                            code_part = opening + part + boundary_newline + closing
                            if self._size(code_part, measure) > limit:
                                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: code block cannot fit")
                            chunks.append(code_part)
                    i = close_index + 1
                    continue

            # 表格头 + 分隔线识别。不可容纳的行按文本拆分，正文保留。
            if (i + 1 < len(lines) and re.match(r"^\s*\|.*\|\s*(?:\n)?$", line)
                    and re.match(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*(?:\n)?$", lines[i + 1])):
                table_end = i + 2
                while table_end < len(lines) and re.match(r"^\s*\|.*\|\s*(?:\n)?$", lines[table_end]):
                    table_end += 1
                header = "".join(lines[i:i + 2])
                rows = lines[i + 2:table_end]
                if self._size(header, measure) > limit:
                    append_plain("".join(lines[i:table_end]))
                else:
                    if current and self._size(current + header, measure) > limit:
                        flush()
                    table_current = header
                    table_parts = []
                    for row_index, row in enumerate(rows):
                        if self._size(header + row, measure) > limit:
                            if table_current != header:
                                table_parts.append(table_current)
                            elif not table_parts:
                                table_parts.append(header)
                            row_chunks, row_tail = self._append_markdown_text(row, "", limit, measure)
                            table_parts.extend(row_chunks)
                            if row_tail:
                                table_parts.append(row_tail)
                            table_current = header if row_index < len(rows) - 1 else ""
                        elif self._size(table_current + row, measure) <= limit:
                            table_current += row
                        else:
                            table_parts.append(table_current)
                            table_current = header + row
                    if table_current:
                        table_parts.append(table_current)
                    elif not rows and not table_parts:
                        table_parts.append(header)
                    for part_index, part in enumerate(table_parts):
                        if part_index == 0 and current and self._size(current + part, measure) <= limit:
                            current += part
                        else:
                            if current:
                                flush()
                            if self._size(part, measure) <= limit:
                                current = part
                            else:
                                append_plain(part)
                i = table_end
                continue

            append_plain(line)
            i += 1
        flush()
        return chunks or [""]

    def _segment_text(self, content: str) -> List[str]:
        """
        文本类型的简单分段

        策略：按行分割，尽量填满每个分段
        """
        segments = []
        current = ""
        lines = content.split('\n')

        # 预留页码标记的空间
        reserved_bytes = MAX_PAGE_INDICATOR_BYTES
        available_bytes = self.max_bytes - reserved_bytes

        for line in lines:
            test_content = current + ('\n' if current else '') + line

            if len(test_content.encode('utf-8')) > available_bytes:
                # 当前行加入会超限
                if current:
                    segments.append(current)
                    current = line
                else:
                    # 单行就超过限制，强制截断
                    chunks = self._force_split(line, available_bytes)
                    segments.extend(chunks[:-1])
                    current = chunks[-1]
            else:
                current = test_content

        if current:
            segments.append(current)

        return segments

    def _segment_markdown(self, content: str) -> List[str]:
        """
        Markdown类型的智能分段

        策略：
        1. 按双换行符分段（段落）
        2. 识别特殊元素（表格、代码块）并保护
        3. 尽量填满每个分段，但不破坏语法
        """
        segments = []
        current = ""

        # 预留页码标记的空间
        reserved_bytes = MAX_PAGE_INDICATOR_BYTES
        available_bytes = self.max_bytes - reserved_bytes

        # 先处理代码块（暂时替换为占位符）
        code_blocks = []
        content = self._extract_code_blocks(content, code_blocks)

        # 按段落分割
        paragraphs = content.split('\n\n')

        i = 0
        while i < len(paragraphs):
            para = paragraphs[i]

            # 还原代码块
            para = self._restore_code_blocks(para, code_blocks)

            # 检查是否是表格（段落开头就是表格）
            if self._is_table_start(para):
                # 处理表格
                table_paras = [para]
                i += 1
                while i < len(paragraphs) and self._is_table_row(paragraphs[i]):
                    table_paras.append(paragraphs[i])
                    i += 1

                table_content = '\n\n'.join(table_paras)
                table_content = self._restore_code_blocks(table_content, code_blocks)

                # 处理表格分段
                table_segments = self._segment_table(table_content)
                for seg in table_segments:
                    if current and len((current + '\n\n' + seg).encode('utf-8')) > available_bytes:
                        segments.append(current)
                        current = seg
                    elif not current:
                        current = seg
                    else:
                        current += '\n\n' + seg
                continue

            # 检查段落中间是否包含表格（表格前有文字的情况）
            table_start_idx = self._find_table_in_paragraph(para)
            if table_start_idx > 0:
                # 分离表格前的文字和表格部分
                lines = para.split('\n')
                prefix_text = '\n'.join(lines[:table_start_idx])
                table_content = '\n'.join(lines[table_start_idx:])

                # 收集后续的表格行
                i += 1
                while i < len(paragraphs) and self._is_table_row(paragraphs[i]):
                    table_content += '\n\n' + paragraphs[i]
                    i += 1

                table_content = self._restore_code_blocks(table_content, code_blocks)

                # 先处理前缀文字
                test_content = current + ('\n\n' if current else '') + prefix_text
                if len(test_content.encode('utf-8')) > available_bytes:
                    if current:
                        segments.append(current)
                    current = prefix_text
                else:
                    current = test_content

                # 处理表格分段（保留表头）
                table_segments = self._segment_table(table_content)
                for seg in table_segments:
                    if current and len((current + '\n' + seg).encode('utf-8')) > available_bytes:
                        segments.append(current)
                        current = seg
                    elif not current:
                        current = seg
                    else:
                        current += '\n' + seg
                continue

            # 普通段落
            test_content = current + ('\n\n' if current else '') + para

            if len(test_content.encode('utf-8')) > available_bytes:
                if current:
                    # 检查 current 末尾是否有孤立标题，避免标题与正文分离
                    content_without_heading, trailing_heading = self._extract_trailing_heading(current)

                    if trailing_heading and content_without_heading:
                        # 有末尾标题且前面有其他内容
                        # 检查 content_without_heading 是否也只包含标题
                        # 如果是，不进行回溯，避免把标题单独分段
                        if not self._is_only_headings(content_without_heading):
                            # 前面有非标题内容，可以安全地回溯
                            segments.append(content_without_heading)
                            current = trailing_heading
                            # 不增加 i，重新处理当前 para（让标题和正文有机会合并）
                            continue
                        # 否则 content_without_heading 也是标题，走下面的 elif 逻辑

                    if trailing_heading:
                        # current 整体就是一个标题，尝试与 para 部分内容合并
                        # 避免标题单独成为一个分段
                        para_lines = para.split('\n')
                        merged_content = current  # 从标题开始
                        remaining_start = 0

                        for idx, line in enumerate(para_lines):
                            separator = '\n\n' if idx == 0 else '\n'
                            test_merge = merged_content + separator + line
                            if len(test_merge.encode('utf-8')) <= available_bytes:
                                merged_content = test_merge
                                remaining_start = idx + 1
                            else:
                                break

                        if remaining_start > 0:
                            # 成功合并了部分内容
                            segments.append(merged_content)
                            remaining_lines = para_lines[remaining_start:]
                            current = '\n'.join(remaining_lines) if remaining_lines else ""
                        else:
                            # para 的第一行都无法完整合并（可能是一个很长的单行）
                            # 尝试将第一行按字符拆分，让标题与部分内容合并
                            first_line = para_lines[0]
                            header_with_sep = current + '\n\n'
                            available_for_content = available_bytes - len(header_with_sep.encode('utf-8'))

                            if available_for_content > 0:
                                # 将 first_line 按字符截断
                                merged_chars = ""
                                for char in first_line:
                                    test = merged_chars + char
                                    if len(test.encode('utf-8')) <= available_for_content:
                                        merged_chars = test
                                    else:
                                        break

                                if merged_chars:
                                    # 成功合并了部分内容
                                    segments.append(header_with_sep + merged_chars)
                                    # 剩余内容
                                    remaining_first_line = first_line[len(merged_chars):]
                                    if remaining_first_line:
                                        remaining_lines = [remaining_first_line] + para_lines[1:]
                                    else:
                                        remaining_lines = para_lines[1:]
                                    current = '\n'.join(remaining_lines) if remaining_lines else ""
                                else:
                                    # 极端情况：标题本身接近限制，无法合并任何字符
                                    segments.append(current)
                                    current = para
                            else:
                                # 极端情况：标题本身超过限制
                                segments.append(current)
                                current = para

                        i += 1
                        continue

                    # 没有需要回溯的标题，正常分段
                    segments.append(current)
                    current = ""
                    # 重新检查para本身是否超限
                    if len(para.encode('utf-8')) > available_bytes:
                        # para本身超限，需要分段
                        if self._is_protected_element(para):
                            chunks = self._force_split(para, available_bytes)
                            segments.extend(chunks[:-1])
                            current = chunks[-1]
                        else:
                            line_segments = self._segment_text(para)
                            segments.extend(line_segments[:-1])
                            current = line_segments[-1]
                    else:
                        current = para
                else:
                    # 单个段落就超过限制
                    if self._is_protected_element(para):
                        # 保护元素，强制截断
                        chunks = self._force_split(para, available_bytes)
                        segments.extend(chunks[:-1])
                        current = chunks[-1]
                    else:
                        # 普通段落，按行分割
                        line_segments = self._segment_text(para)
                        segments.extend(line_segments[:-1])
                        current = line_segments[-1]
            else:
                current = test_content

            i += 1

        if current:
            segments.append(current)

        return segments

    def _segment_table(self, table_content: str) -> List[str]:
        """
        分段表格，保留表头

        Args:
            table_content: 表格内容

        Returns:
            List[str]: 表格分段列表
        """
        lines = table_content.split('\n')

        # 提取表头（前两行：标题行 + 分隔行）
        if len(lines) < 3:
            return [table_content]

        header = '\n'.join(lines[:2])
        data_rows = lines[2:]

        # 检查表头大小
        header_bytes = len(header.encode('utf-8'))
        if header_bytes > self.max_bytes:
            # 表头本身就超限，强制截断
            return self._force_split(table_content, self.max_bytes)

        segments = []
        current_rows = []

        # 预留页码标记的空间
        reserved_bytes = MAX_PAGE_INDICATOR_BYTES

        # 可用字节数 = 总限制 - 表头 - 换行符 - 页码标记
        available_bytes = self.max_bytes - header_bytes - len('\n'.encode('utf-8')) - reserved_bytes

        for row in data_rows:
            row_bytes = len(row.encode('utf-8')) + len('\n'.encode('utf-8'))

            if sum(len(r.encode('utf-8')) + len('\n'.encode('utf-8')) for r in current_rows) + row_bytes <= available_bytes:
                current_rows.append(row)
            else:
                if current_rows:
                    # 生成分段
                    seg = header + '\n' + '\n'.join(current_rows)
                    segments.append(seg)
                    current_rows = [row]
                else:
                    # 单行就超限，强制截断
                    segments.append(header + '\n' + row)

        if current_rows:
            seg = header + '\n' + '\n'.join(current_rows)
            segments.append(seg)

        return segments

    def _extract_code_blocks(self, content: str, code_blocks: List[str]) -> str:
        """提取代码块，替换为占位符"""

        def replacer(match):
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

        return re.sub(r'```[\s\S]*?```', replacer, content)

    def _restore_code_blocks(self, content: str, code_blocks: List[str]) -> str:
        """还原代码块"""
        for i, block in enumerate(code_blocks):
            content = content.replace(f"__CODE_BLOCK_{i}__", block)
        return content

    def _is_heading(self, text: str) -> bool:
        """判断文本是否是 Markdown 标题（# 到 ###### 开头）"""
        stripped = text.strip()
        return bool(re.match(r'^#{1,6}\s+', stripped))

    def _is_only_headings(self, content: str) -> bool:
        """
        判断内容是否只包含标题（没有其他正文内容）

        Args:
            content: 要检查的内容

        Returns:
            bool: 如果内容只包含标题行则返回 True
        """
        if not content or not content.strip():
            return False

        # 按段落分割
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 检查每个段落是否都是标题
            if not self._is_heading(para):
                return False
        return True

    def _extract_trailing_heading(self, content: str) -> tuple:
        """
        提取内容末尾的标题

        Args:
            content: 当前累积的内容

        Returns:
            tuple: (不含标题的内容, 标题) 或 (原内容, None) 如果没有末尾标题
        """
        if not content:
            return (content, None)

        # 按段落分割（双换行）
        parts = content.rsplit('\n\n', 1)

        if len(parts) == 2:
            before, last_para = parts
            # 检查最后一个段落是否是标题
            if self._is_heading(last_para):
                return (before, last_para)
        elif len(parts) == 1:
            # 只有一个段落，检查它是否是标题
            if self._is_heading(parts[0]):
                # 整个内容就是一个标题，返回空和标题
                return ('', parts[0])

        return (content, None)

    def _is_table_start(self, para: str) -> bool:
        """判断是否是表格开始"""
        lines = para.strip().split('\n')
        if len(lines) < 2:
            return False

        # 检查第一行和第二行是否都是表格行
        # 第二行应该是分隔行（如 |---|---|）
        return (re.match(MARKDOWN_TABLE_ROW_PATTERN, lines[0].strip()) and
                re.match(r'^\|[\s:-]+\|', lines[1].strip()))

    def _find_table_in_paragraph(self, para: str) -> int:
        """
        在段落中查找表格的起始行索引

        Args:
            para: 段落内容

        Returns:
            int: 表格起始行索引，如果没找到返回 -1
        """
        lines = para.split('\n')
        for i in range(len(lines) - 1):
            # 检查第 i 行是否是表格标题行，第 i+1 行是否是分隔行
            if (re.match(MARKDOWN_TABLE_ROW_PATTERN, lines[i].strip()) and
                re.match(r'^\|[\s:-]+\|', lines[i + 1].strip())):
                return i
        return -1

    def _is_table_row(self, para: str) -> bool:
        """判断是否是表格行"""
        return bool(re.match(MARKDOWN_TABLE_ROW_PATTERN, para.strip()))

    def _is_protected_element(self, para: str) -> bool:
        """判断是否是需要保护的元素（链接、图片、代码块）"""
        # 代码块
        if para.strip().startswith('```') and para.strip().endswith('```'):
            return True

        # 图片
        if re.match(r'^!\[.*?\]\(.*?\)$', para.strip()):
            return True

        return False

    def _force_split(self, text: str, max_bytes: int) -> List[str]:
        """
        强制按字节截断文本

        Args:
            text: 文本内容
            max_bytes: 最大字节数

        Returns:
            List[str]: 分段列表
        """
        segments = []
        current = ""

        for char in text:
            test = current + char
            if len(test.encode('utf-8')) > max_bytes:
                if current:
                    segments.append(current)
                    current = char
                else:
                    # 单个字符就超限（理论上不会发生）
                    segments.append(char)
            else:
                current = test

        if current:
            segments.append(current)

        return segments

    def _mark_segments(self, segments: List[str], budget: int = None, measure=None) -> List[SegmentInfo]:
        """
        标记分段的首尾，并添加页码标记

        Args:
            segments: 原始分段列表

        Returns:
            List[SegmentInfo]: 带标记的分段列表
        """
        if not segments:
            return []

        measure = measure or (lambda value: len(value.encode("utf-8")))
        total_pages = len(segments)
        result = []

        for i, seg in enumerate(segments):
            is_first = (i == 0)
            is_last = (i == len(segments) - 1)
            page_number = i + 1  # 页码从1开始

            # 仅当总页数 > 1 时添加页码标记
            content = seg
            if total_pages > 1:
                page_indicator = PAGE_INDICATOR_FORMAT.format(
                    current=page_number,
                    total=total_pages
                )
                content = page_indicator + content

            # 创建 SegmentInfo，包含页码信息（方便调试）
            segment_info = SegmentInfo(
                content=content,
                is_first=is_first,
                is_last=is_last,
                page_number=page_number if total_pages > 1 else None,
                total_pages=total_pages if total_pages > 1 else None
            )
            if budget is not None and measure(content) > budget:
                raise MessageSegmentOversizeError("MESSAGE_SEGMENT_OVERSIZE: final page marker exceeds budget")
            result.append(segment_info)

        return result
