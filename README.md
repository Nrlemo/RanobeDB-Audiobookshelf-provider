RanobeDB Audiobookshelf custom metadata provider
=======

Adaptación del plugin de Calibre para funcionar como proveedor de metadata para Audiobookshelf. Proporciona búsqueda avanzada de light novels desde RanobeDB.

## Características

- ✅ **Búsqueda avanzada**: Por título, autor y serie
- ✅ **Preferencias de idioma**: Configurable (Inglés, Romaji, Japonés)
- ✅ **Metadata completo**: Título, autor, descripción, editorial, géneros, fecha de publicación
- ✅ **Imágenes de portada**: Descarga automática desde RanobeDB
- ✅ **Información de series**: Número de volumen, nombre de serie
- ✅ **Control de límite de tasa**: Respeta los límites de API de RanobeDB
- ✅ **Búsqueda de respaldo**: Fallback a búsqueda por serie si fallla la búsqueda por título

## Instalación

### Requisitos

- Python 3.6+
- requests (opcional pero recomendado)
- flask (opcional, solo para ejecutar como servidor HTTP)

### Instalación básica

```bash
# Clonar o descargar el archivo
cp ranobedb_audiobookshelf_provider.py /ruta/a/tu/proyecto/

# Instalar dependencias (opcional)
pip install requests flask
```

Opcion imagen docker disponible en:

docker pull nrlemo/ranobedb-provider:latest

tambien hay un docker compose en el repositorio

## Uso

### 1. Como módulo Python (integración directa)

```python
from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

# Crear instancia con configuración
config = {
    'language_order': 'en,romaji,ja',
    'description_language': 'en',
    'max_results': 10,
    'enhance_series': 'basic',
    'fallback_series_search': 'yes',
}

provider = RanobeDBAudiobookshelfProvider(config)

# Buscar libros
results = provider.search(
    title='Sword Art Online',
    authors=['Reki Kawahara'],
    limit=5
)

# Procesar resultados
for book in results:
    print(f"Título: {book['title']}")
    print(f"Autores: {', '.join(book['authors'])}")
    print(f"Descripción: {book['description'][:100]}...")
    print()

# Obtener detalles completos de un libro
book_details = provider.get_book('12345')
if book_details:
    print(f"Detalles: {book_details}")

# Descargar portada
cover_data = provider.get_cover(book['coverPath'])
if cover_data:
    with open('cover.jpg', 'wb') as f:
        f.write(cover_data)
```

### 2. Como servidor HTTP (microservicio)

```bash
# Iniciar servidor
python ranobedb_audiobookshelf_provider.py server

# Por defecto escucha en http://localhost:5000
```

#### Endpoints disponibles:

**GET /health**
```bash
curl http://localhost:5000/health
```
Respuesta:
```json
{
  "status": "ok",
  "provider": "RanobeDB Light Novels",
  "version": "2.0.0"
}
```

**POST /search**
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sword Art Online",
    "authors": ["Reki Kawahara"],
    "limit": 5
  }'
```

**GET /book/{id}**
```bash
curl http://localhost:5000/book/12345
```

**GET /config**
```bash
curl http://localhost:5000/config
```

### 3. Desde línea de comandos

```bash
# Búsqueda simple
python ranobedb_audiobookshelf_provider.py search "Sword Art Online"

# Búsqueda con autor
python ranobedb_audiobookshelf_provider.py search "Sword Art Online" "Reki Kawahara"

# Iniciar servidor
python ranobedb_audiobookshelf_provider.py server
```

## Configuración

### Opciones disponibles

| Opción | Tipo | Valor por defecto | Descripción |
|--------|------|-------------------|-------------|
| `language_order` | string | `en,romaji,ja` | Orden de preferencia de idiomas (ej: en,romaji,ja) |
| `description_language` | choice | `en` | Idioma para descripciones: `en`, `ja`, `both` |
| `max_results` | number | `10` | Máximo de resultados de búsqueda (1-25) |
| `enhance_series` | choice | `basic` | Nivel de enriquecimiento de series: `no`, `basic`, `full` |
| `fallback_series_search` | choice | `yes` | Búsqueda de respaldo por serie: `yes`, `no` |

### Ejemplo de configuración

```python
config = {
    # Buscar primero en inglés, luego romaji, luego japonés
    'language_order': 'en,romaji,ja',
    
    # Usar descripciones en inglés (o 'ja' para japonés, 'both' para ambos)
    'description_language': 'en',
    
    # Máximo 10 resultados por búsqueda
    'max_results': 10,
    
    # Enriquecimiento de series: 'no' (rápido), 'basic' (recomendado), 'full' (lento)
    'enhance_series': 'basic',
    
    # Si la búsqueda por título falla, intentar búsqueda por serie
    'fallback_series_search': 'yes',
}
```

## Integración con Audiobookshelf

### Opción 1: Como plugin (si Audiobookshelf lo soporta)

Copiar el archivo a la carpeta de plugins de Audiobookshelf:
```bash
cp ranobedb_audiobookshelf_provider.py /ruta/audiobookshelf/plugins/
```

### Opción 2: Como servidor externo

1. Iniciar el servidor:
```bash
python ranobedb_audiobookshelf_provider.py server
```

2. Configurar Audiobookshelf para usar el servidor externo como proveedor de metadata

### Opción 3: Integración personalizada

Crear un script personalizado que integre el proveedor con Audiobookshelf:

```python
from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

class AudiobookshelfRanobeDBAdapter:
    def __init__(self):
        self.provider = RanobeDBAudiobookshelfProvider({
            'language_order': 'en,romaji,ja',
            'enhance_series': 'basic',
        })
    
    def get_metadata(self, title, author=None):
        """Obtener metadata en formato Audiobookshelf"""
        results = self.provider.search(title=title, authors=[author] if author else [])
        
        if not results:
            return None
        
        # Convertir al formato esperado por Audiobookshelf
        book = results[0]
        return {
            'title': book['title'],
            'author': ', '.join(book['authors']),
            'description': book['description'],
            'cover': book.get('coverPath'),
            'publishedYear': book.get('publishedYear'),
            'publisher': book.get('publisher'),
            'series': book.get('seriesName'),
            'seriesNumber': book.get('seriesSequence'),
        }
```

## Estructura de respuesta

### Búsqueda (search)

```json
{
  "title": "Sword Art Online",
  "authors": ["Reki Kawahara"],
  "description": "In the year 2022...",
  "genres": ["Action", "Adventure", "Fantasy"],
  "publishedYear": 2009,
  "publisher": "ASCII Media Works",
  "language": "en",
  "seriesName": "Sword Art Online",
  "seriesSequence": "1",
  "coverPath": "https://images.ranobedb.org/...",
  "relevance": 0,
  "id": "12345",
  "provider_id": "ranobedb_12345"
}
```

### Detalles de libro (get_book)

Contiene toda la información de búsqueda más:
```json
{
  "subtitle": "",
  "narrators": [],
  "duration": 0,
  "releaseDate": "2009-01-01"
}
```

## Limitaciones y consideraciones

- **Rate limiting**: El proveedor respeta el límite de 60 solicitudes/minuto de RanobeDB
- **Idiomas**: Optimizado para light novels, que pueden tener múltiples idiomas disponibles
- **Portadas**: Pueden no estar disponibles para todos los títulos
- **Búsqueda**: Los resultados dependen de la calidad y completitud de RanobeDB

## Solución de problemas

### "No se encuentran resultados"
- Verificar que el título sea correcto
- Intentar con variaciones del título (en inglés, japonés, etc.)
- Activar `fallback_series_search` en la configuración

### "Conexión rechazada"
- Verificar que RanobeDB esté accesible (https://ranobedb.org)
- Comprobar la conexión a Internet
- Revisar límites de tasa (esperar 1 segundo entre solicitudes)

### "Flask no disponible"
```bash
pip install flask
```

### "requests no disponible"
```bash
pip install requests
```

## Ejemplos de uso avanzado

### Búsqueda múltiple con paralelización

```python
from concurrent.futures import ThreadPoolExecutor
from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

provider = RanobeDBAudiobookshelfProvider()

titles = [
    'Sword Art Online',
    'Re:Zero',
    'That Time I Got Reincarnated as a Slime',
]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(
        lambda t: provider.search(title=t),
        titles
    ))

# Procesar resultados...
```

### Caché de resultados

```python
from functools import lru_cache
from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

class CachedProvider(RanobeDBAudiobookshelfProvider):
    @lru_cache(maxsize=128)
    def get_book_cached(self, book_id):
        return self.get_book(book_id)

provider = CachedProvider()
```

## API Reference

### `RanobeDBAudiobookshelfProvider`

#### `__init__(config: Dict)`
Inicializa el proveedor con configuración opcional.

#### `search(title, authors, publisher, narrator, limit) -> List[Dict]`
Busca libros en RanobeDB.

#### `get_book(book_id) -> Dict`
Obtiene detalles completos de un libro por ID.

#### `get_cover(cover_url) -> bytes`
Descarga la imagen de portada.

#### `get_config_options() -> Dict`
Devuelve las opciones de configuración disponibles.

## Licencia

GPL v3

## Autor


