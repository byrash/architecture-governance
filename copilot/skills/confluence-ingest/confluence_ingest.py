#!/usr/bin/env python3
"""
Confluence Page Ingester
Fetches Confluence pages by ID, downloads all attachments, converts diagrams to Mermaid,
and produces a self-contained Markdown file.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Auto-load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in current dir or parent dirs
    env_path = Path('.env')
    if not env_path.exists():
        for parent in Path.cwd().parents:
            candidate = parent / '.env'
            if candidate.exists():
                env_path = candidate
                break
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

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

try:
    import markdownify
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False


def get_confluence_client() -> Optional[Confluence]:
    """Create Confluence client using PAT authentication."""
    url = os.environ.get("CONFLUENCE_URL")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("CONFLUENCE_TOKEN")
    
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


def get_file_category(filename: str) -> Tuple[str, str]:
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


def is_drawio_file(filepath: str) -> bool:
    """Check if file is a Draw.io diagram by extension or content."""
    if filepath.lower().endswith('.drawio'):
        return True
    
    # Check file content for Draw.io markers
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            first_chunk = f.read(500)
            if '<mxfile' in first_chunk or '<mxGraphModel' in first_chunk:
                return True
    except Exception:
        pass
    
    return False


def download_attachments(confluence: Confluence, page_id: str, download_dir: Path) -> Tuple[Dict[str, str], List[str]]:
    """
    Download all attachments from a Confluence page (latest version only).
    Returns (attachment_map, drawio_files) where:
      - attachment_map: filename -> local path mapping
      - drawio_files: list of Draw.io filenames
    """
    attachment_map = {}
    drawio_files = []
    
    print("Downloading attachments...", file=sys.stderr)
    
    try:
        attachments = confluence.get_attachments_from_content(page_id)
        results = attachments.get('results', [])
        
        if not results:
            print("No attachments found on this page.", file=sys.stderr)
            return attachment_map, drawio_files
        
        # Group by filename and keep only latest version
        # Skip backup files and unnecessary file types
        latest_attachments = {}
        skipped_files = {'backup': 0, 'unnecessary': 0}
        
        # File extensions we actually need (diagrams and images for Mermaid conversion)
        needed_extensions = {'.drawio', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
        
        for attachment in results:
            filename = attachment.get('title', 'unknown')
            lower_filename = filename.lower()
            
            # Skip backup and temp files
            if filename.startswith('drawio-backup-') or filename.startswith('tmp') or filename.startswith('~'):
                skipped_files['backup'] += 1
                continue
            
            # Skip unnecessary file types (PDFs, docs, spreadsheets, etc.)
            file_ext = Path(filename).suffix.lower()
            # Also check if it might be a drawio without extension (will check content later)
            has_needed_ext = file_ext in needed_extensions or file_ext == ''
            
            if not has_needed_ext:
                skipped_files['unnecessary'] += 1
                print(f"  ⏭️  Skipping (not needed): {filename}", file=sys.stderr)
                continue
            
            version = attachment.get('version', {}).get('number', 1)
            
            if filename not in latest_attachments or version > latest_attachments[filename]['version']:
                latest_attachments[filename] = {
                    'attachment': attachment,
                    'version': version
                }
        
        if skipped_files['backup'] > 0:
            print(f"Skipped {skipped_files['backup']} backup/temp file(s)", file=sys.stderr)
        if skipped_files['unnecessary'] > 0:
            print(f"Skipped {skipped_files['unnecessary']} unnecessary file(s) (PDFs, docs, etc.)", file=sys.stderr)
        
        print(f"Found {len(latest_attachments)} unique attachment(s) (filtered from {len(results)} total versions)", file=sys.stderr)
        
        for filename, data in latest_attachments.items():
            attachment = data['attachment']
            version = data['version']
            _, emoji = get_file_category(filename)
            filepath = download_dir / filename
            
            try:
                # Skip if already downloaded (avoid re-downloading)
                if filepath.exists():
                    print(f"  {emoji} Already exists: {filename} (v{version})", file=sys.stderr)
                    attachment_map[filename] = filename
                    if is_drawio_file(str(filepath)):
                        drawio_files.append(filename)
                    continue
                
                # Use native SDK method for download
                confluence.download_attachments_from_page(
                    page_id, path=str(download_dir), filename=filename
                )
                
                # Verify the file was actually downloaded - check for exact name and tmp variants
                actual_file = None
                if filepath.exists():
                    actual_file = filepath
                else:
                    # SDK may save with different names - scan directory for recent files
                    for f in download_dir.iterdir():
                        # Check for temp file variants or files containing the base name
                        base_name = Path(filename).stem
                        if f.name == filename or base_name in f.name:
                            actual_file = f
                            break
                        # Also check for tmp files that might be draw.io content
                        if f.name.startswith('tmp') and is_drawio_file(str(f)):
                            # Rename tmp file to expected name
                            new_path = download_dir / filename
                            f.rename(new_path)
                            actual_file = new_path
                            print(f"  📝 Renamed temp file to: {filename}", file=sys.stderr)
                            break
                
                if actual_file and actual_file.exists():
                    # Check if it's a Draw.io file (by extension or content)
                    is_drawio = is_drawio_file(str(actual_file))
                    
                    # If it's a drawio file but missing .drawio extension, rename it
                    final_filename = filename
                    if is_drawio and not filename.lower().endswith('.drawio'):
                        new_filename = filename + '.drawio'
                        new_path = download_dir / new_filename
                        actual_file.rename(new_path)
                        actual_file = new_path
                        final_filename = new_filename
                        print(f"  📝 Added .drawio extension: {filename} → {new_filename}", file=sys.stderr)
                    
                    attachment_map[final_filename] = final_filename  # Store relative path
                    
                    if is_drawio:
                        drawio_files.append(final_filename)
                        print(f"  {emoji} Downloaded (Draw.io): {final_filename} (v{version})", file=sys.stderr)
                    else:
                        print(f"  {emoji} Downloaded: {final_filename} (v{version})", file=sys.stderr)
                else:
                    print(f"  ⚠ Downloaded but file not found at expected path: {filename}", file=sys.stderr)
                    
            except Exception as e:
                print(f"  ❌ Failed to download {filename}: {e}", file=sys.stderr)
    
    except Exception as e:
        print(f"Error fetching attachments: {e}", file=sys.stderr)
    
    # Final scan: check for any .drawio files we may have missed
    # Skip backup files in final scan too
    for f in download_dir.iterdir():
        # Skip backup and temp files
        if f.name.startswith('drawio-backup-') or f.name.startswith('tmp') or f.name.startswith('~'):
            continue
        if is_drawio_file(str(f)) and f.name not in drawio_files:
            final_name = f.name
            # Add .drawio extension if missing
            if not f.name.lower().endswith('.drawio'):
                new_name = f.name + '.drawio'
                new_path = download_dir / new_name
                f.rename(new_path)
                final_name = new_name
                print(f"  📝 Added .drawio extension: {f.name} → {new_name}", file=sys.stderr)
            
            drawio_files.append(final_name)
            if final_name not in attachment_map:
                attachment_map[final_name] = final_name
            print(f"  📊 Found additional Draw.io file: {final_name}", file=sys.stderr)
    
    return attachment_map, drawio_files


def extract_drawio_diagrams(html: str, confluence: Confluence,
                            download_dir: Path, attachment_map: Dict[str, str]) -> Dict[str, str]:
    """
    Extract drawio diagram metadata and map to .drawio files or PNG previews.
    Returns dict mapping macro_id -> local filename (prioritizes .drawio files).
    Also extracts embedded diagram data and saves as .drawio files.
    """
    diagram_map = {}
    
    # Find all drawio-macro-data divs with base64 metadata
    data_divs = re.findall(
        r'<div[^>]*id="drawio-macro-data-([^"]+)"[^>]*style="display:none"[^>]*>([^<]+)</div>',
        html, re.IGNORECASE
    )
    
    if data_divs:
        print(f"\n📊 DRAW.IO DETECTION: Found {len(data_divs)} Draw.io macro(s) in page HTML", file=sys.stderr)
    
    # Get list of all .drawio files from attachments
    drawio_attachments = [f for f in attachment_map.keys() if f.lower().endswith('.drawio')]
    
    for macro_id, base64_data in data_divs:
        try:
            # Decode the base64 metadata
            decoded = base64.b64decode(base64_data).decode('utf-8')
            metadata = json.loads(decoded)
            
            # Look for template image URL (PNG preview)
            template_image_url = metadata.get('templateImageLoadUrl', '')
            template_url = metadata.get('templateUrl', '')
            diagram_name = template_url.split('/')[-1] if template_url else f"diagram_{macro_id}"
            
            # Clean up diagram name
            diagram_name = re.sub(r'[^\w\-_.]', '_', diagram_name)
            
            # PRIORITY 1: Check if we have the actual .drawio file in attachments
            drawio_found = False
            
            # First try exact match by name
            for filename in drawio_attachments:
                base_name = Path(filename).stem.lower()
                check_name = diagram_name.lower()
                if base_name == check_name or check_name in base_name or base_name in check_name:
                    diagram_map[macro_id] = filename
                    print(f"   ✓ Macro {macro_id[:8]}... → {filename}", file=sys.stderr)
                    drawio_found = True
                    break
            
            # If only one drawio file and one diagram, assume they match
            if not drawio_found and len(drawio_attachments) == 1 and len(data_divs) == 1:
                filename = drawio_attachments[0]
                diagram_map[macro_id] = filename
                print(f"   ✓ Macro {macro_id[:8]}... → {filename} (single match)", file=sys.stderr)
                drawio_found = True
            
            # If still not found, try to use any unmatched .drawio file
            if not drawio_found:
                for filename in drawio_attachments:
                    if filename not in diagram_map.values():
                        diagram_map[macro_id] = filename
                        print(f"   ✓ Macro {macro_id[:8]}... → {filename} (available)", file=sys.stderr)
                        drawio_found = True
                        break
            
            if drawio_found:
                continue
            
            # PRIORITY 2: Try to download the actual .drawio file from diagramUrl
            diagram_url = metadata.get('diagramUrl', '') or metadata.get('templateUrl', '')
            if diagram_url and '.drawio' in diagram_url:
                try:
                    drawio_filename = f"{diagram_name}.drawio"
                    drawio_path = download_dir / drawio_filename
                    full_url = diagram_url if diagram_url.startswith('http') else f"{confluence.url}{diagram_url}"
                    
                    response = confluence._session.get(full_url)
                    if response.status_code == 200 and len(response.content) > 0:
                        with open(drawio_path, 'wb') as f:
                            f.write(response.content)
                        diagram_map[macro_id] = drawio_filename
                        attachment_map[drawio_filename] = drawio_filename
                        print(f"  ✓ Downloaded .drawio file: {drawio_filename}", file=sys.stderr)
                        continue
                except Exception as e:
                    print(f"  ⚠ Failed to download .drawio: {e}", file=sys.stderr)
            
            # PRIORITY 3: Try to download the PNG preview if no .drawio file found
            if template_image_url:
                try:
                    png_filename = f"{diagram_name}.png"
                    png_path = download_dir / png_filename
                    full_url = template_image_url if template_image_url.startswith('http') else f"{confluence.url}{template_image_url}"
                    
                    # Try using confluence client's session
                    response = confluence._session.get(full_url)
                    if response.status_code == 200 and len(response.content) > 0:
                        with open(png_path, 'wb') as f:
                            f.write(response.content)
                        diagram_map[macro_id] = png_filename
                        attachment_map[png_filename] = png_filename
                        print(f"  ✓ Downloaded PNG preview: {png_filename}", file=sys.stderr)
                except Exception as e:
                    print(f"  ⚠ Failed to download preview: {e}", file=sys.stderr)
        
        except Exception as e:
            print(f"  ⚠ Failed to parse diagram {macro_id}: {e}", file=sys.stderr)
    
    # Handle case where we have .drawio attachments but no macro data blocks
    # (diagrams uploaded as attachments but not embedded via macro)
    if not data_divs and drawio_attachments:
        print(f"\n📊 DRAW.IO DETECTION: Found {len(drawio_attachments)} .drawio file(s) as attachments (not embedded)", file=sys.stderr)
        for f in drawio_attachments:
            print(f"   → {f}", file=sys.stderr)
    
    return diagram_map


def replace_drawio_with_images(html: str, diagram_map: Dict[str, str], 
                                attachment_map: Dict[str, str]) -> str:
    """Replace empty drawio-macro divs with actual img tags."""
    if not HAS_BS4:
        return html
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all drawio-macro containers
    for macro_div in soup.find_all('div', class_='drawio-macro'):
        macro_id = macro_div.get('data-macroid', '')
        
        if macro_id in diagram_map:
            img = soup.new_tag('img')
            img['src'] = diagram_map[macro_id]
            img['alt'] = f"Diagram {macro_id}"
            img['style'] = "max-width: 100%; height: auto;"
            macro_div.clear()
            macro_div.append(img)
        else:
            # Check if there's an attachment that might be the diagram
            found_attachment = None
            for att_name in attachment_map:
                if macro_id in att_name or att_name.endswith('.drawio') or 'diagram' in att_name.lower():
                    found_attachment = att_name
                    break
            
            if found_attachment and found_attachment.lower().endswith(('.png', '.jpg', '.svg')):
                img = soup.new_tag('img')
                img['src'] = found_attachment
                img['alt'] = "Diagram"
                img['style'] = "max-width: 100%; height: auto;"
                macro_div.clear()
                macro_div.append(img)
            else:
                # Add a placeholder message
                placeholder = soup.new_tag('div')
                placeholder['style'] = "border: 2px dashed #ccc; padding: 40px; text-align: center; color: #666; background: #f9f9f9; margin: 10px 0;"
                placeholder.string = "📊 [Diagram Template - Edit in Confluence to add content]"
                macro_div.clear()
                macro_div.append(placeholder)
    
    # Remove the hidden data divs
    for data_div in soup.find_all('div', id=re.compile(r'drawio-macro-data-')):
        data_div.decompose()
    
    return str(soup)


def extract_and_embed_images(storage_html: str, view_html: str, 
                             attachment_map: Dict[str, str]) -> str:
    """
    Extract image references from storage format and embed local images in view HTML.
    Replaces Confluence image URLs with local attachment paths.
    """
    if not HAS_BS4:
        return view_html
    
    soup = BeautifulSoup(view_html, 'html.parser')
    
    # Process all img tags - replace Confluence URLs with local paths
    for img in soup.find_all('img'):
        src = img.get('src', '')
        data_src = img.get('data-image-src', '')
        
        for attr_value in [src, data_src]:
            if attr_value:
                for filename in attachment_map:
                    filename_patterns = [
                        filename,
                        filename.replace(' ', '%20'),
                        filename.replace(' ', '+'),
                    ]
                    for pattern in filename_patterns:
                        if pattern in attr_value:
                            img['src'] = filename
                            break
    
    # Handle span.confluence-embedded-file-wrapper
    for wrapper in soup.find_all('span', class_='confluence-embedded-file-wrapper'):
        img = wrapper.find('img')
        if img:
            src = img.get('src', '') or img.get('data-image-src', '')
            for filename in attachment_map:
                if filename in src or filename.replace(' ', '%20') in src:
                    img['src'] = filename
                    break
    
    return str(soup)


def process_confluence_tabs(html: str) -> str:
    """
    Convert Confluence tabs macro to flat HTML sections.
    Makes all tab content visible with section headers.
    """
    if not HAS_BS4:
        return html
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all auitabs containers
    tabs_containers = soup.find_all('div', class_='aui-tabs')
    
    if tabs_containers:
        print(f"Processing {len(tabs_containers)} tab container(s)...", file=sys.stderr)
    
    for container in tabs_containers:
        # Remove the tabs-menu (clickable headers)
        tabs_menu = container.find('ul', class_='tabs-menu')
        if tabs_menu:
            tabs_menu.decompose()
        
        # Find all tab panes and make them visible with headers
        tab_panes = container.find_all('div', class_='tabs-pane')
        
        for pane in tab_panes:
            title = pane.get('data-pane-title', 'Tab Content')
            
            # Remove display:none style
            if pane.has_attr('style'):
                style = pane['style']
                style = style.replace('display: none;', '')
                style = style.replace('display:none;', '')
                pane['style'] = style
            
            # Remove unnecessary attributes
            for attr in ['jwtdata', 'data-hasbody', 'data-macro-name', 'role']:
                if pane.has_attr(attr):
                    del pane[attr]
            
            # Create a header for this tab section
            header = soup.new_tag('h3')
            header.string = f"📑 {title}"
            header['class'] = 'tab-section-header'
            header['style'] = "background-color: #f0f0f0; padding: 10px; margin-top: 20px; border-left: 4px solid #0052cc;"
            
            pane.insert(0, header)
            pane['class'] = pane.get('class', []) + ['tab-section-visible']
            pane['style'] = "display: block; border: 1px solid #ddd; padding: 15px; margin-bottom: 20px;"
    
    # Remove jwtdata from any other elements
    for elem in soup.find_all(attrs={'jwtdata': True}):
        del elem['jwtdata']
    
    # Remove lazy-loading-div placeholders
    for lazy_div in soup.find_all('div', class_='lazy-loading-div'):
        lazy_div.decompose()
    
    return str(soup)


def convert_html_to_markdown(html_content: str, attachment_map: Dict[str, str]) -> str:
    """Convert HTML to Markdown using markdownify or fallback."""
    if HAS_MARKDOWNIFY:
        md_content = markdownify.markdownify(html_content, heading_style="ATX", bullets="-")
    else:
        # Basic fallback conversion
        md_content = html_content
        md_content = re.sub(r'<br\s*/?>', '\n', md_content)
        md_content = re.sub(r'<p[^>]*>', '\n\n', md_content)
        md_content = re.sub(r'</p>', '', md_content)
        md_content = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', 
                           lambda m: '#' * int(m.group(1)) + ' ' + m.group(2) + '\n', md_content)
        md_content = re.sub(r'<li[^>]*>', '- ', md_content)
        md_content = re.sub(r'<[^>]+>', '', md_content)
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
    
    # Fix remaining Confluence image references in markdown
    for filename in attachment_map:
        md_content = re.sub(
            rf"!\[([^\]]*)\]\([^)]*?{re.escape(filename)}[^)]*?\)",
            rf"![\1]({filename})",
            md_content, flags=re.IGNORECASE
        )
    
    return md_content.strip()


def convert_drawio_to_mermaid(drawio_path: Path) -> Optional[str]:
    """Convert a Draw.io file to Mermaid using the local drawio_to_mermaid script."""
    # Try to find the conversion script - check multiple possible locations
    script_dir = Path(__file__).parent
    workspace_root = Path.cwd()
    
    script_paths = [
        script_dir / 'drawio_to_mermaid.py',  # Same directory as this script
        Path('.github/skills/confluence-ingest/drawio_to_mermaid.py'),
        Path('copilot/skills/confluence-ingest/drawio_to_mermaid.py'),
        Path('governance/scripts/drawio_to_mermaid.py'),  # Legacy path
        workspace_root / '.github/skills/confluence-ingest/drawio_to_mermaid.py',
        workspace_root / 'copilot/skills/confluence-ingest/drawio_to_mermaid.py',
    ]
    
    script_path = None
    for p in script_paths:
        if p.exists():
            script_path = p
            print(f"  📍 Using conversion script: {script_path}", file=sys.stderr)
            break
    
    if not script_path:
        print("  ⚠ drawio_to_mermaid.py script not found in any of these locations:", file=sys.stderr)
        for p in script_paths[:4]:
            print(f"     - {p}", file=sys.stderr)
        return None
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), '--input', str(drawio_path)],
            capture_output=True, text=True, check=True,
            timeout=30  # Add timeout to prevent hanging
        )
        if result.stdout:
            return result.stdout.strip()
        else:
            print(f"  ⚠ No output from conversion script", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  ✗ Conversion timed out after 30 seconds", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Conversion failed: {e.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"  ✗ Error: {e}", file=sys.stderr)
    
    return None


def inline_mermaid_diagrams(md_content: str, diagram_mermaid_map: Dict[str, str]) -> str:
    """Replace image references with Mermaid code blocks inline."""
    for filename, mermaid_code in diagram_mermaid_map.items():
        # Match both formats: ![alt](path/file.png) and ![alt](file.png)
        pattern = rf"!\[[^\]]*\]\([^)]*{re.escape(filename)}\)"
        if re.search(pattern, md_content):
            md_content = re.sub(pattern, f"\n{mermaid_code}\n", md_content, count=1)
            print(f"  ✓ Replaced {filename} with Mermaid", file=sys.stderr)
    
    return md_content


def fix_image_paths(md_content: str, attachments_folder: str, attachment_map: Dict[str, str]) -> str:
    """Fix image references to include the attachments folder prefix and convert Confluence URLs."""
    
    # First, fix Confluence download URLs: /download/attachments/PAGE_ID/filename.png?version=...
    # Pattern: ![alt](/download/attachments/123/file.png?...) -> ![alt](attachments/file.png)
    def replace_confluence_url(match):
        alt_text = match.group(1)
        url_path = match.group(2)
        
        # Extract filename from URL (before query params)
        filename_match = re.search(r'/([^/?]+)\.(png|jpg|jpeg|gif|svg|drawio)(?:\?|$)', url_path, re.IGNORECASE)
        if filename_match:
            filename = f"{filename_match.group(1)}.{filename_match.group(2)}"
            # Check if this file exists in our attachments
            if filename in attachment_map:
                return f"![{alt_text}]({attachments_folder}/{filename})"
            # Try case-insensitive match
            for att_name in attachment_map:
                if att_name.lower() == filename.lower():
                    return f"![{alt_text}]({attachments_folder}/{att_name})"
        
        # Return original if no match found
        return match.group(0)
    
    # Match Confluence download URLs
    md_content = re.sub(
        r'!\[([^\]]*)\]\((/download/attachments/[^)]+)\)',
        replace_confluence_url,
        md_content, flags=re.IGNORECASE
    )
    
    # Also handle full Confluence URLs with domain
    md_content = re.sub(
        r'!\[([^\]]*)\]\((https?://[^/]+/download/attachments/[^)]+)\)',
        replace_confluence_url,
        md_content, flags=re.IGNORECASE
    )
    
    # Fix simple filenames: ![anything](filename.ext) -> ![anything](attachments_folder/filename.ext)
    # Skip if already has the attachments prefix
    md_content = re.sub(
        rf"!\[([^\]]*)\]\((?!{re.escape(attachments_folder)}/)(?!/download/)([^/)][^)]*\.(png|jpg|jpeg|gif|svg|drawio))\)",
        rf"![\1]({attachments_folder}/\2)",
        md_content, flags=re.IGNORECASE
    )
    
    return md_content


def ingest_page(page_id: str, output_dir: str = "governance/output",
                convert_diagrams: bool = True, mode: str = "governance") -> dict:
    """
    Ingest a Confluence page and produce a self-contained Markdown file.
    
    Args:
        page_id: Confluence page ID
        output_dir: Base output directory
        convert_diagrams: Whether to convert Draw.io diagrams to Mermaid
        mode: 'governance' or 'index' mode
    
    Returns:
        Dict with metadata, paths, and attachments info
    """
    if not HAS_ATLASSIAN:
        print("Error: atlassian-python-api not installed.", file=sys.stderr)
        print("Install with: pip install atlassian-python-api", file=sys.stderr)
        sys.exit(1)
    
    confluence = get_confluence_client()
    if not confluence:
        sys.exit(1)
    
    # Create output directories: governance/output/<PAGE_ID>/
    output_base = Path(output_dir)
    page_dir = output_base / page_id
    download_dir = page_dir / "attachments"
    
    # Clean up existing output if it exists (fresh ingestion)
    cleaned_items = []
    
    # Remove page folder
    if page_dir.exists():
        try:
            shutil.rmtree(page_dir)
            cleaned_items.append(f"{page_id}/")
        except Exception as e:
            print(f"   ⚠ Could not remove {page_dir}: {e}", file=sys.stderr)
    
    # Remove associated report files
    report_patterns = [
        f"{page_id}-patterns-report.md",
        f"{page_id}-standards-report.md",
        f"{page_id}-security-report.md",
        f"{page_id}-governance-report.md",
        f"{page_id}-governance-report.html",
    ]
    
    for report_name in report_patterns:
        report_path = output_base / report_name
        if report_path.exists():
            try:
                report_path.unlink()
                cleaned_items.append(report_name)
            except Exception as e:
                print(f"   ⚠ Could not remove {report_name}: {e}", file=sys.stderr)
    
    if cleaned_items:
        print(f"🧹 Cleaned existing output:", file=sys.stderr)
        for item in cleaned_items:
            print(f"   ✓ {item}", file=sys.stderr)
    
    download_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch page content
    print(f"Fetching page {page_id}...", file=sys.stderr)
    
    try:
        page = confluence.get_page_by_id(page_id, expand='body.storage,body.view,version,space,ancestors')
    except Exception as e:
        print(f"Error fetching page: {e}", file=sys.stderr)
        sys.exit(1)
    
    title = page.get('title', 'Untitled')
    print(f"Page: {title}", file=sys.stderr)
    
    # Extract metadata
    metadata = {
        'id': page.get('id'),
        'title': title,
        'space': page.get('space', {}).get('key'),
        'space_name': page.get('space', {}).get('name'),
        'version': page.get('version', {}).get('number'),
        'last_modified': page.get('version', {}).get('when'),
        'url': page.get('_links', {}).get('webui', ''),
        'ingested_at': datetime.now().isoformat()
    }
    
    # Download attachments
    attachment_map, drawio_files = download_attachments(confluence, page_id, download_dir)
    
    # Get HTML content - prefer view format for better rendering
    storage_content = page.get('body', {}).get('storage', {}).get('value', '')
    view_content = page.get('body', {}).get('view', {}).get('value', '')
    html_content = view_content if view_content else storage_content
    
    if not html_content:
        print("Warning: Page has no body content", file=sys.stderr)
        html_content = ""
    
    # Debug: Check for images, SVGs and drawio elements
    print("\n--- DEBUG: Checking page content ---", file=sys.stderr)
    svg_count = len(re.findall(r'<svg[^>]*>', html_content, re.IGNORECASE))
    img_count = len(re.findall(r'<img[^>]+>', html_content, re.IGNORECASE))
    drawio_macros = re.findall(r'<div[^>]*class="[^"]*drawio-macro[^"]*"[^>]*>', html_content, re.IGNORECASE)
    linked_resources = re.findall(r'data-linked-resource-default-alias="([^"]+)"', html_content)
    ac_images = re.findall(r'<ac:image[^>]*>.*?</ac:image>', storage_content, re.DOTALL)
    
    print(f"  SVG elements: {svg_count}", file=sys.stderr)
    print(f"  IMG elements: {img_count}", file=sys.stderr)
    print(f"  DrawIO macro placeholders: {len(drawio_macros)}", file=sys.stderr)
    print(f"  Linked resources: {linked_resources}", file=sys.stderr)
    print(f"  ac:image macros in storage: {len(ac_images)}", file=sys.stderr)
    print("--- END DEBUG ---\n", file=sys.stderr)
    
    # Process Draw.io diagrams
    diagram_map = extract_drawio_diagrams(html_content, confluence, download_dir, attachment_map)
    html_content = replace_drawio_with_images(html_content, diagram_map, attachment_map)
    
    # Embed local images
    html_content = extract_and_embed_images(storage_content, html_content, attachment_map)
    
    # Process Confluence tabs
    html_content = process_confluence_tabs(html_content)
    
    # Save intermediate HTML (useful for debugging)
    html_filename = f"{title.replace('/', '_').replace(' ', '_')}.html"
    html_path = page_dir / html_filename
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{title}</title></head>
<body><h1>{title}</h1>{html_content}</body>
</html>""")
    
    # Convert to Markdown
    md_content = convert_html_to_markdown(html_content, attachment_map)
    md_content = f"# {title}\n\n{md_content}"
    
    # Convert Draw.io diagrams to Mermaid using XML parsing (FREE - no model costs)
    diagram_mermaid_map = {}
    if convert_diagrams:
        # Scan download directory for ALL .drawio files
        all_drawio_files = []
        if download_dir.exists():
            all_drawio_files = [f.name for f in download_dir.iterdir() 
                               if f.is_file() and (f.suffix.lower() == '.drawio' or is_drawio_file(str(f)))]
        
        # Also include any from the drawio_files list
        all_drawio_files = list(set(all_drawio_files + drawio_files))
        
        if all_drawio_files:
            print(f"\n📊 DRAW.IO → MERMAID (XML parsing - FREE, no model cost)", file=sys.stderr)
            print(f"   Found {len(all_drawio_files)} Draw.io file(s)", file=sys.stderr)
            
            for drawio_file in all_drawio_files:
                drawio_path = download_dir / drawio_file
                if not drawio_path.exists():
                    print(f"   ⚠ File not found: {drawio_file}", file=sys.stderr)
                    continue
                
                print(f"   📄 {drawio_file} → parsing XML...", file=sys.stderr)
                mermaid_code = convert_drawio_to_mermaid(drawio_path)
                
                if mermaid_code and "No diagram data extracted" not in mermaid_code:
                    # Map both .drawio and .png versions (PNG preview uses same name)
                    diagram_mermaid_map[drawio_file] = mermaid_code
                    png_name = os.path.splitext(drawio_file)[0] + '.png'
                    diagram_mermaid_map[png_name] = mermaid_code
                    print(f"   ✅ {drawio_file} → Mermaid (success)", file=sys.stderr)
                else:
                    print(f"   ⚠ {drawio_file} → XML parsing failed (agent will use vision on PNG)", file=sys.stderr)
        else:
            print("\n📊 DRAW.IO: No .drawio files found", file=sys.stderr)
    
    # Inline Mermaid diagrams (replace image refs with Mermaid)
    if diagram_mermaid_map:
        print(f"\n🔄 Replacing {len(diagram_mermaid_map)//2} diagram reference(s) with Mermaid...", file=sys.stderr)
        md_content = inline_mermaid_diagrams(md_content, diagram_mermaid_map)
    
    # Fix image paths to include attachments folder prefix and convert Confluence URLs
    attachments_folder = "attachments"
    md_content = fix_image_paths(md_content, attachments_folder, attachment_map)
    
    # Save final Markdown to page folder
    final_md_path = page_dir / "page.md"
    with open(final_md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    # Save metadata to page folder
    metadata['attachments'] = list(attachment_map.keys())
    metadata['drawio_files'] = drawio_files
    metadata['converted_diagrams'] = list(diagram_mermaid_map.keys())
    
    meta_path = page_dir / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    # Print summary
    remaining_image_refs = re.findall(r'!\[[^\]]*\]\(([^)]*\.(png|jpg|jpeg|gif|svg))\)', md_content)
    remaining_images = len(remaining_image_refs)
    mermaid_count = len(re.findall(r'```mermaid', md_content))
    
    print("\n" + "="*60, file=sys.stderr)
    print("✅ INGESTION COMPLETE", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"   Output: {final_md_path}", file=sys.stderr)
    print(f"   Attachments: {download_dir}", file=sys.stderr)
    
    if mermaid_count > 0:
        print(f"\n   📊 Draw.io → Mermaid: {mermaid_count} diagram(s) converted (FREE via XML parsing)", file=sys.stderr)
    
    if remaining_images > 0:
        print(f"\n   🖼️  IMAGES NEED VISION: {remaining_images} image(s) (costs $$ - no .drawio source)", file=sys.stderr)
        for img_path, ext in remaining_image_refs:
            print(f"      → {img_path}", file=sys.stderr)
        print(f"\n   📋 Agent: Read each image and convert to Mermaid", file=sys.stderr)
    else:
        print(f"\n   ✅ All diagrams converted - no vision needed (saved $$$)", file=sys.stderr)
    
    return {
        'metadata': metadata,
        'page_dir': str(page_dir),
        'markdown_path': str(final_md_path),
        'attachments_dir': str(download_dir),
        'attachments': list(attachment_map.keys()),
        'drawio_files': drawio_files,
        'mermaid_diagrams': len(diagram_mermaid_map)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Confluence page and convert to self-contained Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  CONFLUENCE_URL          Your Confluence instance URL
  CONFLUENCE_API_TOKEN    Personal Access Token (PAT)

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
        "--output-dir", "-o",
        default="governance/output",
        help="Output directory (default: governance/output)"
    )
    parser.add_argument(
        "--no-convert",
        action="store_true",
        help="Skip diagram conversion to Mermaid"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["governance", "index"],
        default="governance",
        help="Mode: 'governance' for validation, 'index' for rule indexing (default: governance)"
    )
    
    args = parser.parse_args()
    
    result = ingest_page(
        page_id=args.page_id,
        output_dir=args.output_dir,
        convert_diagrams=not args.no_convert,
        mode=args.mode
    )
    
    # Print result as JSON for programmatic use
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
