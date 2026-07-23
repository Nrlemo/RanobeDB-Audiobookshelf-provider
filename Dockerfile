FROM python:3.11-slim

LABEL maintainer="RanobeDB Provider Author"
LABEL description="RanobeDB Metadata Provider for Audiobookshelf"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ranobedb_audiobookshelf_provider.py .
COPY config.json .

# Create non-root user
RUN useradd -m -u 1000 provider && chown -R provider:provider /app
USER provider

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=ranobedb_audiobookshelf_provider.py

# Run server
CMD ["python", "ranobedb_audiobookshelf_provider.py", "server"]
