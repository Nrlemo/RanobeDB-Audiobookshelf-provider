#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
"""
RanobeDB Metadata Provider for Audiobookshelf

Provides metadata and covers from RanobeDB (https://ranobedb.org) for light novels
via HTTP API compatible with Audiobookshelf metadata providers.

Features:
- Advanced search by title, author, and series
- Language preference configuration
- Rate limiting for API requests
- Cover image caching
- Series metadata enrichment
- Fallback series search

License: GPL v3
"""

from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2024, RanobeDB Provider Author'
__docformat__ = 'restructuredtext en'

import json
import time
import logging
import threading
from urllib.parse import urlencode, quote_plus
from typing import Dict, List, Optional, Tuple, Any
import traceback

try:
    import requests
except ImportError:
    requests = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RanobeDBAudiobookshelfProvider:
    """
    Metadata provider for Audiobookshelf using RanobeDB as data source.
    
    Provides book identification, metadata retrieval, and cover downloads
    for light novels from RanobeDB.
    """

    name = 'RanobeDB Light Novels'
    version = '2.0.0'
    description = 'Downloads metadata and covers from RanobeDB for light novels'
    author = 'RanobeDB Provider Author'

    # API settings
    BASE_URL = 'https://ranobedb.org/api/v0'
    WEBSITE_URL = 'https://ranobedb.org'
    IMAGE_BASE_URL = 'https://images.ranobedb.org'

    # Rate limiting: 60 requests/minute = 1 second between requests
    RATE_LIMIT_DELAY = 1.0
    _last_request_time = 0
    _rate_lock = threading.Lock()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metadata provider.

        :param config: Configuration dictionary with options like:
            - language_order: Comma-separated language preference (en,romaji,ja)
            - description_language: Preferred description language (en, ja, both)
            - max_results: Maximum number of search results (1-25)
            - enhance_series: Series enhancement level (no, basic, full)
            - fallback_series_search: Enable fallback series search (yes, no)
        """
        self.config = config or {}
        self._init_session()

    def _init_session(self):
        """Initialize requests session if available."""
        if requests:
            self.session = requests.Session()
            self.session.timeout = 30
        else:
            self.session = None
            logger.warning("requests library not available, using urllib")

    def _rate_limit(self):
        """Ensure we don't exceed RanobeDB's rate limit of 60 requests/minute."""
        with RanobeDBAudiobookshelfProvider._rate_lock:
            elapsed = time.time() - RanobeDBAudiobookshelfProvider._last_request_time
            if elapsed < self.RATE_LIMIT_DELAY:
                time.sleep(self.RATE_LIMIT_DELAY - elapsed)
            RanobeDBAudiobookshelfProvider._last_request_time = time.time()

    # =========================================================================
    # Language Preference Helpers
    # =========================================================================

    def _parse_language_order(self) -> List[str]:
        """
        Parse user's language preference string into ordered list.

        :return: List of language codes in preferred order
        """
        order_str = self.config.get('language_order', 'en,romaji,ja')
        order = []

        for lang in order_str.split(','):
            lang = lang.strip().lower()
            # Normalize language codes
            if lang in ('en', 'english'):
                lang = 'en'
            elif lang in ('ja', 'japanese', 'jp'):
                lang = 'ja'
            elif lang == 'romaji':
                lang = 'romaji'
            else:
                continue

            if lang not in order:
                order.append(lang)

        # Ensure all languages are included as fallbacks
        for lang in ['en', 'romaji', 'ja']:
            if lang not in order:
                order.append(lang)

        return order

    def _select_by_language(self, options: Dict[str, Optional[str]]) -> Optional[str]:
        """
        Select value based on user's language preference order.

        :param options: Dict with keys 'en', 'romaji', 'ja' and corresponding values
        :return: First non-empty value in preferred order, or None
        """
        order = self._parse_language_order()

        for lang in order:
            value = options.get(lang)
            if value:
                return value

        # Fallback to any non-None value
        for value in options.values():
            if value:
                return value

        return None

    # =========================================================================
    # API Request Helpers
    # =========================================================================

    def _make_api_request(self, endpoint: str, params: Optional[Dict] = None,
                         timeout: int = 30) -> Optional[Dict]:
        """
        Make a rate-limited request to the RanobeDB API.

        :param endpoint: API endpoint (e.g., '/books' or '/book/123')
        :param params: Optional query parameters dict
        :param timeout: Request timeout in seconds
        :return: Parsed JSON response or None on error
        """
        self._rate_limit()

        url = self.BASE_URL + endpoint
        if params:
            url += '?' + urlencode(params)

        logger.info(f'RanobeDB API request: {url}')

        try:
            if requests and self.session:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.json()
            else:
                # Fallback to urllib
                import urllib.request
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    raw = response.read()
                    return json.loads(raw)

        except Exception as e:
            logger.exception(f'RanobeDB API error: {str(e)}')
            return None

    # =========================================================================
    # Search Helpers
    # =========================================================================

    def _create_search_query(self, title: Optional[str] = None,
                            authors: Optional[List[str]] = None) -> str:
        """
        Create a search query from title and authors.

        :param title: Book title
        :param authors: List of author names
        :return: Search query string
        """
        parts = []

        if title:
            parts.append(title)

        if authors:
            for author in authors:
                if author and author not in parts:
                    parts.append(author)

        query = ' '.join(parts).strip()
        return query[:500]  # Limit query length

    def _search_books(self, query: str, timeout: int = 30) -> Optional[List[Dict]]:
        """
        Search for books on RanobeDB.

        :param query: Search query
        :param timeout: Request timeout
        :return: List of book results or None on error
        """
        if not query:
            return None

        max_results = self.config.get('max_results', 10)
        params = {
            'q': query,
            'limit': min(max(int(max_results), 1), 25),
        }

        result = self._make_api_request('/books', params, timeout)

        # Manejar ambas estructuras de respuesta posibles
        if result and isinstance(result, dict):
            # Intentar obtener libros/series de diferentes keys
            books = result.get('books', result.get('series', []))
            if isinstance(books, list):
                return books

        return None

    # =========================================================================
    # Book Details Retrieval
    # =========================================================================

    def _get_book_details(self, book_id: str, timeout: int = 30) -> Optional[Dict]:
        """
        Fetch complete details for a specific book.

        :param book_id: RanobeDB book ID
        :param timeout: Request timeout
        :return: Complete book data or None on error
        """
        endpoint = f'/books/{book_id}'
        return self._make_api_request(endpoint, timeout=timeout)

    def _get_series_details(self, series_id: str, timeout: int = 30) -> Optional[Dict]:
        """
        Fetch complete details for a series including all volumes.

        :param series_id: RanobeDB series ID
        :param timeout: Request timeout
        :return: Complete series data or None on error
        """
        endpoint = f'/series/{series_id}'
        return self._make_api_request(endpoint, timeout=timeout)

    # =========================================================================
    # Metadata Extraction
    # =========================================================================

    def _extract_metadata(self, book_data: Dict, relevance: int = 0,
                         timeout: int = 30) -> Dict[str, Any]:
        """
        Extract metadata from RanobeDB book data.

        :param book_data: Book data from RanobeDB API
        :param relevance: Relevance score for ranking (0 = best)
        :param timeout: Request timeout
        :return: Metadata dictionary suitable for Audiobookshelf
        """
        metadata = {
            'id': str(book_data.get('id', '')),
            'provider_id': f"ranobedb_{book_data.get('id', '')}",
            'title': '',
            'subtitle': '',
            'description': '',
            'authors': [],
            'narrators': [],
            'genres': [],
            'tags': [],
            'publishedYear': None,
            'publisher': '',
            'language': 'en',
            'duration': 0,
            'coverPath': '',
            'releaseDate': None,
            'seriesName': '',
            'seriesSequence': '',
            'relevance': relevance,
        }

        # Extract title - manejar nueva estructura de RanobeDB
        # La API actual devuelve: title, title_orig, romaji, romaji_orig
        title = book_data.get('title')
        
        # Si title no existe o está vacío, intentar otras opciones basadas en language_order
        if not title:
            order = self._parse_language_order()
            for lang in order:
                if lang == 'en' and book_data.get('title'):
                    title = book_data.get('title')
                    break
                elif lang == 'romaji' and book_data.get('romaji'):
                    title = book_data.get('romaji')
                    break
                elif lang == 'ja' and book_data.get('title_orig'):
                    title = book_data.get('title_orig')
                    break
        
        # Fallback final
        if not title:
            title = book_data.get('title') or book_data.get('romaji') or book_data.get('title_orig')

        metadata['title'] = str(title) if title else 'Unknown'

        # Extract description
        description_lang = self.config.get('description_language', 'en')
        if description_lang == 'both':
            desc_en = book_data.get('description', {}).get('en', '')
            desc_ja = book_data.get('description', {}).get('ja', '')
            metadata['description'] = (desc_en + '\n\n' + desc_ja).strip()
        else:
            desc_obj = book_data.get('description', {})
            if isinstance(desc_obj, dict):
                metadata['description'] = desc_obj.get(description_lang, '')
            else:
                metadata['description'] = str(desc_obj) if desc_obj else ''

        # Extract authors - manejar nueva estructura de RanobeDB
        authors = book_data.get('authors', [])
        if isinstance(authors, list):
            for author in authors:
                if isinstance(author, dict):
                    # Intentar obtener nombre del autor en el idioma preferido
                    if 'name' in author:
                        if isinstance(author['name'], dict):
                            author_name = self._select_by_language(author.get('name', {}))
                        else:
                            author_name = str(author['name'])
                    else:
                        author_name = None
                elif isinstance(author, str):
                    author_name = author
                else:
                    author_name = None

                if author_name:
                    metadata['authors'].append(author_name)
        
        # Si no hay autores, usar campo alternativo si existe
        if not metadata['authors'] and book_data.get('author'):
            author = book_data.get('author')
            if isinstance(author, str):
                metadata['authors'] = [author]
            elif isinstance(author, dict) and author.get('name'):
                metadata['authors'] = [str(author['name'])]

        # Extract publisher
        publisher = book_data.get('publisher')
        if isinstance(publisher, dict):
            metadata['publisher'] = self._select_by_language(publisher.get('name', {})) or ''
        else:
            metadata['publisher'] = str(publisher) if publisher else ''

        # Extract genres/tags
        genres = book_data.get('genres', [])
        if isinstance(genres, list):
            for genre in genres:
                if isinstance(genre, dict):
                    genre_name = self._select_by_language(genre.get('name', {}))
                elif isinstance(genre, str):
                    genre_name = genre
                else:
                    genre_name = None

                if genre_name:
                    metadata['genres'].append(genre_name)

        # Extract publication date
        release_date = book_data.get('release_date')
        if release_date:
            try:
                metadata['publishedYear'] = int(release_date[:4])
                metadata['releaseDate'] = release_date
            except (ValueError, TypeError):
                pass

        # Extract language
        lang = book_data.get('lang')
        if lang:
            metadata['language'] = lang

        # Extract cover - manejar ambas estructuras (books y series)
        image = book_data.get('image')
        
        # Si no está en 'image', buscar en 'book.image' (estructura de series)
        if not image:
            book_obj = book_data.get('book')
            if book_obj and isinstance(book_obj, dict):
                image = book_obj.get('image')
        
        if image and isinstance(image, dict):
            filename = image.get('filename')
            if filename:
                metadata['coverPath'] = f'{self.IMAGE_BASE_URL}/{filename}'

        # Extract series information - manejar nueva estructura de RanobeDB
        enhance_series = self.config.get('enhance_series', 'basic')
        if enhance_series != 'no':
            series_data = book_data.get('series')
            if series_data:
                if isinstance(series_data, dict):
                    # Manejar tanto diccionario como string para el nombre de serie
                    series_name_obj = series_data.get('name', {})
                    if isinstance(series_name_obj, dict):
                        series_name = self._select_by_language(series_name_obj)
                    else:
                        series_name = str(series_name_obj) if series_name_obj else None
                    
                    metadata['seriesName'] = series_name or ''

                    # Extract series index si está disponible
                    series_books = series_data.get('books', [])
                    if isinstance(series_books, list):
                        try:
                            for idx, book in enumerate(series_books, 1):
                                if book.get('id') == book_data.get('id'):
                                    metadata['seriesSequence'] = str(idx)
                                    break
                        except Exception as e:
                            logger.warning(f'Error extracting series index: {e}')

        return metadata

    # =========================================================================
    # Public API Methods
    # =========================================================================

    def search(self, title: Optional[str] = None,
               authors: Optional[List[str]] = None,
               publisher: Optional[str] = None,
               narrator: Optional[str] = None,
               limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for books in RanobeDB.

        :param title: Book title to search for
        :param authors: List of author names
        :param publisher: Publisher name (not used for RanobeDB)
        :param narrator: Narrator name (not used for RanobeDB)
        :param limit: Maximum number of results to return
        :return: List of book metadata dictionaries
        """
        logger.info(f'Searching: title={title}, authors={authors}')

        # Create search query
        query = self._create_search_query(title, authors)

        if not query:
            logger.warning('Insufficient metadata for search')
            return []

        # Search for books
        search_results = self._search_books(query)

        if not search_results:
            logger.info('No results found')
            # Try fallback series search if enabled
            if self.config.get('fallback_series_search', 'yes') == 'yes' and title:
                logger.info(f'Trying fallback series search for: {title}')
                search_results = self._search_by_series(title)

            if not search_results:
                return []

        logger.info(f'Found {len(search_results)} results')

        # Process results
        results = []
        max_results = min(limit, len(search_results))

        # Determine how many to fetch full details for
        top_score = search_results[0].get('sim_score', 0) if search_results else 0
        if top_score >= 0.9:
            fetch_count = 1
            logger.info(f'High confidence match (score {top_score:.2f}), fetching full details for 1 result')
        else:
            fetch_count = min(3, len(search_results))
            logger.info(f'Fetching full details for top {fetch_count} results')

        # Fetch full details for top results
        for relevance, book in enumerate(search_results[:fetch_count]):
            book_id = book.get('id')
            if not book_id:
                continue

            try:
                logger.info(f'Fetching details for book ID: {book_id}')
                book_data = self._get_book_details(str(book_id))

                if book_data:
                    metadata = self._extract_metadata(book_data, relevance)
                    results.append(metadata)
                    logger.info(f'Added result: {metadata["title"]} by {", ".join(metadata["authors"])}')
            except Exception as e:
                logger.exception(f'Error fetching details for book {book_id}: {e}')
                continue

        # Add basic metadata for remaining results (fast path - no API calls)
        for relevance, book in enumerate(search_results[fetch_count:], start=fetch_count):
            try:
                # Convert search result to basic metadata
                # Manejar nuevo formato de RanobeDB
                title = book.get('title') or book.get('romaji') or book.get('title_orig') or 'Unknown'
                
                metadata = {
                    'id': str(book.get('id', '')),
                    'provider_id': f"ranobedb_{book.get('id', '')}",
                    'title': str(title),
                    'authors': [],
                    'description': '',
                    'genres': [],
                    'publishedYear': None,
                    'publisher': '',
                    'language': book.get('lang', 'en'),
                    'relevance': relevance,
                }

                # Extract cover from search result - manejar ambas estructuras
                image = book.get('image')
                
                # Si no está en 'image', buscar en 'book.image' (estructura de series)
                if not image:
                    book_obj = book.get('book')
                    if book_obj and isinstance(book_obj, dict):
                        image = book_obj.get('image')
                
                if image and isinstance(image, dict):
                    filename = image.get('filename')
                    if filename:
                        metadata['coverPath'] = f'{self.IMAGE_BASE_URL}/{filename}'

                results.append(metadata)
                logger.info(f'Added basic result: {metadata["title"]}')
            except Exception as e:
                logger.exception(f'Error processing search result: {e}')
                continue

        return results[:max_results]

    def _search_by_series(self, series_name: str, timeout: int = 30) -> Optional[List[Dict]]:
        """
        Fallback search by series name.

        :param series_name: Series name to search for
        :param timeout: Request timeout
        :return: List of series/books in the series or None
        """
        params = {
            'q': series_name,
            'limit': 25,
        }

        result = self._make_api_request('/series', params, timeout)

        if result and isinstance(result, dict):
            series_list = result.get('series', [])
            if isinstance(series_list, list) and series_list:
                return series_list
        
        return None

    def get_book(self, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a specific book.

        :param book_id: RanobeDB book ID
        :return: Complete book metadata or None
        """
        logger.info(f'Getting book details for ID: {book_id}')

        try:
            book_data = self._get_book_details(book_id)
            if book_data:
                return self._extract_metadata(book_data)
        except Exception as e:
            logger.exception(f'Error getting book {book_id}: {e}')

        return None

    def get_cover(self, cover_url: str, timeout: int = 30) -> Optional[bytes]:
        """
        Download cover image from URL.

        :param cover_url: URL to the cover image
        :param timeout: Request timeout
        :return: Cover image data or None on error
        """
        self._rate_limit()

        logger.info(f'Downloading cover from: {cover_url}')

        try:
            if requests:
                response = requests.get(cover_url, timeout=timeout)
                response.raise_for_status()
                return response.content
            else:
                # Fallback to urllib
                import urllib.request
                with urllib.request.urlopen(cover_url, timeout=timeout) as response:
                    return response.read()

        except Exception as e:
            logger.exception(f'Failed to download cover: {e}')
            return None

    def get_config_options(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available configuration options.

        :return: Dictionary of configuration options
        """
        return {
            'language_order': {
                'type': 'string',
                'default': 'en,romaji,ja',
                'description': 'Comma-separated language preference order (en, romaji, ja)',
                'example': 'en,romaji,ja',
            },
            'description_language': {
                'type': 'choice',
                'default': 'en',
                'choices': ['en', 'ja', 'both'],
                'description': 'Preferred language for book descriptions',
            },
            'max_results': {
                'type': 'number',
                'default': 10,
                'min': 1,
                'max': 25,
                'description': 'Maximum number of search results to return',
            },
            'enhance_series': {
                'type': 'choice',
                'default': 'basic',
                'choices': ['no', 'basic', 'full'],
                'description': 'Series metadata enhancement level',
            },
            'fallback_series_search': {
                'type': 'choice',
                'default': 'yes',
                'choices': ['yes', 'no'],
                'description': 'Enable fallback series search if title search fails',
            },
        }


# ============================================================================
# HTTP Server for Audiobookshelf Integration
# ============================================================================

def create_flask_app(config: Optional[Dict] = None) -> Optional[Any]:
    """
    Create a Flask application for serving the metadata provider.

    This function requires Flask to be installed.

    :param config: Configuration dictionary
    :return: Flask app or None if Flask not available
    """
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.warning("Flask not available. Install with: pip install flask")
        return None

    app = Flask(__name__)
    provider = RanobeDBAudiobookshelfProvider(config)

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'ok',
            'provider': provider.name,
            'version': provider.version,
        })

    @app.route('/search', methods=['POST'])
    def search():
        """Search endpoint."""
        try:
            data = request.get_json() or {}
            title = data.get('title')
            authors = data.get('authors', [])
            limit = data.get('limit', 10)

            results = provider.search(
                title=title,
                authors=authors,
                limit=limit
            )

            return jsonify({
                'success': True,
                'results': results,
            })
        except Exception as e:
            logger.exception('Search error')
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/book/<book_id>', methods=['GET'])
    def get_book(book_id):
        """Get book details endpoint."""
        try:
            book = provider.get_book(book_id)
            if book:
                return jsonify({
                    'success': True,
                    'book': book,
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Book not found',
                }), 404
        except Exception as e:
            logger.exception('Book fetch error')
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/config', methods=['GET'])
    def get_config():
        """Get configuration options endpoint."""
        return jsonify({
            'success': True,
            'options': provider.get_config_options(),
        })

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(error):
        logger.exception('Server error')
        return jsonify({'success': False, 'error': 'Server error'}), 500

    return app


if __name__ == '__main__':
    # Example usage
    import sys

    # Create provider
    config = {
        'language_order': 'en,romaji,ja',
        'description_language': 'en',
        'max_results': 10,
        'enhance_series': 'basic',
        'fallback_series_search': 'yes',
    }

    provider = RanobeDBAudiobookshelfProvider(config)

    if len(sys.argv) > 1 and sys.argv[1] == 'server':
        # Run as HTTP server
        app = create_flask_app(config)
        if app:
            print('Starting Audiobookshelf metadata provider server...')
            app.run(host='0.0.0.0', port=5000, debug=False)
        else:
            print('Flask is required to run the server. Install with: pip install flask')
            sys.exit(1)
    else:
        # Command line search
        if len(sys.argv) < 2:
            print('Usage:')
            print('  python ranobedb_audiobookshelf_provider.py search "<title>" [author1] [author2] ...')
            print('  python ranobedb_audiobookshelf_provider.py server')
            print()
            print('Example:')
            print('  python ranobedb_audiobookshelf_provider.py search "Sword Art Online" "Reki Kawahara"')
            sys.exit(1)

        command = sys.argv[1]

        if command == 'search':
            title = sys.argv[2] if len(sys.argv) > 2 else None
            authors = sys.argv[3:] if len(sys.argv) > 3 else []

            print(f'Searching for: {title}')
            if authors:
                print(f'Authors: {", ".join(authors)}')

            results = provider.search(title=title, authors=authors)

            print(f'\nFound {len(results)} results:\n')
            for i, result in enumerate(results, 1):
                print(f'{i}. {result["title"]}')
                if result['authors']:
                    print(f'   Authors: {", ".join(result["authors"])}')
                if result['seriesName']:
                    print(f'   Series: {result["seriesName"]} #{result["seriesSequence"]}')
                if result['publishedYear']:
                    print(f'   Published: {result["publishedYear"]}')
                print()
