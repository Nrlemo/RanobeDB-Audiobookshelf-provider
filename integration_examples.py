#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integration examples for RanobeDB metadata provider with Audiobookshelf.

Demonstrates various ways to integrate the provider with Audiobookshelf.
"""

from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider
from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Basic Integration Adapter
# ============================================================================

class AudiobookshelfRanobeDBAdapter:
    """
    Basic adapter that converts RanobeDB metadata to Audiobookshelf format.
    
    This adapter takes metadata from the RanobeDB provider and converts it
    into the format expected by Audiobookshelf's metadata system.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the adapter."""
        self.provider = RanobeDBAudiobookshelfProvider(config)

    def search(self, title: Optional[str] = None,
               author: Optional[str] = None,
               limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for books and convert to Audiobookshelf format.
        
        :param title: Book title
        :param author: Author name
        :param limit: Maximum results
        :return: List of books in Audiobookshelf format
        """
        authors = [author] if author else []
        results = self.provider.search(title=title, authors=authors, limit=limit)

        # Convert to Audiobookshelf format
        converted = []
        for book in results:
            converted.append({
                'id': book['id'],
                'title': book['title'],
                'author': ', '.join(book['authors']) if book['authors'] else 'Unknown',
                'narrators': book.get('narrators', []),
                'description': book['description'],
                'cover': book.get('coverPath'),
                'publishYear': book.get('publishedYear'),
                'publisher': book.get('publisher'),
                'genres': book.get('genres', []),
                'series': {
                    'name': book.get('seriesName'),
                    'sequence': book.get('seriesSequence'),
                } if book.get('seriesName') else None,
                'language': book.get('language', 'en'),
                'source': 'ranobedb',
                'relevance': book.get('relevance', 100),
            })

        return converted

    def get_book_metadata(self, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a specific book.
        
        :param book_id: Book ID from RanobeDB
        :return: Book metadata in Audiobookshelf format
        """
        book = self.provider.get_book(book_id)
        if not book:
            return None

        return {
            'id': book['id'],
            'title': book['title'],
            'subtitle': book.get('subtitle'),
            'author': ', '.join(book['authors']) if book['authors'] else 'Unknown',
            'narrators': book.get('narrators', []),
            'description': book['description'],
            'cover': book.get('coverPath'),
            'publishYear': book.get('publishedYear'),
            'publisher': book.get('publisher'),
            'genres': book.get('genres', []),
            'tags': book.get('tags', []),
            'series': {
                'name': book.get('seriesName'),
                'sequence': book.get('seriesSequence'),
            } if book.get('seriesName') else None,
            'language': book.get('language', 'en'),
            'releaseDate': book.get('releaseDate'),
            'duration': book.get('duration'),
            'source': 'ranobedb',
        }


# ============================================================================
# Example 2: Caching Adapter with Local Cache
# ============================================================================

class CachedAudiobookshelfAdapter:
    """
    Adapter with local caching to improve performance.
    
    Caches search results and book metadata locally to avoid repeated
    API calls to RanobeDB.
    """

    def __init__(self, config: Optional[Dict] = None, cache_size: int = 100):
        """Initialize the adapter with caching."""
        self.adapter = AudiobookshelfRanobeDBAdapter(config)
        self.cache_size = cache_size
        self.search_cache: Dict[str, List[Dict]] = {}
        self.book_cache: Dict[str, Dict] = {}

    def search(self, title: Optional[str] = None,
               author: Optional[str] = None,
               limit: int = 10,
               use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Search with caching support.
        
        :param title: Book title
        :param author: Author name
        :param limit: Maximum results
        :param use_cache: Whether to use cached results
        :return: List of books
        """
        # Create cache key
        cache_key = f"{title}|{author}|{limit}"

        if use_cache and cache_key in self.search_cache:
            logger.info(f"Cache hit for search: {cache_key}")
            return self.search_cache[cache_key]

        # Search using adapter
        results = self.adapter.search(title=title, author=author, limit=limit)

        # Store in cache
        if len(self.search_cache) >= self.cache_size:
            # Remove oldest entry
            self.search_cache.pop(next(iter(self.search_cache)))

        self.search_cache[cache_key] = results
        return results

    def get_book_metadata(self, book_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get book metadata with caching.
        
        :param book_id: Book ID
        :param use_cache: Whether to use cached data
        :return: Book metadata
        """
        if use_cache and book_id in self.book_cache:
            logger.info(f"Cache hit for book: {book_id}")
            return self.book_cache[book_id]

        # Get from adapter
        book = self.adapter.get_book_metadata(book_id)

        if book:
            if len(self.book_cache) >= self.cache_size:
                self.book_cache.pop(next(iter(self.book_cache)))
            self.book_cache[book_id] = book

        return book

    def clear_cache(self):
        """Clear all cached data."""
        self.search_cache.clear()
        self.book_cache.clear()
        logger.info("Cache cleared")


# ============================================================================
# Example 3: Batch Processing Adapter
# ============================================================================

class BatchAudiobookshelfAdapter:
    """
    Adapter for processing multiple books in batch operations.
    
    Useful for bulk importing or updating metadata for multiple books
    at once.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the adapter."""
        self.adapter = AudiobookshelfRanobeDBAdapter(config)

    def batch_search(self, queries: List[Dict[str, str]],
                     batch_size: int = 10) -> Dict[str, List[Dict]]:
        """
        Search for multiple books in batch.
        
        :param queries: List of search queries, each with 'title' and optional 'author'
        :param batch_size: Number of searches per batch
        :return: Dictionary with query index as key and results as value
        """
        results = {}

        for i, query in enumerate(queries):
            title = query.get('title')
            author = query.get('author')

            logger.info(f"Batch search {i+1}/{len(queries)}: {title}")

            try:
                search_results = self.adapter.search(
                    title=title,
                    author=author,
                    limit=5
                )
                results[i] = search_results
            except Exception as e:
                logger.error(f"Batch search failed for query {i}: {e}")
                results[i] = []

            # Simple rate limiting
            if (i + 1) % batch_size == 0:
                logger.info(f"Processed {i + 1}/{len(queries)} queries")

        return results

    def update_books_metadata(self, book_ids: List[str]) -> Dict[str, Dict]:
        """
        Update metadata for multiple books.
        
        :param book_ids: List of RanobeDB book IDs
        :return: Dictionary with book ID as key and metadata as value
        """
        results = {}

        for book_id in book_ids:
            try:
                metadata = self.adapter.get_book_metadata(book_id)
                if metadata:
                    results[book_id] = metadata
            except Exception as e:
                logger.error(f"Failed to get metadata for book {book_id}: {e}")

        return results


# ============================================================================
# Example 4: Webhook Integration for Real-time Updates
# ============================================================================

class WebhookAudiobookshelfAdapter:
    """
    Adapter for webhook-based integration.
    
    Can receive webhooks from Audiobookshelf when books need metadata
    and respond with RanobeDB data.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the adapter."""
        self.adapter = AudiobookshelfRanobeDBAdapter(config)

    def handle_metadata_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a metadata request webhook.
        
        :param request_data: Webhook request data containing book info
        :return: Response with metadata
        """
        logger.info(f"Handling metadata request: {request_data}")

        title = request_data.get('title')
        author = request_data.get('author')
        book_id = request_data.get('id')

        # Try to get metadata
        if book_id and book_id.startswith('ranobedb_'):
            # Direct lookup by ID
            db_id = book_id.replace('ranobedb_', '')
            metadata = self.adapter.get_book_metadata(db_id)
        else:
            # Search by title and author
            results = self.adapter.search(title=title, author=author, limit=1)
            metadata = results[0] if results else None

        if metadata:
            return {
                'success': True,
                'metadata': metadata,
            }
        else:
            return {
                'success': False,
                'error': 'Metadata not found',
            }

    def handle_cover_request(self, book_id: str) -> Optional[bytes]:
        """
        Handle a cover image request.
        
        :param book_id: RanobeDB book ID
        :return: Cover image data
        """
        logger.info(f"Handling cover request for book: {book_id}")

        # Get book metadata to find cover URL
        metadata = self.adapter.get_book_metadata(book_id)
        if metadata and metadata.get('cover'):
            return self.adapter.provider.get_cover(metadata['cover'])

        return None


# ============================================================================
# Example 5: Configuration and Export
# ============================================================================

class ExportAdapter:
    """
    Adapter for exporting metadata to various formats.
    
    Can export search results and book metadata in different formats
    suitable for import into Audiobookshelf or other systems.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the adapter."""
        self.adapter = AudiobookshelfRanobeDBAdapter(config)

    def export_to_json(self, books: List[Dict[str, Any]],
                       filepath: str) -> bool:
        """
        Export books to JSON file.
        
        :param books: List of book metadata
        :param filepath: Output file path
        :return: True if successful
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(books, f, indent=2, ensure_ascii=False)
            logger.info(f"Exported {len(books)} books to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Export to JSON failed: {e}")
            return False

    def export_to_csv(self, books: List[Dict[str, Any]],
                      filepath: str) -> bool:
        """
        Export books to CSV file.
        
        :param books: List of book metadata
        :param filepath: Output file path
        :return: True if successful
        """
        try:
            import csv

            if not books:
                logger.warning("No books to export")
                return False

            # Get all unique keys
            fieldnames = set()
            for book in books:
                fieldnames.update(book.keys())
            fieldnames = sorted(list(fieldnames))

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(books)

            logger.info(f"Exported {len(books)} books to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Export to CSV failed: {e}")
            return False

    def export_to_audiobookshelf_import(self, books: List[Dict[str, Any]],
                                        filepath: str) -> bool:
        """
        Export in Audiobookshelf import format.
        
        :param books: List of book metadata
        :param filepath: Output file path
        :return: True if successful
        """
        # Format for Audiobookshelf bulk import
        import_data = {
            'provider': 'ranobedb',
            'version': '2.0.0',
            'books': books,
            'count': len(books),
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(import_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Exported {len(books)} books in Audiobookshelf format to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False


# ============================================================================
# Usage Examples
# ============================================================================

def example_basic_search():
    """Example: Basic search and results."""
    print("Example 1: Basic Search")
    print("-" * 40)

    config = {
        'language_order': 'en,romaji,ja',
        'max_results': 5,
    }

    adapter = AudiobookshelfRanobeDBAdapter(config)
    results = adapter.search(
        title='Sword Art Online',
        author='Reki Kawahara',
        limit=3
    )

    for book in results:
        print(f"Title: {book['title']}")
        print(f"Author: {book['author']}")
        if book.get('series'):
            print(f"Series: {book['series']['name']} #{book['series']['sequence']}")
        print()


def example_cached_search():
    """Example: Cached search for better performance."""
    print("Example 2: Cached Search")
    print("-" * 40)

    config = {
        'language_order': 'en,romaji,ja',
    }

    adapter = CachedAudiobookshelfAdapter(config)

    # First search (will query API)
    print("First search (from API)...")
    results1 = adapter.search(title='Re:Zero', limit=3)
    print(f"Found {len(results1)} results\n")

    # Second search (will use cache)
    print("Second search (from cache)...")
    results2 = adapter.search(title='Re:Zero', limit=3, use_cache=True)
    print(f"Found {len(results2)} results\n")

    adapter.clear_cache()


def example_batch_processing():
    """Example: Batch processing multiple books."""
    print("Example 3: Batch Processing")
    print("-" * 40)

    config = {
        'language_order': 'en,romaji,ja',
    }

    adapter = BatchAudiobookshelfAdapter(config)

    queries = [
        {'title': 'Sword Art Online', 'author': 'Reki Kawahara'},
        {'title': 'Re:Zero'},
        {'title': 'Overlord'},
    ]

    results = adapter.batch_search(queries)
    for idx, books in results.items():
        print(f"Query {idx}: Found {len(books)} results")


def example_export():
    """Example: Export search results to different formats."""
    print("Example 4: Export Results")
    print("-" * 40)

    config = {
        'language_order': 'en,romaji,ja',
    }

    adapter = AudiobookshelfRanobeDBAdapter(config)
    export = ExportAdapter(config)

    # Search for books
    results = adapter.search(title='Light Novel', limit=5)

    if results:
        # Export to different formats
        export.export_to_json(results, 'results.json')
        export.export_to_csv(results, 'results.csv')
        export.export_to_audiobookshelf_import(results, 'import.json')


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run examples
    try:
        example_basic_search()
        example_cached_search()
        example_batch_processing()
        example_export()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
