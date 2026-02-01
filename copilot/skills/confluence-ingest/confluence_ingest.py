#!/usr/bin/env python3
"""
Confluence Page Ingester
Fetches Confluence pages by ID and downloads all attachments including draw.io diagrams.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Auto-load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in current dir or parent dirs
    env_path = Path('.env')
    if not env_path.exists():
        # Try workspace root (for when running from skill folder)
        for parent in Path.cwd().parents:
            candidate = parent / '.env'
            if candidate.exists():
                env_path = candidate
                break
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

try:
    from atlassian import Confluence
    HAS_ATLASSIAN = True
except ImportError:
    HAS_ATLASSIAN = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def get_confluence_client() -> Optional[Confluence]:
    """Create Confluence client from environment variables using PAT authentication."""
    url = os.environ.get("CONFLUENCE_URL")
    token = os.environ.get("CONFLUENCE_API_TOKEN")
    
    if not url or not token:
        missing = []
        if not url:
            missing.append("CONFLUENCE_URL")
        if not token:
            missing.append("CONFLUENCE_API_TOKEN")
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set these variables or add them to .env file", file=sys.stderr)
        return None
    
    return Confluence(url=url, token=token)


def html_to_markdown(html_content: str) -> str:
    """Convert Confluence HTML content to Markdown."""
    if not html_content:
        return ""
    
    if not HAS_BS4:
        # Basic fallback without BeautifulSoup
        text = re.sub(r'<br\s*/?>', '\n', html_content)
        text = re.sub(r'<p[^>]*>', '\n\n', text)
        text = re.sub(r'</p>', '', text)
        text = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: '#' * int(m.group(1)) + ' ' + m.group(2) + '\n', text)
        text = re.sub(r'<li[^>]*>', '- ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove Confluence-specific elements
    for element in soup.select('.confluence-embedded-file-wrapper, .expand-control'):
        element.decompose()
    
    def process_element(element, depth=0):
        """Recursively process HTML elements to Markdown."""
        if element.name is None:
            return str(element).strip()
        
        if element.name in ['script', 'style']:
            return ''
        
        if element.name == 'h1':
            return f"# {element.get_text().strip()}\n\n"
        if element.name == 'h2':
            return f"## {element.get_text().strip()}\n\n"
        if element.name == 'h3':
            return f"### {element.get_text().strip()}\n\n"
        if element.name == 'h4':
            return f"#### {element.get_text().strip()}\n\n"
        if element.name == 'h5':
            return f"##### {element.get_text().strip()}\n\n"
        if element.name == 'h6':
            return f"###### {element.get_text().strip()}\n\n"
        
        if element.name == 'p':
            text = element.get_text().strip()
            return f"{text}\n\n" if text else ""
        
        if element.name == 'br':
            return "\n"
        
        if element.name == 'strong' or element.name == 'b':
            return f"**{element.get_text().strip()}**"
        
        if element.name == 'em' or element.name == 'i':
            return f"*{element.get_text().strip()}*"
        
        if element.name == 'code':
            return f"`{element.get_text()}`"
        
        if element.name == 'pre':
            code = element.get_text()
            return f"```\n{code}\n```\n\n"
        
        if element.name == 'a':
            href = element.get('href', '')
            text = element.get_text().strip()
            return f"[{text}]({href})"
        
        if element.name == 'ul':
            items = []
            for li in element.find_all('li', recursive=False):
                items.append(f"- {li.get_text().strip()}")
            return '\n'.join(items) + '\n\n'
        
        if element.name == 'ol':
            items = []
            for i, li in enumerate(element.find_all('li', recursive=False), 1):
                items.append(f"{i}. {li.get_text().strip()}")
            return '\n'.join(items) + '\n\n'
        
        if element.name == 'table':
            return process_table(element)
        
        if element.name == 'img':
            alt = element.get('alt', 'image')
            src = element.get('src', '')
            return f"![{alt}]({src})"
        
        if element.name == 'blockquote':
            text = element.get_text().strip()
            lines = text.split('\n')
            return '\n'.join(f"> {line}" for line in lines) + '\n\n'
        
        # Default: process children
        result = []
        for child in element.children:
            if hasattr(child, 'name'):
                result.append(process_element(child, depth + 1))
            elif str(child).strip():
                result.append(str(child).strip())
        return ' '.join(result)
    
    def process_table(table):
        """Convert HTML table to Markdown table."""
        rows = []
        headers = []
        
        # Find headers
        thead = table.find('thead')
        if thead:
            for th in thead.find_all('th'):
                headers.append(th.get_text().strip())
        
        # Find body rows
        tbody = table.find('tbody') or table
        for tr in tbody.find_all('tr'):
            cells = []
            for td in tr.find_all(['td', 'th']):
                cells.append(td.get_text().strip().replace('|', '\\|'))
            if cells:
                if not headers and tr.find('th'):
                    headers = cells
                else:
                    rows.append(cells)
        
        if not headers and rows:
            headers = rows.pop(0)
        
        if not headers:
            return ""
        
        # Build markdown table
        md = []
        md.append('| ' + ' | '.join(headers) + ' |')
        md.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in rows:
            # Pad row if needed
            while len(row) < len(headers):
                row.append('')
            md.append('| ' + ' | '.join(row[:len(headers)]) + ' |')
        
        return '\n'.join(md) + '\n\n'
    
    # Process the content
    body = soup.find('body') or soup
    markdown = process_element(body)
    
    # Clean up
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    return markdown.strip()


def get_file_category(filename: str) -> tuple:
    """Categorize file by extension. Returns (category, emoji)."""
    lower = filename.lower()
    if lower.endswith('.drawio'):
        return 'diagram', '📊'
    elif lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
        return 'image', '🖼️'
    elif lower.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
        return 'document', '📄'
    else:
        return 'other', '📎'


def download_attachments(confluence: Confluence, page_id: str, output_dir: Path) -> list:
    """Download all attachments from a Confluence page to attachments folder."""
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded = []
    start = 0
    limit = 50  # Confluence API pagination
    
    try:
        while True:
            # Get attachments with pagination
            attachments = confluence.get_attachments_from_content(
                page_id, 
                start=start, 
                limit=limit
            )
            results = attachments.get('results', [])
            
            if not results:
                if start == 0:
                    print("No attachments found on this page.", file=sys.stderr)
                break
            
            if start == 0:
                total = attachments.get('size', len(results))
                print(f"Found {total} attachment(s)", file=sys.stderr)
            
            for attachment in results:
                title = attachment.get('title', 'unknown')
                download_link = attachment.get('_links', {}).get('download', '')
                media_type = attachment.get('metadata', {}).get('mediaType', '')
                
                if not download_link:
                    print(f"  ⚠ Skipping {title}: no download link", file=sys.stderr)
                    continue
                
                category, emoji = get_file_category(title)
                output_path = attachments_dir / title
                
                try:
                    content = confluence.get(download_link, not_json_response=True)
                    with open(output_path, 'wb') as f:
                        f.write(content)
                    
                    print(f"  {emoji} Downloaded: {title}", file=sys.stderr)
                    
                    downloaded.append({
                        'filename': title,
                        'path': str(output_path),
                        'size': len(content),
                        'category': category,
                        'media_type': media_type,
                        'is_drawio': title.lower().endswith('.drawio'),
                        'is_image': category == 'image'
                    })
                except Exception as e:
                    print(f"  ❌ Failed to download {title}: {e}", file=sys.stderr)
            
            # Check for more pages
            if len(results) < limit:
                break
            start += limit
    
    except Exception as e:
        print(f"Error fetching attachments: {e}", file=sys.stderr)
    
    # Print summary by category
    if downloaded:
        images = [d for d in downloaded if d['category'] == 'image']
        diagrams = [d for d in downloaded if d['category'] == 'diagram']
        docs = [d for d in downloaded if d['category'] == 'document']
        others = [d for d in downloaded if d['category'] == 'other']
        
        print(f"\nDownload summary:", file=sys.stderr)
        if images:
            print(f"  🖼️  Images: {len(images)}", file=sys.stderr)
        if diagrams:
            print(f"  📊 Diagrams: {len(diagrams)}", file=sys.stderr)
        if docs:
            print(f"  📄 Documents: {len(docs)}", file=sys.stderr)
        if others:
            print(f"  📎 Other: {len(others)}", file=sys.stderr)
    
    return downloaded


def fetch_child_pages(confluence: Confluence, page_id: str) -> list:
    """Get list of child pages."""
    try:
        children = confluence.get_page_child_by_type(page_id, type='page')
        return [
            {
                'id': child['id'],
                'title': child['title']
            }
            for child in children
        ]
    except Exception as e:
        print(f"Error fetching child pages: {e}", file=sys.stderr)
        return []


def ingest_page(page_id: str, include_children: bool = False, 
                skip_attachments: bool = False) -> dict:
    """Ingest a Confluence page and its attachments."""
    
    if not HAS_ATLASSIAN:
        print("Error: atlassian-python-api not installed.", file=sys.stderr)
        print("Install with: pip install atlassian-python-api", file=sys.stderr)
        sys.exit(1)
    
    confluence = get_confluence_client()
    if not confluence:
        sys.exit(1)
    
    # Output to governance/output/<page_id>/
    output_dir = Path("governance/output") / page_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching page {page_id}...", file=sys.stderr)
    
    try:
        # Get page content with body
        page = confluence.get_page_by_id(
            page_id,
            expand='body.storage,version,space,ancestors'
        )
    except Exception as e:
        print(f"Error fetching page: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract metadata
    metadata = {
        'id': page.get('id'),
        'title': page.get('title'),
        'space': page.get('space', {}).get('key'),
        'space_name': page.get('space', {}).get('name'),
        'version': page.get('version', {}).get('number'),
        'created_by': page.get('version', {}).get('by', {}).get('displayName'),
        'last_modified': page.get('version', {}).get('when'),
        'url': page.get('_links', {}).get('webui', ''),
        'ingested_at': datetime.now().isoformat()
    }
    
    # Get ancestors (breadcrumb)
    ancestors = page.get('ancestors', [])
    metadata['ancestors'] = [
        {'id': a.get('id'), 'title': a.get('title')} 
        for a in ancestors
    ]
    
    print(f"Page: {metadata['title']}", file=sys.stderr)
    print(f"Space: {metadata['space_name']} ({metadata['space']})", file=sys.stderr)
    
    # Convert HTML body to Markdown
    html_body = page.get('body', {}).get('storage', {}).get('value', '')
    markdown_content = html_to_markdown(html_body)
    
    # Build output Markdown
    md_output = []
    md_output.append(f"# {metadata['title']}")
    md_output.append("")
    md_output.append(f"**Source**: Confluence - {metadata['space_name']}")
    md_output.append(f"**Page ID**: {metadata['id']}")
    md_output.append(f"**Last Modified**: {metadata['last_modified']}")
    md_output.append(f"**Ingested**: {metadata['ingested_at']}")
    md_output.append("")
    md_output.append("---")
    md_output.append("")
    md_output.append(markdown_content)
    
    # Save Markdown
    md_path = output_dir / "page.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_output))
    print(f"✅ Saved page content to {md_path}", file=sys.stderr)
    
    # Save metadata
    meta_path = output_dir / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Saved metadata to {meta_path}", file=sys.stderr)
    
    # Download attachments
    attachments = []
    if not skip_attachments:
        print("\nDownloading attachments...", file=sys.stderr)
        attachments = download_attachments(confluence, page_id, output_dir)
        metadata['attachments'] = attachments
        
        # Update metadata with attachments info
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
    
    # Get child pages
    children = []
    if include_children:
        print("\nFetching child pages...", file=sys.stderr)
        children = fetch_child_pages(confluence, page_id)
        if children:
            print(f"Found {len(children)} child page(s):", file=sys.stderr)
            for child in children:
                print(f"  • {child['title']} (ID: {child['id']})", file=sys.stderr)
            metadata['children'] = children
            
            # Update metadata with children
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
    
    # Report draw.io diagrams for conversion
    drawio_files = [a for a in attachments if a.get('is_drawio')]
    if drawio_files:
        print("\n📊 Draw.io diagrams found - convert with:", file=sys.stderr)
        for d in drawio_files:
            print(f"   python copilot/skills/drawio-to-mermaid/drawio_to_mermaid.py \\", file=sys.stderr)
            print(f"       --input {d['path']} \\", file=sys.stderr)
            stem = Path(d['filename']).stem
            print(f"       --output {output_dir}/{stem}.mermaid.md", file=sys.stderr)
    
    return {
        'metadata': metadata,
        'markdown_path': str(md_path),
        'attachments': attachments,
        'children': children
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Confluence pages and attachments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  CONFLUENCE_URL        Your Confluence instance URL
  CONFLUENCE_API_TOKEN  Personal Access Token (PAT)

Example:
  export CONFLUENCE_URL="https://company.atlassian.net"
  export CONFLUENCE_API_TOKEN="your-personal-access-token"
  
  python confluence_ingest.py --page-id 123456789
        """
    )
    parser.add_argument(
        "--page-id", "-p",
        required=True,
        help="Confluence page ID to ingest"
    )
    parser.add_argument(
        "--include-children",
        action="store_true",
        help="Also list child pages (doesn't download them)"
    )
    parser.add_argument(
        "--skip-attachments",
        action="store_true",
        help="Skip downloading attachments"
    )
    
    args = parser.parse_args()
    
    result = ingest_page(
        page_id=args.page_id,
        include_children=args.include_children,
        skip_attachments=args.skip_attachments
    )
    
    print("\n✅ Ingestion complete!", file=sys.stderr)
    print(f"   Markdown: {result['markdown_path']}", file=sys.stderr)
    print(f"   Attachments: {len(result['attachments'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
