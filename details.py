"""Movie metadata from Letterboxd's public JSON-LD, with bounded requests."""
import json
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def parse_details(html):
    soup = BeautifulSoup(html, 'html.parser')
    def movies(value):
        if isinstance(value, list):
            for entry in value:
                yield from movies(entry)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            if kinds == 'Movie' or isinstance(kinds, list) and 'Movie' in kinds:
                yield value
            if '@graph' in value:
                yield from movies(value['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        raw = re.sub(r'/\*.*?\*/', '', script.get_text(), flags=re.S).strip()
        try:
            movie = next(movies(json.loads(raw)), None)
        except (ValueError, TypeError):
            continue
        if movie:
            rating = movie.get('aggregateRating') or {}
            image = movie.get('image', '')
            if isinstance(image, list):
                image = image[0] if image else ''
            if isinstance(image, dict):
                image = image.get('url', '')
            return {'synopsis': BeautifulSoup(movie.get('description') or '', 'html.parser').get_text(' ', strip=True),
                    'image': image, 'rating': rating.get('ratingValue'),
                    'best': rating.get('bestRating', 5), 'count': rating.get('ratingCount')}
    raise ValueError('Letterboxd did not provide movie metadata on this page.')


def fetch_details(url):
    if not re.fullmatch(r'https://letterboxd\.com/film/[^/]+/', url):
        raise ValueError('Invalid Letterboxd film URL.')
    with requests.Session() as session:
        session.headers['User-Agent'] = 'MovieRoulette/1.0 (personal desktop movie picker)'
        retry = Retry(total=2, backoff_factor=.5, status_forcelist=[429, 500, 502, 503, 504], respect_retry_after_header=False)
        session.mount('https://', HTTPAdapter(max_retries=retry))
        response = session.get(url, timeout=(5, 12))
        response.raise_for_status()
        result = parse_details(response.text)
        result['poster'] = b''
        result['poster_error'] = False
        image = urlparse(result['image'])
        if image.scheme == 'https' and (image.hostname or '').endswith('.ltrbxd.com'):
            try:
                with session.get(result['image'], timeout=(5, 12), stream=True) as poster:
                    poster.raise_for_status()
                    data = bytearray()
                    for chunk in poster.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > 8_000_000:
                            raise ValueError('Poster exceeds download limit.')
                    result['poster'] = bytes(data)
            except (requests.RequestException, ValueError):
                result['poster_error'] = True
        return result
