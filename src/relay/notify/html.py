"""HTML email layout shared by every mailing sent through the notify gateway.

`render_email()` wraps ready-made HTML in the layout: a pale grey page with a
white, centered content area. `markdown_to_html()` converts Markdown (tables
included) and wraps it. Email clients drop or ignore most CSS, so the layout
is built from nested tables and every tag is styled inline.
"""

import html
import re
from urllib.parse import urlsplit

import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

PAGE_BACKGROUND = "#f2f3f5"
CONTENT_BACKGROUND = "#ffffff"
CONTENT_WIDTH = "90%"
CONTENT_MAX_WIDTH = "1000px"
FONT = "Arial, Helvetica, sans-serif"
TEXT_COLOR = "#24292f"
MUTED_COLOR = "#6a737d"
BORDER_COLOR = "#d0d7de"

_CONTENT_STYLES = {
    "table": "width: 100%; border-collapse: collapse; margin: 8px 0 16px",
    "th": f"border: 1px solid {BORDER_COLOR}; padding: 4px 8px; background: #f6f8fa",
    "td": f"border: 1px solid {BORDER_COLOR}; padding: 4px 8px; vertical-align: top",
    "code": "font-family: monospace; background: #f6f8fa; padding: 0 3px",
    "h1": "font-size: 20px; margin: 0 0 16px",
    "h2": "font-size: 17px; margin: 24px 0 8px",
    "h3": "font-size: 15px; margin: 16px 0 8px",
}

#: Link and image URL schemes kept by `markdown_to_html()`. Any other scheme
#: (javascript:, data:, vbscript:…) loses its href/src; scheme-less URLs stay.
SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})

# Browsers decode character references in an attribute ("&#106;avascript:")
# and ignore control characters and spaces in a URL scheme ("java\tscript:").
_URL_IGNORED_RE = re.compile(r"[\x00-\x20]")

# Only clients that keep <style> apply it: a phone gets the full width.
_HEAD_STYLE = "@media (max-width: 600px) { .content { width: 100% !important; } }"

_LAYOUT = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{head_style}</style>
</head>
<body style="margin: 0; padding: 0; background: {page_bg}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background: {page_bg}">
<tr><td align="center" style="padding: 24px 8px">
<table role="presentation" class="content" width="{width}" cellpadding="0" cellspacing="0" border="0" style="width: {width}; max-width: {max_width}; background: {content_bg}; border: 1px solid #e1e4e8; border-radius: 6px">
<tr><td style="padding: 24px 32px; font-family: {font}; font-size: 14px; line-height: 1.5; color: {text}">
{content}
</td></tr>
</table>
{footer}</td></tr>
</table>
</body></html>
"""

_FOOTER = """\
<table role="presentation" class="content" width="{width}" cellpadding="0" cellspacing="0" border="0" style="width: {width}; max-width: {max_width}">
<tr><td style="padding: 12px 32px; font-family: {font}; font-size: 12px; color: {muted}">{text}</td></tr>
</table>
"""


def render_email(content: str, title: str = "", footer: str = "") -> str:
    """Wrap an HTML fragment in the email layout. ``title`` (the page title,
    not shown by most clients) and ``footer`` (shown under the content area)
    are plain text and get escaped."""
    common = {"width": CONTENT_WIDTH, "max_width": CONTENT_MAX_WIDTH, "font": FONT}
    footer_html = (
        _FOOTER.format(**common, muted=MUTED_COLOR, text=html.escape(footer))
        if footer
        else ""
    )
    return _LAYOUT.format(
        **common,
        title=html.escape(title),
        head_style=_HEAD_STYLE,
        page_bg=PAGE_BACKGROUND,
        content_bg=CONTENT_BACKGROUND,
        text=TEXT_COLOR,
        content=content,
        footer=footer_html,
    )


class _SafeUrls(Treeprocessor):
    """Remove an `<a href>` or `<img src>` whose scheme is not safe."""

    def run(self, root):
        for el in root.iter():
            attr = {"a": "href", "img": "src"}.get(el.tag)
            if attr is None or attr not in el.attrib:
                continue
            url = _URL_IGNORED_RE.sub("", html.unescape(el.get(attr)))
            scheme = urlsplit(url).scheme.lower()
            if scheme and scheme not in SAFE_URL_SCHEMES:
                del el.attrib[attr]


class _EscapeHtml(Extension):
    """Treat raw HTML in the Markdown source as text, and drop unsafe URLs:
    the Markdown carries data (names, details) from outside."""

    def extendMarkdown(self, md):
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        # After "unescape" (priority 0): URLs are final there.
        md.treeprocessors.register(_SafeUrls(md), "safe_urls", -1)


def markdown_to_html(content: str, title: str = "", footer: str = "") -> str:
    """Convert Markdown (with tables) to a complete HTML email, see
    `render_email()`.

    Raw HTML in ``content`` is escaped and shown as text, and only http,
    https, mailto and scheme-less link and image URLs are kept: any other
    scheme (javascript:, data:…) loses its href/src."""
    body = markdown.markdown(
        content,
        extensions=["tables", _EscapeHtml()],
        # Alignment as an attribute leaves the style attribute free below.
        extension_configs={"tables": {"use_align_attribute": True}},
    )
    # GFM escapes `|` in table cells; Python-Markdown keeps the backslash
    # inside code spans.
    body = body.replace("\\|", "|")
    for tag, style in _CONTENT_STYLES.items():
        body = re.sub(rf"<{tag}(?=[ >])", f'<{tag} style="{style}"', body)
    # Outlook ignores a CSS width on tables, not the attribute.
    body = body.replace("<table ", '<table width="100%" ')
    return render_email(body, title=title, footer=footer)
