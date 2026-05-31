#!/usr/bin/env python3
"""
Generate OpenAPI specification from FastAPI application.

Usage:
    python scripts/generate_openapi.py [--output openapi.json]

This script generates the OpenAPI 3.0 specification from the FastAPI app
and saves it to a JSON file. Useful for:
- Publishing to GitHub Pages
- API documentation versioning
- Integration with API gateways
- Client code generation
"""

import json
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app


def generate_openapi(output_path: str = "openapi.json"):
    """Generate OpenAPI spec and save to file."""
    openapi = app.openapi()
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(openapi, f, indent=2, ensure_ascii=False)
    
    print(f"✅ OpenAPI specification generated: {output_path}")
    print(f"   API Title: {openapi.get('info', {}).get('title', 'Unknown')}")
    print(f"   API Version: {openapi.get('info', {}).get('version', 'Unknown')}")
    print(f"   Endpoints: {len(openapi.get('paths', {}))}")
    
    return openapi


def main():
    parser = argparse.ArgumentParser(description='Generate OpenAPI specification')
    parser.add_argument(
        '--output', '-o',
        default='openapi.json',
        help='Output file path (default: openapi.json)'
    )
    parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        help='Pretty print JSON output'
    )
    
    args = parser.parse_args()
    
    try:
        generate_openapi(args.output)
    except Exception as e:
        print(f"❌ Error generating OpenAPI spec: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()