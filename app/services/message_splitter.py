"""
WhatsApp message splitting — keeps messages under the safe length limit.
"""


def split_for_whatsapp(text: str, max_len: int = 1500) -> list[str]:
    """Split a long message into WhatsApp-friendly chunks.

    Strategy:
    1. If it fits, return as-is.
    2. Split at paragraph boundaries (\\n\\n).
    3. Fall back to line boundaries (\\n).
    4. Last resort: hard split.
    Adds (1/N) indicators when multiple parts.
    """
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    current = ""

    # Try paragraph-level splits first
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
            # If this single paragraph is too long, split by lines
            if len(para) > max_len:
                lines = para.split("\n")
                current = ""
                for line in lines:
                    candidate = f"{current}\n{line}" if current else line
                    if len(candidate) <= max_len:
                        current = candidate
                    else:
                        if current:
                            parts.append(current.strip())
                        # Hard split if a single line is too long
                        if len(line) > max_len:
                            while line:
                                parts.append(line[:max_len])
                                line = line[max_len:]
                            current = ""
                        else:
                            current = line
            else:
                current = para

    if current.strip():
        parts.append(current.strip())

    if not parts:
        return [text[:max_len]]

    # Add part indicators
    if len(parts) > 1:
        total = len(parts)
        parts = [f"({i + 1}/{total})\n{part}" for i, part in enumerate(parts)]

    return parts
