import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from datetime import datetime
from pathlib import Path
import time
import re
from html import unescape
from bs4 import BeautifulSoup
import html2text

class WebsiteToMarkdownPipeline:
    def __init__(self, base_output_dir='knowledge_base'):
        self.base_output_dir = Path(base_output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.body_width = 0  # Don't wrap text
        
    def fetch_url(self, url, delay=1):
        """Fetch URL content with rate limiting"""
        try:
            time.sleep(delay)  # Rate limiting
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def discover_sitemaps(self, base_url):
        """Discover sitemap URLs from robots.txt and common locations"""
        sitemaps = []
        parsed = urlparse(base_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try robots.txt
        robots_url = urljoin(domain, '/robots.txt')
        content = self.fetch_url(robots_url, delay=0.5)
        if content:
            for line in content.decode('utf-8', errors='ignore').split('\n'):
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    sitemaps.append(sitemap_url)
        
        # Try common sitemap locations
        common_locations = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemap-index.xml',
            '/sitemap1.xml'
        ]
        
        for location in common_locations:
            url = urljoin(domain, location)
            if url not in sitemaps:
                content = self.fetch_url(url, delay=0.5)
                if content:
                    try:
                        ET.fromstring(content)
                        sitemaps.append(url)
                    except:
                        pass
        
        return sitemaps if sitemaps else [urljoin(domain, '/sitemap.xml')]
    
    def parse_sitemap(self, xml_content):
        """Parse sitemap and return all URLs"""
        try:
            root = ET.fromstring(xml_content)
            namespaces = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            urls = []
            
            # Check for sitemap index
            sitemaps = root.findall('sm:sitemap', namespaces)
            if sitemaps:
                for sitemap in sitemaps:
                    loc = sitemap.find('sm:loc', namespaces)
                    if loc is not None:
                        urls.append(('sitemap', loc.text))
            else:
                # Regular sitemap
                for url in root.findall('sm:url', namespaces):
                    loc = url.find('sm:loc', namespaces)
                    if loc is not None:
                        urls.append(('page', loc.text))
            
            return urls
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return []
    
    def extract_all_urls(self, sitemap_url):
        """Recursively extract all page URLs from sitemaps"""
        all_pages = []
        to_process = [sitemap_url]
        processed = set()
        
        while to_process:
            current_url = to_process.pop(0)
            if current_url in processed:
                continue
            
            processed.add(current_url)
            print(f"Processing sitemap: {current_url}")
            
            content = self.fetch_url(current_url)
            if not content:
                continue
            
            urls = self.parse_sitemap(content)
            for url_type, url in urls:
                if url_type == 'sitemap':
                    to_process.append(url)
                else:
                    all_pages.append(url)
        
        return all_pages
    
    def clean_html_to_markdown(self, html_content, page_url):
        """Convert HTML to clean Markdown"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script, style, nav, footer, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                            'aside', 'iframe', 'noscript']):
            element.decompose()
        
        # Remove comments
        for comment in soup.findAll(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else 'Untitled'
        
        # Try to find main content area
        main_content = None
        for selector in ['main', 'article', '[role="main"]', '.content', '#content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body') or soup
        
        # Convert to markdown
        markdown = self.html_converter.handle(str(main_content))
        
        # Clean up excessive newlines
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # Add metadata header
        header = f"""---
title: {title_text}
source: {page_url}
fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# {title_text}

"""
        
        return header + markdown.strip()
    
    def url_to_filename(self, url):
        """Convert URL to safe filename"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if not path or path == '':
            path = 'index'
        
        # Replace special characters
        safe_path = re.sub(r'[^\w\-/]', '_', path)
        safe_path = re.sub(r'_+', '_', safe_path)
        
        # Create directory structure
        parts = safe_path.split('/')
        if len(parts) > 1:
            directory = '/'.join(parts[:-1])
            filename = parts[-1]
        else:
            directory = ''
            filename = safe_path
        
        if not filename:
            filename = 'index'
        
        return directory, f"{filename}.md"
    
    def process_page(self, url):
        """Fetch and convert a single page to Markdown"""
        print(f"Processing: {url}")
        
        html_content = self.fetch_url(url)
        if not html_content:
            return None
        
        try:
            markdown = self.clean_html_to_markdown(html_content, url)
            return markdown
        except Exception as e:
            print(f"Error converting {url}: {e}")
            return None
    
    def save_markdown(self, url, markdown_content):
        """Save markdown content to file"""
        directory, filename = self.url_to_filename(url)
        
        # Create full path
        if directory:
            full_dir = self.base_output_dir / directory
        else:
            full_dir = self.base_output_dir
        
        full_dir.mkdir(parents=True, exist_ok=True)
        filepath = full_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"Saved: {filepath}")
        return filepath
    
    def create_index(self, processed_pages):
        """Create an index file listing all pages"""
        index_content = f"""# Knowledge Base Index

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Pages: {len(processed_pages)}

## Pages

"""
        for url, filepath in processed_pages:
            relative_path = filepath.relative_to(self.base_output_dir)
            index_content += f"- [{url}]({relative_path})\n"
        
        index_path = self.base_output_dir / 'INDEX.md'
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        print(f"\nIndex created: {index_path}")
    
    def run(self, website_url, max_pages=None):
        """Main pipeline execution"""
        print(f"Starting pipeline for: {website_url}\n")
        
        # Create output directory
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Discover sitemaps
        print("Discovering sitemaps...")
        sitemaps = self.discover_sitemaps(website_url)
        print(f"Found {len(sitemaps)} sitemap(s)\n")
        
        # Extract all URLs
        print("Extracting URLs from sitemaps...")
        all_urls = []
        for sitemap in sitemaps:
            urls = self.extract_all_urls(sitemap)
            all_urls.extend(urls)
        
        all_urls = list(set(all_urls))  # Remove duplicates
        print(f"Found {len(all_urls)} unique pages\n")
        
        if max_pages:
            all_urls = all_urls[:max_pages]
            print(f"Limiting to {max_pages} pages\n")
        
        # Process each page
        processed_pages = []
        for idx, url in enumerate(all_urls, 1):
            print(f"\n[{idx}/{len(all_urls)}]")
            markdown = self.process_page(url)
            
            if markdown:
                filepath = self.save_markdown(url, markdown)
                processed_pages.append((url, filepath))
        
        # Create index
        print("\n" + "="*50)
        self.create_index(processed_pages)
        
        print(f"\nPipeline complete!")
        print(f"Processed: {len(processed_pages)}/{len(all_urls)} pages")
        print(f"Output directory: {self.base_output_dir.absolute()}")


# Example usage
if __name__ == "__main__":
    print("Website to Markdown Knowledge Base Pipeline")
    print("="*50 + "\n")
    
    website_url = input("Enter website URL (e.g., https://example.com): ").strip()
    
    if not website_url:
        print("Error: URL is required")
        exit(1)
    
    output_dir = input("Enter output directory (default: knowledge_base): ").strip()
    if not output_dir:
        output_dir = "knowledge_base"
    
    max_pages = input("Max pages to process (leave empty for demo - default 5): ").strip()
    max_pages = int(max_pages) if max_pages else 5
    
    # Run pipeline
    pipeline = WebsiteToMarkdownPipeline(base_output_dir=output_dir)
    pipeline.run(website_url, max_pages=max_pages)


    # headpohne zone url : https://www.headphonezone.in