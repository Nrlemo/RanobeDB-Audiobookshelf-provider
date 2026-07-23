#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup script for RanobeDB Audiobookshelf Metadata Provider

Handles installation, configuration, and deployment of the metadata provider.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path


class ProviderSetup:
    """Setup and configuration helper for RanobeDB provider."""

    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.config_file = self.script_dir / 'config.json'

    def check_dependencies(self):
        """Check and report on dependencies."""
        print("Checking dependencies...")
        print()

        dependencies = {
            'requests': 'Optional - for HTTP requests',
            'flask': 'Optional - for running as HTTP server',
            'json': 'Built-in - for configuration',
        }

        installed = []
        missing = []

        for package, description in dependencies.items():
            if package == 'json':
                installed.append((package, description))
                continue

            try:
                __import__(package)
                installed.append((package, description))
            except ImportError:
                missing.append((package, description))

        print("✓ Installed:")
        for package, desc in installed:
            print(f"  - {package}: {desc}")
        print()

        if missing:
            print("✗ Missing (optional):")
            for package, desc in missing:
                print(f"  - {package}: {desc}")
            print()
            print("Install optional dependencies with:")
            print(f"  pip install {' '.join(pkg for pkg, _ in missing)}")
            print()

        return len(missing) == 0

    def create_config(self, preset='basic'):
        """Create configuration file."""
        print(f"Creating configuration file (preset: {preset})...")

        presets = {
            'basic': {
                'language_order': 'en,romaji,ja',
                'description_language': 'en',
                'max_results': 10,
                'enhance_series': 'basic',
                'fallback_series_search': 'yes',
            },
            'english': {
                'language_order': 'en',
                'description_language': 'en',
                'max_results': 5,
                'enhance_series': 'basic',
                'fallback_series_search': 'yes',
            },
            'comprehensive': {
                'language_order': 'en,romaji,ja',
                'description_language': 'both',
                'max_results': 15,
                'enhance_series': 'full',
                'fallback_series_search': 'yes',
            },
            'fast': {
                'language_order': 'en',
                'description_language': 'en',
                'max_results': 5,
                'enhance_series': 'no',
                'fallback_series_search': 'no',
            },
        }

        config = presets.get(preset, presets['basic'])

        if self.config_file.exists():
            response = input(f"Configuration file exists. Overwrite? (y/n): ").lower()
            if response != 'y':
                print("Configuration creation cancelled.")
                return False

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"✓ Configuration created at: {self.config_file}")
        print()
        return True

    def test_provider(self):
        """Test the metadata provider."""
        print("Testing metadata provider...")
        print()

        try:
            from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider

            # Load configuration
            config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

            # Create provider
            provider = RanobeDBAudiobookshelfProvider(config)

            # Test search
            print("Testing search functionality...")
            print("Searching for: 'Sword Art Online'")
            results = provider.search(
                title='Sword Art Online',
                authors=['Reki Kawahara'],
                limit=3
            )

            if results:
                print(f"✓ Found {len(results)} results")
                print()
                for i, book in enumerate(results, 1):
                    print(f"  {i}. {book['title']}")
                    if book['authors']:
                        print(f"     Authors: {', '.join(book['authors'][:2])}")
                    if book['publishedYear']:
                        print(f"     Year: {book['publishedYear']}")
                print()
                return True
            else:
                print("✗ No results found")
                print("  Check your internet connection and try again.")
                print()
                return False

        except ImportError as e:
            print(f"✗ Error importing provider: {e}")
            return False
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False

    def install_systemd_service(self):
        """Create systemd service file for running as daemon."""
        if sys.platform != 'linux':
            print("Systemd service only available on Linux")
            return False

        service_name = 'ranobedb-provider'
        service_file = f'/etc/systemd/system/{service_name}.service'
        provider_file = os.path.abspath(
            self.script_dir / 'ranobedb_audiobookshelf_provider.py'
        )

        service_content = f"""[Unit]
Description=RanobeDB Metadata Provider for Audiobookshelf
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={self.script_dir}
ExecStart=/usr/bin/python3 {provider_file} server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

        print(f"Creating systemd service: {service_file}")
        print()
        print("Service content:")
        print(service_content)
        print()

        if os.geteuid() != 0:
            print("✗ Root privileges required to install systemd service")
            print("  Run with: sudo python setup.py install-service")
            return False

        try:
            with open(service_file, 'w') as f:
                f.write(service_content)

            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            print(f"✓ Service installed")
            print()
            print("To enable and start the service:")
            print(f"  sudo systemctl enable {service_name}")
            print(f"  sudo systemctl start {service_name}")
            print()
            print("To view logs:")
            print(f"  sudo journalctl -u {service_name} -f")
            print()
            return True

        except Exception as e:
            print(f"✗ Failed to install service: {e}")
            return False

    def create_docker_files(self):
        """Create Dockerfile for containerization."""
        print("Creating Docker files...")

        dockerfile_content = """FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy provider
COPY ranobedb_audiobookshelf_provider.py .
COPY config.json .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
  CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run server
CMD ["python", "ranobedb_audiobookshelf_provider.py", "server"]
"""

        requirements_content = """requests>=2.25.0
flask>=2.0.0
"""

        docker_compose_content = """version: '3.8'

services:
  ranobedb-provider:
    build: .
    ports:
      - "5000:5000"
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
"""

        files = {
            'Dockerfile': dockerfile_content,
            'requirements.txt': requirements_content,
            'docker-compose.yml': docker_compose_content,
        }

        for filename, content in files.items():
            filepath = self.script_dir / filename
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✓ Created {filename}")

        print()
        print("To build and run with Docker:")
        print("  docker-compose up --build")
        print()
        return True

    def print_usage_examples(self):
        """Print usage examples."""
        print("Usage examples:")
        print()
        print("1. As Python module:")
        print("   from ranobedb_audiobookshelf_provider import RanobeDBAudiobookshelfProvider")
        print("   provider = RanobeDBAudiobookshelfProvider(config)")
        print("   results = provider.search(title='Sword Art Online')")
        print()
        print("2. As HTTP server:")
        print("   python ranobedb_audiobookshelf_provider.py server")
        print("   curl http://localhost:5000/health")
        print()
        print("3. Command line search:")
        print("   python ranobedb_audiobookshelf_provider.py search 'Sword Art Online'")
        print()

    def run_interactive_setup(self):
        """Run interactive setup wizard."""
        print("=" * 60)
        print("RanobeDB Metadata Provider Setup Wizard")
        print("=" * 60)
        print()

        # Check dependencies
        self.check_dependencies()

        # Create config
        while True:
            print("Configuration Presets:")
            print("  1. Basic (recommended)")
            print("  2. English only")
            print("  3. Comprehensive (more data, slower)")
            print("  4. Fast (minimal data, fastest)")
            print()
            choice = input("Select configuration preset (1-4, default 1): ").strip() or '1'

            presets_map = {
                '1': 'basic',
                '2': 'english',
                '3': 'comprehensive',
                '4': 'fast',
            }

            if choice in presets_map:
                self.create_config(presets_map[choice])
                break
            else:
                print("Invalid choice. Please select 1-4.")
                print()

        # Test provider
        while True:
            print()
            response = input("Test the provider now? (y/n, default y): ").lower()
            if response in ('y', ''):
                if self.test_provider():
                    break
                else:
                    print("Please check your configuration and try again.")
            else:
                break

        # Additional setup options
        print()
        print("Additional setup options:")
        print()

        response = input("Create Docker files? (y/n, default n): ").lower()
        if response == 'y':
            self.create_docker_files()

        if sys.platform == 'linux':
            response = input("Install as systemd service? (y/n, default n): ").lower()
            if response == 'y':
                self.install_systemd_service()

        print()
        print("=" * 60)
        print("Setup complete!")
        print("=" * 60)
        self.print_usage_examples()


def main():
    parser = argparse.ArgumentParser(
        description='Setup RanobeDB Metadata Provider'
    )
    parser.add_argument(
        'command',
        nargs='?',
        default='setup',
        choices=[
            'setup', 'test', 'config', 'docker',
            'install-service', 'examples', 'dependencies'
        ],
        help='Command to run'
    )
    parser.add_argument(
        '--preset',
        choices=['basic', 'english', 'comprehensive', 'fast'],
        default='basic',
        help='Configuration preset'
    )

    args = parser.parse_args()
    setup = ProviderSetup()

    try:
        if args.command == 'setup':
            setup.run_interactive_setup()
        elif args.command == 'test':
            setup.test_provider()
        elif args.command == 'config':
            setup.create_config(args.preset)
        elif args.command == 'docker':
            setup.create_docker_files()
        elif args.command == 'install-service':
            setup.install_systemd_service()
        elif args.command == 'examples':
            setup.print_usage_examples()
        elif args.command == 'dependencies':
            setup.check_dependencies()
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
