
"""
Clean untrusted job-posting content before parsing.

Removes common webpage clutter and unsafe markup while
preserving job titles, descriptions, and requirements.

Cleaning is not a replacement for prompt-injection defenses.
"""

import html
import re
import unicodedata
from html.parser import HTMLParser


MAX_POSTING_CHARS = 30000

ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\u2060\ufeff"

UNWANTED_HEADINGS = {
    "navigation",
    "menu",
    "cookie policy",
    "cookie preferences",
    "advertisement",
    "advertisements",
    "sponsored content",
    "footer",
    "related jobs",
    "recommended jobs",
}

UNWANTED_HTML_TAGS = {
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "iframe",
    "svg",
}

BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "li",
    "h1",
    "h2",
    "h3",
    "br",
}


class _HTMLCleaner(HTMLParser):
    """Extract visible HTML text without executable markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        style = attributes.get("style") or ""
        classes = attributes.get("class") or ""

        hidden = (
            tag in UNWANTED_HTML_TAGS
            or "hidden" in attributes
            or attributes.get("aria-hidden", "").lower() == "true"
            or re.search(
                r"display\s*:\s*none|visibility\s*:\s*hidden",
                style,
                re.IGNORECASE,
            ) is not None
            or re.search(
                r"\b(?:cookie-banner|advertisement|site-footer)\b",
                classes,
                re.IGNORECASE,
            ) is not None
        )

        if self.skip_depth:
            self.skip_depth += 1
        elif hidden:
            self.skip_depth = 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

    def get_text(self):
        return "".join(self.parts)


def clean_posting(markdown: str) -> str:
    """
    Clean a scraped job posting.

    Supports plain Markdown and mixed HTML/Markdown.

    Returns an empty string for empty input and raises
    ValueError when the input exceeds the allowed size.
    """

    if not isinstance(markdown, str):
        raise TypeError("Posting content must be a string.")

    if not markdown.strip():
        return ""

    # Reject oversized pages instead of silently truncating
    # important requirements or descriptions.
    if len(markdown) > MAX_POSTING_CHARS:
        raise ValueError("Job posting exceeds maximum allowed length.")

    # Remove HTML comments, including multiline comments.
    text = re.sub(
        r"<!--[\s\S]*?-->",
        "",
        markdown,
    )

    # Remove common HTML sections containing hidden content.
    text = re.sub(
        r"<(script|style|noscript|nav|footer|iframe|svg)\b[^>]*>"
        r"[\s\S]*?</\1\s*>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove zero-width and control characters.
    text = "".join(
        char
        for char in text
        if char not in ZERO_WIDTH_CHARS
        and (
            char in "\n\r\t"
            or not unicodedata.category(char).startswith("C")
        )
    )

    # Convert HTML markup when a page contains actual HTML tags.
    # Preserve ordinary Markdown headings and bullet lists.
    if re.search(r"</?[a-zA-Z][^>]*>", text):
        parser = _HTMLCleaner()
        parser.feed(text)
        text = parser.get_text()

    text = html.unescape(text)

    # Remove obvious standalone website clutter.
    cleaned_lines = []
    skip_section = False

    for line in text.splitlines():
        stripped = line.strip()

        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)

        if heading:
            heading_text = heading.group(1).strip().lower()
            skip_section = heading_text in UNWANTED_HEADINGS

        if skip_section:
            continue

        if stripped.lower() in {
            "accept cookies",
            "reject cookies",
            "manage cookies",
            "back to top",
            "all rights reserved",
        }:
            continue

        cleaned_lines.append(line.rstrip())

    text = "\n".join(cleaned_lines)

    # Normalize excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
