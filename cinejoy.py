"""Resolve a film using rendered public search results, without guessing IDs."""
import re
import unicodedata
from urllib.parse import urlparse, urljoin, urlencode

BASE = 'https://cinejoy.pk'


def split_title(display):
    match = re.fullmatch(r'(.*?)\s+\((\d{4})\)', display.strip())
    return (match[1], match[2]) if match else (display.strip(), None)


def normalized(title):
    value = unicodedata.normalize('NFKD', title).casefold()
    return ''.join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def search_url(display):
    return BASE + '/search?' + urlencode({'q': split_title(display)[0]})


def exact_matches(display, links):
    title, year = split_title(display)
    if year is None:
        return []
    matches = set()
    for link in links:
        url = urljoin(BASE, link)
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'cinejoy.pk':
            continue
        match = re.fullmatch(r'/movie/(\d+)-(.+)-(\d{4})/?', parsed.path)
        if match and match[3] == year and normalized(match[2]) == normalized(title):
            # Remove query strings/fragments from the result we open.
            matches.add(BASE + parsed.path.rstrip('/'))
    return sorted(matches)


def resolve(display):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            # Only search metadata is needed; avoid media and large assets.
            page.route('**/*', lambda route: route.abort() if route.request.resource_type in ('image', 'media', 'font') else route.continue_())
            response = page.goto(search_url(display), wait_until='domcontentloaded', timeout=20000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f'Cinejoy returned HTTP {response.status}.')
            page.locator('a[href^="/movie/"], a[href^="https://cinejoy.pk/movie/"]').first.wait_for(timeout=15000)
            # Give a reactive result list a moment to settle after its first card.
            page.wait_for_timeout(800)
            links = page.locator('a[href]').evaluate_all('(elements) => elements.map(a => a.href)')
            matches = exact_matches(display, links)
            if len(matches) == 1:
                return matches[0], 'Matched title and year on Cinejoy.'
            if len(matches) > 1:
                return search_url(display), 'Multiple matching films; please choose a result.'
            return search_url(display), 'No exact title/year match; please choose a result.'
        finally:
            browser.close()
