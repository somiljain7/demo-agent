# sitemap exact flow 

--- 

| Library | Why Chosen | Alternatives |
|---------|------------|--------------|
| **requests** | Industry standard, simple API | `urllib`, `httpx`, `aiohttp` |
| **BeautifulSoup** | Robust HTML parsing, easy to use | `lxml`, `html.parser`, `scrapy` |
| **html2text** | Clean markdown conversion | `markdownify`, `pypandoc` |
| **xml.etree** | Built-in, no dependencies | `lxml`, `xmltodict` |
| **pathlib** | Modern, object-oriented | `os.path` (older style) |

---

```
┌──────────────────────────────────────────────────────────────┐
│  1️⃣  DISCOVER SITEMAPS                                       │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► requests.get('/robots.txt')
    │     └─► Parse text for "Sitemap: " lines
    │
    ├─► requests.get('/sitemap.xml')  [Try common locations]
    │     └─► xml.etree.ElementTree.fromstring()
    │           └─► Validate it's valid XML
    │
    └─► Return list of sitemap URLs

┌──────────────────────────────────────────────────────────────┐
│  2️⃣  EXTRACT ALL URLs                                        │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► For each sitemap URL:
    │     │
    │     ├─► requests.get(sitemap_url)
    │     │
    │     ├─► ET.fromstring(xml_content)
    │     │
    │     ├─► root.findall('sm:url', namespaces)
    │     │     └─► Extract <loc> tags
    │     │
    │     └─► Check if it's sitemap index
    │           └─► Recursively process sub-sitemaps
    │
    └─► Return deduplicated list of page URLs

┌──────────────────────────────────────────────────────────────┐
│  3️⃣  FETCH & PROCESS EACH PAGE                               │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► time.sleep(1)  [Rate limiting]
    │
    ├─► requests.get(page_url, timeout=30)
    │     └─► Returns HTML content
    │
    ├─► BeautifulSoup(html_content, 'html.parser')
    │     │
    │     ├─► Remove unwanted tags
    │     │     └─► soup(['script', 'style', ...]).decompose()
    │     │
    │     ├─► Extract title
    │     │     └─► soup.find('title').get_text()
    │     │
    │     └─► Find main content
    │           └─► soup.select_one('main') or soup.find('body')
    │
    ├─► html2text.HTML2Text().handle(str(main_content))
    │     └─► Converts HTML → Markdown
    │
    ├─► re.sub(r'\n{3,}', '\n\n', markdown)
    │     └─► Clean excessive newlines
    │
    └─► Add metadata header
          └─► datetime.now().strftime('%Y-%m-%d %H:%M:%S')

┌──────────────────────────────────────────────────────────────┐
│  4️⃣  SAVE TO FILE SYSTEM                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► urlparse(url).path
    │     └─► Extract path component
    │
    ├─► re.sub(r'[^\w\-/]', '_', path)
    │     └─► Create safe filename
    │
    ├─► Path('knowledge_base') / directory / filename
    │     └─► Build full file path
    │
    ├─► full_dir.mkdir(parents=True, exist_ok=True)
    │     └─► Create nested directories
    │
    └─► open(filepath, 'w', encoding='utf-8').write(markdown)
          └─► Write markdown file

┌──────────────────────────────────────────────────────────────┐
│  5️⃣  CREATE INDEX                                            │
└──────────────────────────────────────────────────────────────┘
    │
    ├─► Collect all processed (url, filepath) pairs
    │
    ├─► filepath.relative_to(base_output_dir)
    │     └─► Get relative paths
    │
    ├─► Generate markdown index with links
    │
    └─► Write to knowledge_base/INDEX.md
```