import pytest

from relay.notify.html import (
    CONTENT_MAX_WIDTH,
    CONTENT_WIDTH,
    PAGE_BACKGROUND,
    markdown_to_html,
    render_email,
)


def test_layout_centers_a_white_content_area_on_grey():
    page = render_email("<p>hello</p>")
    assert page.startswith("<!DOCTYPE html>")
    assert (
        f'<body style="margin: 0; padding: 0; background: {PAGE_BACKGROUND}">' in page
    )
    assert (
        f"width: {CONTENT_WIDTH}; max-width: {CONTENT_MAX_WIDTH}; background: #ffffff"
        in page
    )
    assert "<p>hello</p>" in page


def test_title_and_footer_are_escaped():
    page = render_email("", title="A & B", footer="<sent by job>")
    assert "<title>A &amp; B</title>" in page
    assert "&lt;sent by job&gt;" in page


def test_no_footer_by_default():
    assert "font-size: 12px" not in render_email("")


def test_markdown_tables_are_styled_inline():
    page = markdown_to_html(
        "# Report\n\n| Name | Count |\n| --- | ---: |\n| `a\\|b` | 3 |\n"
    )
    assert '<h1 style="font-size: 20px' in page
    assert '<table width="100%" style="width: 100%; border-collapse' in page
    assert '<td style="border' in page
    assert 'background: #f6f8fa" align="right">Count' in page
    assert ">a|b</code>" in page  # GFM escape removed
    assert "\\|" not in page


# ── Untrusted Markdown ───────────────────────────────────────────────────────


def test_raw_html_is_escaped():
    page = markdown_to_html(
        "<script>alert(1)</script>\n\n"
        "| a |\n| --- |\n| <img src=x onerror=alert(1)> |\n"
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "<script" not in page
    assert "<img" not in page


@pytest.mark.parametrize(
    "source",
    [
        "[x](javascript:alert(1))",
        "[x](JaVa\tScript:alert(1))",
        "[x](&#106;avascript:alert(1))",
        "![i](data:text/html,<script>alert(1)</script>)",
    ],
)
def test_unsafe_urls_are_dropped(source):
    page = markdown_to_html(source)
    assert "href=" not in page
    assert "src=" not in page


@pytest.mark.parametrize(
    ("source", "url"),
    [
        ("[ok](https://apik.cloud)", 'href="https://apik.cloud"'),
        ("<https://auto.link>", 'href="https://auto.link"'),
        ("[m](mailto:a@b.c)", 'href="mailto:a@b.c"'),
        ("[r](/path)", 'href="/path"'),
    ],
)
def test_safe_urls_are_kept(source, url):
    assert url in markdown_to_html(source)


def test_html_in_code_span_is_shown_as_text():
    page = markdown_to_html("`<b>x</b>`")
    assert "&lt;b&gt;x&lt;/b&gt;</code>" in page
