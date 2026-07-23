#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba rápida para validar que el proveedor funciona
con la nueva estructura de RanobeDB.
"""

import json
from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

def test_provider():
    """Test el proveedor con datos reales de RanobeDB."""
    
    print("="*70)
    print("🧪 Test del Proveedor RanobeDB")
    print("="*70)
    print()
    
    config = {
        'language_order': 'en,romaji,ja',
        'description_language': 'en',
        'max_results': 10,
        'enhance_series': 'basic',
        'fallback_series_search': 'yes',
    }
    
    provider = RanobeDBAudiobookshelfProvider(config)
    
    # Test 1: Health
    print("[1/3] Testing basic initialization...")
    print(f"✅ Provider: {provider.name}")
    print(f"✅ Version: {provider.version}")
    print()
    
    # Test 2: Search
    print("[2/3] Testing search functionality...")
    print("Searching for: 'Sword Art Online'")
    print()
    
    try:
        results = provider.search(
            title='Sword Art Online',
            authors=[],
            limit=5
        )
        
        if results:
            print(f"✅ Found {len(results)} results")
            print()
            
            for i, book in enumerate(results[:3], 1):
                print(f"Result {i}:")
                print(f"  Title: {book.get('title', 'N/A')}")
                print(f"  Authors: {', '.join(book.get('authors', []))}")
                print(f"  ID: {book.get('id', 'N/A')}")
                print(f"  Cover: {'✅ Yes' if book.get('coverPath') else '❌ No'}")
                print()
        else:
            print("❌ No results found")
            print()
            
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        print()
    
    # Test 3: Alternative searches
    print("[3/3] Testing alternative searches...")
    test_queries = [
        'Re:Zero',
        'Spice and Wolf',
        'Overlord',
    ]
    
    for query in test_queries:
        try:
            results = provider.search(title=query, limit=1)
            status = "✅" if results else "❌"
            count = len(results) if results else 0
            print(f"{status} '{query}': {count} results")
        except Exception as e:
            print(f"❌ '{query}': Error - {e}")
    
    print()
    print("="*70)
    print("✅ Tests completados")
    print("="*70)

if __name__ == '__main__':
    try:
        test_provider()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelado por usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
