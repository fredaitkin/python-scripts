#!/usr/bin/env python3
"""
Script to fetch and read website content.
"""

import argparse
import json
from html.parser import HTMLParser
from html import unescape
from urllib import request, error, parse


REDDIT_JSON_HEADERS = {
    "User-Agent": "python:read_website:1.0 (by /u/anonymous)",
    "Accept": "application/json",
}


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Read website content")
    parser.add_argument("url", help="Website URL (e.g., https://example.com)")
    parser.add_argument("--output", "-o", default=None, help="Optional output file path")
    parser.add_argument("--div", action="store_true",
                        help="Extract the first <div> with property=\"schema:articleBody\"")
    parser.add_argument("--debug-id", default=None,
                        help="Debug: extract and preview the first <div> with this exact id")
    parser.add_argument("--reddit-json", action="store_true",
                        help="Use Reddit JSON endpoint to get post content without HTML parsing")
    parser.add_argument("--playwright", action="store_true",
                        help="Fetch content with a real browser via Playwright")
    parser.add_argument("--wait-ms", type=int, default=3000,
                        help="Extra wait time in milliseconds for JS-rendered pages in --playwright mode")
    parser.add_argument("--headed", action="store_true",
                        help="Run Playwright browser in headed mode (visible window)")
    parser.add_argument("--scroll-to-bottom", action=argparse.BooleanOptionalAction, default=True,
                        help="In --playwright mode, auto-scroll to load more lazy comments. Default: enabled")
    parser.add_argument("--max-scroll-steps", type=int, default=30,
                        help="Maximum auto-scroll passes in --playwright mode")
    parser.add_argument("--scroll-pause-ms", type=int, default=1200,
                        help="Pause in milliseconds between auto-scroll passes")
    parser.add_argument("--expand-comments", action=argparse.BooleanOptionalAction, default=True,
                        help="In --playwright mode, click 'View more comments' where available. Default: enabled")
    parser.add_argument("--max-comment-clicks", type=int, default=120,
                        help="Maximum number of 'View more comments' button clicks in --playwright mode")
    parser.add_argument("--clean-text", action="store_true",
                        help="Convert extracted HTML content to readable plain text")
    parser.add_argument("--preview", "-p", type=int, default=1000,
                        help="Number of characters to print to console")
    args = parser.parse_args()

    parsed_url = parse.urlparse(args.url)
    is_reddit_url = "reddit.com" in parsed_url.netloc.lower()
    auto_playwright = is_reddit_url and not args.playwright and not args.reddit_json
    if auto_playwright:
        print("Auto-enabled Playwright for reddit.com URL.")

    if args.reddit_json:
        content = fetch_reddit_post_content(args.url)
        if content is None:
            return
        if args.div or args.debug_id:
            print("Note: --div and --debug-id are ignored when --reddit-json is used.")
    else:
        if args.playwright or auto_playwright:
            content = fetch_website_playwright(
                args.url,
                wait_ms=max(args.wait_ms, 0),
                headless=not args.headed,
                scroll_to_bottom=args.scroll_to_bottom,
                max_scroll_steps=max(args.max_scroll_steps, 0),
                scroll_pause_ms=max(args.scroll_pause_ms, 0),
                expand_comments=args.expand_comments,
                max_comment_clicks=max(args.max_comment_clicks, 0),
            )
        else:
            content = fetch_website(args.url)

        if content is None:
            return

        if args.div:
            div_content = extract_article_body_div(content)
            comment_divs = extract_comment_div(content)

            if not div_content and not comment_divs:
                print("No matching div found for schema:articleBody.")
                return

            combined_parts = []
            if div_content:
                combined_parts.append(div_content)

            for comment_div in comment_divs:
                if comment_div != div_content:
                    combined_parts.append(comment_div)

            content = "\n\n".join(combined_parts)

        if args.debug_id:
            debug_div = extract_div_by_id(content, args.debug_id)
            if not debug_div:
                marker_index = content.find(args.debug_id)
                if marker_index >= 0:
                    start = max(marker_index - 200, 0)
                    end = min(marker_index + len(args.debug_id) + 200, len(content))
                    print(f"Debug: no div found with id '{args.debug_id}', but the id text exists in raw HTML.")
                    print("Debug: raw snippet around id:\n")
                    print(content[start:end])
                else:
                    print(f"Debug: no div found with id '{args.debug_id}'.")
                return
            print(f"Debug: found div with id '{args.debug_id}'.")
            content = debug_div

    if args.clean_text:
        content = html_to_clean_text(content)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(content)
            print(f"Saved website content to {args.output}")
        except OSError as err:
            print(f"Failed to write output file: {err}")
            return

    preview = content[: max(args.preview, 0)]
    print("\nWebsite content preview:\n")
    print(preview)


def fetch_website(url, timeout=10):
    """Fetch website content and return it as text."""
    try:
        req = request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Python urllib)"}
        )
        with request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            content = response.read().decode(charset, errors="replace")
            return content
    except error.HTTPError as err:
        print(f"HTTP error: {err.code} {err.reason}")
    except error.URLError as err:
        print(f"URL error: {err.reason}")
    except TimeoutError:
        print("Request timed out.")
    return None


def fetch_website_playwright(
    url,
    wait_ms=3000,
    headless=True,
    scroll_to_bottom=True,
    max_scroll_steps=30,
    scroll_pause_ms=1200,
    expand_comments=True,
    max_comment_clicks=120,
):
    """Fetch website content in a browser context and return the rendered HTML."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install it with: pip install playwright")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(wait_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            if expand_comments and max_comment_clicks > 0:
                clicked = click_view_more_comments(
                    page,
                    max_clicks=max_comment_clicks,
                    pause_ms=max(scroll_pause_ms, 300),
                )
                if clicked > 0:
                    print(f"Clicked 'View more comments' {clicked} time(s).")

            if scroll_to_bottom and max_scroll_steps > 0:
                auto_scroll_page(page, max_scroll_steps=max_scroll_steps, pause_ms=scroll_pause_ms)
                if expand_comments and max_comment_clicks > 0:
                    clicked_after_scroll = click_view_more_comments(
                        page,
                        max_clicks=max_comment_clicks,
                        pause_ms=max(scroll_pause_ms, 300),
                    )
                    if clicked_after_scroll > 0:
                        print(f"Clicked 'View more comments' {clicked_after_scroll} additional time(s) after scrolling.")
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

            final_url = page.url
            if final_url != url:
                print(f"Playwright final URL: {final_url}")

            content = page.content()
            context.close()
            browser.close()
            return content
    except Exception as err:
        print(f"Playwright error: {err}")
        return None


def auto_scroll_page(page, max_scroll_steps=30, pause_ms=1200):
    """Scroll down repeatedly to trigger lazy-loading content."""
    last_height = 0
    stable_passes = 0

    for _ in range(max_scroll_steps):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        new_height = page.evaluate("document.body.scrollHeight")

        if new_height == last_height:
            stable_passes += 1
        else:
            stable_passes = 0
            last_height = new_height

        if stable_passes >= 2:
            break


def click_view_more_comments(page, max_clicks=120, pause_ms=1200):
    """Click visible 'View more comments' controls repeatedly to expand comment threads."""
    total_clicks = 0

    for _ in range(max_clicks):
        clicked_this_pass = False

        selectors = [
            "button:has-text('View more comments')",
            "a:has-text('View more comments')",
            "[role='button']:has-text('View more comments')",
        ]

        for selector in selectors:
            locator = page.locator(selector)
            count = locator.count()
            if count == 0:
                continue

            for index in range(count):
                try:
                    candidate = locator.nth(index)
                    if not candidate.is_visible():
                        continue
                    candidate.scroll_into_view_if_needed(timeout=2000)
                    candidate.click(timeout=3000)
                    total_clicks += 1
                    clicked_this_pass = True
                    page.wait_for_timeout(pause_ms)
                    break
                except Exception:
                    continue

            if clicked_this_pass:
                break

        if not clicked_this_pass:
            break

        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(300)

    return total_clicks


def build_reddit_json_urls(url):
    """Build Reddit JSON endpoint candidates for a post URL."""
    parsed_url = parse.urlparse(url)
    if "reddit.com" not in parsed_url.netloc.lower():
        print("Error: --reddit-json requires a reddit.com URL.")
        return []

    post_path = parsed_url.path.rstrip("/")
    if not post_path.endswith(".json"):
        post_path = f"{post_path}.json"

    query_items = parse.parse_qsl(parsed_url.query, keep_blank_values=True)
    query_dict = dict(query_items)
    query_dict["raw_json"] = "1"
    query_string = parse.urlencode(query_dict)

    scheme = parsed_url.scheme or "https"
    urls = [
        parse.urlunparse((scheme, parsed_url.netloc, post_path, "", query_string, ""))
    ]

    path_parts = [part for part in parsed_url.path.split("/") if part]
    if "comments" in path_parts:
        comments_index = path_parts.index("comments")
        if comments_index + 1 < len(path_parts):
            post_id = path_parts[comments_index + 1]
            old_reddit_path = f"/comments/{post_id}/.json"
            old_reddit_url = parse.urlunparse((scheme, "old.reddit.com", old_reddit_path, "", query_string, ""))
            urls.insert(0, old_reddit_url)

    return urls


def fetch_json(url, timeout=10):
    """Fetch JSON content and return it as a Python object."""
    try:
        # Detect login-gated Reddit responses before automatic redirect handling obscures the cause.
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        preflight_opener = request.build_opener(NoRedirect)
        req = request.Request(
            url,
            headers=REDDIT_JSON_HEADERS,
        )
        try:
            preflight_opener.open(req, timeout=timeout)
        except error.HTTPError as err:
            if err.code in (301, 302, 303, 307, 308):
                location = err.headers.get("Location", "")
                if "reddit.com/login/" in location and "reason=lor2" in location:
                    print("Reddit redirected this request to login (reason=lor2).")
                    print("This post requires a logged-in browser session, so unauthenticated JSON fetch is blocked.")
                    return None

        with request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
            return json.loads(payload)
    except error.HTTPError as err:
        print(f"HTTP error: {err.code} {err.reason}")
    except error.URLError as err:
        print(f"URL error: {err.reason}")
    except json.JSONDecodeError as err:
        print(f"JSON decode error: {err}")
    except TimeoutError:
        print("Request timed out.")
    return None


def extract_reddit_post_text(payload):
    """Extract title and selftext from Reddit post JSON payload."""
    if not isinstance(payload, list) or not payload:
        return None

    try:
        post_data = payload[0]["data"]["children"][0]["data"]
    except (KeyError, IndexError, TypeError):
        return None

    title = (post_data.get("title") or "").strip()
    selftext = (post_data.get("selftext") or "").strip()
    subreddit = (post_data.get("subreddit") or "").strip()
    author = (post_data.get("author") or "").strip()

    lines = []
    if title:
        lines.append(f"Title: {title}")
    if subreddit:
        lines.append(f"Subreddit: {subreddit}")
    if author:
        lines.append(f"Author: {author}")
    lines.append("")
    lines.append("Post body:")
    lines.append(selftext if selftext else "(No selftext body in this post)")

    return "\n".join(lines).strip()


def fetch_reddit_post_content(url):
    """Fetch and extract readable content from a Reddit post via JSON endpoint."""
    json_urls = build_reddit_json_urls(url)
    if not json_urls:
        return None

    payload = None
    for json_url in json_urls:
        payload = fetch_json(json_url)
        if payload is not None:
            break

    if payload is None:
        print("Could not fetch Reddit JSON from available endpoints.")
        return None

    content = extract_reddit_post_text(payload)
    if content is None:
        print("Could not extract Reddit post content from JSON response.")
        return None

    return content


class ArticleBodyDivParser(HTMLParser):
    """Parse HTML and extract the first div with property="schema:articleBody"."""

    def __init__(self):
        super().__init__()
        self.target_value = "schema:articleBody"
        self.in_target_div = False
        self.target_depth = 0
        self.found_html_parts = []
        self.result = None

    def handle_starttag(self, tag, attrs):
        if self.result is not None:
            return

        if not self.in_target_div and tag.lower() == "div":
            if any(
                attr_name == "property" and (value or "").strip() == self.target_value
                for attr_name, value in attrs
            ):
                self.in_target_div = True
                self.target_depth = 1
                self.found_html_parts.append(self.get_starttag_text())
                return

        if self.in_target_div:
            self.target_depth += 1
            self.found_html_parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.result is not None or not self.in_target_div:
            return

        self.found_html_parts.append(f"</{tag}>")
        self.target_depth -= 1
        if self.target_depth == 0:
            self.result = "".join(self.found_html_parts)
            self.in_target_div = False

    def handle_data(self, data):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(data)

    def handle_entityref(self, name):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(f"&#{name};")


class DivByIdParser(HTMLParser):
    """Parse HTML and extract the first div with a matching id attribute."""

    def __init__(self, target_id):
        super().__init__()
        self.target_id = target_id
        self.in_target_div = False
        self.target_depth = 0
        self.found_html_parts = []
        self.result = None

    def handle_starttag(self, tag, attrs):
        if self.result is not None:
            return

        if not self.in_target_div and tag.lower() == "div":
            if any(
                attr_name == "id" and (value or "").strip() == self.target_id
                for attr_name, value in attrs
            ):
                self.in_target_div = True
                self.target_depth = 1
                self.found_html_parts.append(self.get_starttag_text())
                return

        if self.in_target_div:
            self.target_depth += 1
            self.found_html_parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.result is not None or not self.in_target_div:
            return

        self.found_html_parts.append(f"</{tag}>")
        self.target_depth -= 1
        if self.target_depth == 0:
            self.result = "".join(self.found_html_parts)
            self.in_target_div = False

    def handle_data(self, data):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(data)

    def handle_entityref(self, name):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.result is None and self.in_target_div:
            self.found_html_parts.append(f"&#{name};")


class DivsByIdSubstringParser(HTMLParser):
    """Parse HTML and extract all divs whose id contains a target substring."""

    def __init__(self, target_substring):
        super().__init__()
        self.target_substring = target_substring
        self.results = []
        self.in_target_div = False
        self.target_depth = 0
        self.current_html_parts = []

    def handle_starttag(self, tag, attrs):
        if self.in_target_div:
            self.target_depth += 1
            self.current_html_parts.append(self.get_starttag_text())
            return

        if tag.lower() == "div":
            for attr_name, value in attrs:
                if attr_name == "id" and self.target_substring in (value or ""):
                    self.in_target_div = True
                    self.target_depth = 1
                    self.current_html_parts = [self.get_starttag_text()]
                    break

    def handle_endtag(self, tag):
        if not self.in_target_div:
            return

        self.current_html_parts.append(f"</{tag}>")
        self.target_depth -= 1
        if self.target_depth == 0:
            self.results.append("".join(self.current_html_parts))
            self.in_target_div = False
            self.current_html_parts = []

    def handle_data(self, data):
        if self.in_target_div:
            self.current_html_parts.append(data)

    def handle_entityref(self, name):
        if self.in_target_div:
            self.current_html_parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.in_target_div:
            self.current_html_parts.append(f"&#{name};")

    def handle_startendtag(self, tag, attrs):
        if self.in_target_div:
            self.current_html_parts.append(self.get_starttag_text())


def extract_article_body_div(content):
    """Return the first div with property="schema:articleBody"."""
    parser = ArticleBodyDivParser()
    parser.feed(content)
    parser.close()
    return parser.result


def extract_div_by_id(content, target_id):
    """Return the first div with id equal to target_id."""
    parser = DivByIdParser(target_id)
    parser.feed(content)
    parser.close()
    return parser.result


def extract_comment_div(content):
    """Return all div blocks whose id contains 'post-rtjson-content'."""
    parser = DivsByIdSubstringParser("post-rtjson-content")
    parser.feed(content)
    parser.close()
    return parser.results


class HtmlToTextParser(HTMLParser):
    """Convert HTML markup to readable plain text."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "hr"}:
            self.parts.append("\n")
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li", "section", "article", "ul", "ol"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if data:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(unescape(f"&{name};"))

    def handle_charref(self, name):
        self.parts.append(unescape(f"&#{name};"))

    def get_text(self):
        return "".join(self.parts)


def html_to_clean_text(content):
    """Strip HTML tags and normalize spacing for readability."""
    parser = HtmlToTextParser()
    parser.feed(content)
    parser.close()

    text = parser.get_text().replace("\r", "")
    lines = [line.strip() for line in text.split("\n")]

    cleaned_lines = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(line)
            previous_blank = False

    return "\n".join(cleaned_lines).strip()


if __name__ == "__main__":
    main()
