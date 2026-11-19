"""Public HTML fetching and validated, atomic offline snapshots."""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCE = 'https://letterboxd.com/official/list/letterboxds-top-500-films/'
CACHE = Path.home() / 'Library/Application Support/Movie Roulette/top500.json'
BUNDLED = Path(__file__).with_name('snapshot.json')


def validate(films):
    if not isinstance(films, list) or len(films) != 500:
        raise ValueError('Expected exactly 500 films; keeping the previous snapshot.')
    if [f['rank'] for f in films] != list(range(1, 501)):
        raise ValueError('Missing or duplicate ranks.')
    if len({f['url'] for f in films}) != 500:
        raise ValueError('Duplicate film links.')
    for f in films:
        u = urlparse(f['url'])
        if not isinstance(f['title'], str) or not f['title'].strip() or u.scheme != 'https' or u.netloc != 'letterboxd.com' or not re.fullmatch(r'/film/[^/]+/', u.path):
            raise ValueError('Invalid film record.')
    return films


def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    films = []
    for item in soup.select('li.numbered-list-item'):
        poster = item.select_one('[data-item-link], [data-film-slug]')
        number = item.select_one('.list-number')
        if poster is None or number is None:
            continue
        image = poster.select_one('img[alt]')
        title = poster.get('data-item-name') or (image.get('alt') if image else None)
        link = poster.get('data-item-link') or '/film/' + poster['data-film-slug'].strip('/') + '/'
        if title:
            films.append({'rank': int(number.get_text(strip=True).replace(',', '')), 'title': title, 'url': urljoin(SOURCE, link)})
    return films


def fetch(progress=lambda message: None):
    films = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'MovieRoulette/1.0 (personal desktop movie picker)'
        for page in range(1, 6):
            progress(f'Fetching page {page} of 5…')
            url = SOURCE if page == 1 else urljoin(SOURCE, f'page/{page}/')
            for attempt in range(3):
                try:
                    response = session.get(url, timeout=(8, 20))
                    response.raise_for_status()
                    records = parse_page(response.text)
                    expected = list(range((page - 1) * 100 + 1, page * 100 + 1))
                    if [f['rank'] for f in records] != expected:
                        raise ValueError('Letterboxd returned an incomplete page or changed its layout.')
                    films.extend(records)
                    break
                except (requests.RequestException, ValueError) as error:
                    if attempt == 2:
                        raise RuntimeError(f'Page {page}: {error}') from error
                    time.sleep(2 ** attempt)
            if page < 5:
                time.sleep(0.4)
    validate(films)
    return {'source': SOURCE, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'films': films}


def load(path):
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if obj['source'] != SOURCE:
        raise ValueError('Snapshot source does not match.')
    datetime.fromisoformat(obj['fetched_at'])
    validate(obj['films'])
    return obj


def fallback():
    for path, label in [(CACHE, 'Saved cache'), (BUNDLED, 'Bundled snapshot')]:
        try:
            return load(path), label
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return None, 'No offline snapshot available'


def save(obj, path=CACHE):
    validate(obj['films'])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    snapshot = fetch(print)
    save(snapshot, BUNDLED)
    print('Saved 500 verified records to', BUNDLED)
