"""Markdown 感知的文档分块器.

相比旧的字符滑窗分块（`embeddings.chunk_text`），本模块：
- 以 token（而非字符）度量块大小，适配嵌入模型的 token 预算。
- 按 Markdown 标题层级切分，各级标题下内容作为独立 chunk。
- 保护 fenced code block 与 Markdown 表格为原子单元，绝不从中切断。
- 每个 chunk 前置其所属标题路径，使向量携带结构上下文。

设计权衡：表格与代码块即使超过 token 上限也保持整块不切分
（切碎比 oversized chunk 更伤语义）；仅对散文段落按断句点续切并保留重叠。
"""

import re

# CJK 统一表意文字区间（用于逐字计数）
_CJK = re.compile(r"[一-鿿㐀-䶿豈-﫿]")

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
# 表格分隔行：| --- | --- | 或 --- | ---
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}(?:\s*\|\s*:?-{3,})*\s*\|?\s*$")
# 句子边界：中文句末标点 / 英文句点+空白+大写 / 换行
_SENT = re.compile(r"(?<=[。！？!?；;])|(?<=[.])\s+(?=[A-Z])|\n+")


def estimate_tokens(text: str) -> int:
    """粗略估计文本的 token 数（doubao 无离线 tokenizer，采用启发式）.

    CJK 字符逐个计 1 token，非 CJK 的字母/数字词按 1 token 计。
    估计值与真实 token 存在 ±20% 偏差，通过保守的 chunk_size 取值兜底。
    """
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    words = len(re.findall(r"[A-Za-z0-9]+", _CJK.sub(" ", text)))
    return cjk + words


def _format_path(path: list[tuple[int, str]]) -> str:
    """将标题栈格式化为前置路径，如 ``# A / ## B``."""
    return " / ".join("#" * level + " " + title for level, title in path)


def _fence_info(line: str) -> tuple[str, int, bool] | None:
    """识别代码围栏行，返回 ``(围栏字符, 长度, 是否闭合围栏)``，否则 None.

    开围栏可带信息串（如 ```python）；闭围栏只含围栏字符与空白。
    """
    s = line
    indent = len(s) - len(s.lstrip(" "))
    if indent > 3:
        return None
    s = s.lstrip(" ")
    if not s or s[0] not in "`~":
        return None
    ch = s[0]
    n = 0
    while n < len(s) and s[n] == ch:
        n += 1
    if n < 3:
        return None
    return ch, n, s[n:].strip() == ""


def _sentences(content: str) -> list[str]:
    """将散文拆成句子单元（保留句末标点，便于重叠）."""
    parts = _SENT.split(content)
    return [p for p in parts if p.strip()]


def _split_oversized(content: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """将超过 token 上限的散文段落按断句点续切，块间保留重叠."""
    sents = _sentences(content)
    if not sents:
        return [content] if content.strip() else []

    chunks: list[str] = []
    cur: list[str] = []
    cur_tokens = 0

    for s in sents:
        t = estimate_tokens(s)
        if cur and cur_tokens + t > chunk_size:
            chunks.append("".join(cur))
            # 重叠：保留末尾 chunk_overlap token 内的句子
            tail: list[str] = []
            tail_tokens = 0
            for prev in reversed(cur):
                pt = estimate_tokens(prev)
                if tail_tokens + pt > chunk_overlap:
                    break
                tail.insert(0, prev)
                tail_tokens += pt
            cur = tail
            cur_tokens = tail_tokens
        cur.append(s)
        cur_tokens += t

    if cur:
        chunks.append("".join(cur))
    return chunks


def _parse_blocks(text: str) -> list[tuple[str, str, list[tuple[int, str]]]]:
    """将 markdown 解析为块列表，返回 ``(kind, content, heading_path)``.

    kind 取值：``paragraph`` / ``code`` / ``table``。标题不单独成块，
    而是更新标题栈，作为后续内容块的路径前缀。
    """
    lines = text.split("\n")
    blocks: list[tuple[str, str, list[tuple[int, str]]]] = []
    stack: list[tuple[int, str]] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # fenced code block（``` 或 ~~~，开围栏可带语言信息串）
        fence = _fence_info(line)
        if fence:
            ch, flen, _ = fence
            buf = [line]
            i += 1
            while i < n:
                f2 = _fence_info(lines[i])
                if f2 and f2[0] == ch and f2[1] >= flen and f2[2]:
                    buf.append(lines[i])
                    i += 1
                    break
                buf.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(buf), list(stack)))
            continue

        # 标题
        m = _HEADING.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 表格（当前行含 | 且下一行是分隔行）
        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            buf = [line, lines[i + 1]]
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                buf.append(lines[i])
                i += 1
            blocks.append(("table", "\n".join(buf), list(stack)))
            continue

        # 段落 / 列表块：累积到空行、标题、代码块或表格起始
        buf = [line]
        i += 1
        while i < n and lines[i].strip() \
                and not _fence_info(lines[i]) \
                and not _HEADING.match(lines[i]) \
                and not ("|" in lines[i] and i + 1 < n and _TABLE_SEP.match(lines[i + 1])):
            buf.append(lines[i])
            i += 1
        blocks.append(("paragraph", "\n".join(buf), list(stack)))

    return blocks


def _join(path: list[tuple[int, str]], contents: list[str]) -> str:
    """组装 chunk：前置标题路径 + 正文."""
    prefix = _format_path(path)
    body = "\n".join(contents).strip()
    if prefix and body:
        return prefix + "\n" + body
    return prefix or body


def chunk_markdown(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[str]:
    """将 markdown 文档分块.

    Args:
        text: markdown 原文
        chunk_size: 每块目标 token 数
        chunk_overlap: 散文续切时块间重叠 token 数

    Returns:
        分块列表（每个 chunk 已前置标题路径）
    """
    blocks = _parse_blocks(text)
    chunks: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    buf_path: list[tuple[int, str]] | None = None

    def flush() -> None:
        nonlocal buf, buf_tokens, buf_path
        if buf:
            chunks.append(_join(buf_path or [], buf))
        buf = []
        buf_tokens = 0
        buf_path = None

    for kind, content, path in blocks:
        # 标题层级变化 → 换新 chunk（各级标题下内容独立成块）
        if buf and path != buf_path:
            flush()

        piece_tokens = estimate_tokens(content) + 1  # +1 换行

        # 超过预算 → flush 当前 chunk
        if buf and buf_tokens + piece_tokens > chunk_size:
            flush()

        if not buf:
            buf_path = path

        if kind in ("code", "table"):
            # 原子单元：整块保留，绝不从中切断
            buf.append(content)
            buf_tokens += piece_tokens
        elif piece_tokens > chunk_size:
            # 超大散文段落：按断句点续切（带重叠），直接产出
            for piece in _split_oversized(content, chunk_size, chunk_overlap):
                chunks.append(_join(path, [piece]))
        else:
            buf.append(content)
            buf_tokens += piece_tokens

    flush()
    return [c for c in chunks if c.strip()]
