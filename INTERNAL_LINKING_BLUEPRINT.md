# AI-Powered Internal Linking Opportunity Finder - Complete Blueprint

## Table of Contents
1. [Recommended Architecture](#1-recommended-architecture)
2. [System Workflow Diagram](#2-system-workflow-diagram)
3. [Technology Stack](#3-technology-stack)
4. [Database/Schema Design](#4-databaseschema-design)
5. [Crawling Strategy](#5-crawling-strategy)
6. [URL Normalization Strategy](#6-url-normalization-strategy)
7. [Existing-Link Detection Logic](#7-existing-link-detection-logic)
8. [Semantic Search Strategy](#8-semantic-search-strategy)
9. [AI Model Strategy](#9-ai-model-strategy)
10. [Prompt Architecture](#10-prompt-architecture)
11. [JSON Schemas](#11-json-schemas)
12. [UI Design](#12-ui-design)
13. [Cost Optimization Strategy](#13-cost-optimization-strategy)
14. [MVP Plan](#14-mvp-plan)
15. [Step-by-Step Implementation](#15-step-by-step-implementation)
16. [Example Code](#16-example-code)
17. [Example Gemini Prompts](#17-example-gemini-prompts)
18. [Testing Strategy](#18-testing-strategy)
19. [Common Failure Cases](#19-common-failure-cases)
20. [Version 2 Improvements](#20-version-2-improvements)

---

## 1. Recommended Architecture

### Architecture Choice: Python + SQLite + Gemini API + Streamlit UI

**Why this approach?**
- **Simplicity**: Python is beginner-friendly with excellent libraries for web scraping, NLP, and data handling
- **Cost**: SQLite is free and embedded (no separate database server), Gemini has generous free tier
- **Accuracy**: Deterministic code for facts, AI only for semantic understanding
- **Scalability**: Can handle thousands of blog posts locally; can migrate to PostgreSQL/Supabase later if needed
- **Development Speed**: Streamlit provides instant UI without frontend development
- **No deployment complexity initially**: Run locally, deploy to Streamlit Cloud or Hugging Face Spaces later

**Simpler Alternative Considered:**
- Google Sheets + Apps Script: Limited by API quotas, slower for large datasets, UI constraints
- **Decision**: Python approach is only slightly more complex but significantly more capable

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│                      (Streamlit Web App)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Sitemap      │  │ Blog         │  │ New Page     │          │
│  │ Parser       │  │ Crawler      │  │ Analyzer     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ URL          │  │ Existing     │  │ Candidate    │          │
│  │ Normalizer   │  │ Link Checker │  │ Retriever    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Content      │  │ Embedding    │  │ AI Ranking   │          │
│  │ Extractor    │  │ Generator    │  │ Engine       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              SQLite Database (local.db)                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
│  │  │ blog_posts  │  │ embeddings  │  │ analysis    │      │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Gemini API    │  │ Your Website │  │ (Optional)   │          │
│  │ (AI/LLM)      │  │ (Sitemap/    │  │ Supabase/    │          │
│  │               │  │  Content)    │  │ PostgreSQL   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. System Workflow Diagram

### Initial Indexing Workflow (One-time or periodic)

```
Start
  │
  ▼
Input: Sitemap URL
  │
  ▼
Parse Sitemap XML → Extract Blog URLs
  │
  ▼
For Each URL:
  ├─→ Fetch HTML
  ├─→ Extract Article Content (title, body, headings)
  ├─→ Extract All Links (for existing-link detection)
  ├─→ Clean Content (remove nav, footer, etc.)
  ├─→ Generate Embedding (using Gemini or sentence-transformers)
  ├─→ Normalize URL
  └─→ Store in SQLite
  │
  ▼
Indexing Complete
```

### New Page Analysis Workflow

```
Start
  │
  ▼
Input: New Page URL + Anchor Text
  │
  ▼
Fetch & Analyze New Page
  ├─→ Extract title, content
  ├─→ Generate embedding
  ├─→ AI Analysis: topic, intent, concepts
  │
  ▼
Candidate Retrieval (Multi-stage)
  │
  ├─→ Stage 1: Vector Similarity Search (top 100)
  │   └─→ Compare new page embedding with blog embeddings
  │
  ├─→ Stage 2: Keyword/Topic Filter (top 50)
  │   └─→ Filter by title/content keyword matches
  │
  ├─→ Stage 3: Existing-Link Filter (remaining)
  │   └─→ Remove posts already linking to destination
  │
  └─→ Stage 4: AI Semantic Ranking (top 20)
      └─→ Gemini ranks by contextual relevance
  │
  ▼
For Each Top Candidate:
  ├─→ Check if exact anchor exists (deterministic)
  ├─→ AI: Analyze best anchor placement
  ├─→ AI: Generate suggested edit if needed
  └─→ Calculate opportunity score
  │
  ▼
Display Ranked Opportunities
  │
  ▼
User Clicks Opportunity → Show Detail View
  │
  ▼
Display: Before/After, Reason, Score
  │
  ▼
End
```

---

## 3. Technology Stack

### Core Stack

| Component | Technology | Why? |
|-----------|-----------|------|
| **Language** | Python 3.10+ | Beginner-friendly, excellent libraries |
| **Web Framework** | Streamlit | Instant UI, no frontend code needed |
| **Database** | SQLite | Embedded, free, sufficient for 10K+ posts |
| **AI/LLM** | Google Gemini API | Generous free tier, good semantic understanding |
| **Web Scraping** | BeautifulSoup + requests | Simple, reliable for static content |
| **Embeddings** | sentence-transformers (local) OR Gemini embeddings | Free local option vs paid API |
| **URL Handling** | urllib.parse | Built-in, reliable |
| **Data Processing** | pandas | Easy data manipulation |

### Optional Future Upgrades

| Component | When Needed | Upgrade To |
|-----------|-------------|------------|
| Database | >50K posts or concurrent users | PostgreSQL/Supabase |
| Vector Search | >100K posts | pgvector or Qdrant |
| Hosting | Production deployment | Streamlit Cloud, Hugging Face, or Railway |
| Caching | Frequent re-analysis | Redis |

### Required Python Packages

```
streamlit
beautifulsoup4
requests
pandas
google-generativeai
sentence-transformers  # or use Gemini embeddings
numpy
sqlite3  # built-in
urllib3
lxml
```

---

## 4. Database/Schema Design

### SQLite Schema

```sql
-- Blog posts table
CREATE TABLE blog_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT,
    content TEXT,
    cleaned_content TEXT,
    headings TEXT,  -- JSON array of headings
    word_count INTEGER,
    category TEXT,
    last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    existing_links TEXT,  -- JSON array of normalized outbound links
    embedding BLOB,  -- Serialized numpy array or use separate table
    is_indexed BOOLEAN DEFAULT 0
);

-- Embeddings table (alternative: store in separate table for performance)
CREATE TABLE embeddings (
    blog_post_id INTEGER PRIMARY KEY,
    embedding_vector BLOB,  -- Serialized numpy array (768-dim for typical models)
    FOREIGN KEY (blog_post_id) REFERENCES blog_posts(id)
);

-- Analysis results table (cache for re-use)
CREATE TABLE analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_url TEXT NOT NULL,
    anchor_text TEXT NOT NULL,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    results_json TEXT NOT NULL,  -- Full JSON results
    UNIQUE(destination_url, anchor_text)
);

-- Indexes for performance
CREATE INDEX idx_normalized_url ON blog_posts(normalized_url);
CREATE INDEX idx_word_count ON blog_posts(word_count);
CREATE INDEX idx_last_crawled ON blog_posts(last_crawled);
```

### Why This Schema?

- **Separate embeddings table**: Allows efficient vector operations without loading full post content
- **Normalized URL**: Critical for reliable existing-link detection
- **Existing links stored**: Pre-computed during crawl, no need to re-parse
- **Analysis cache**: Avoid re-analyzing same destination page + anchor combination
- **JSON fields**: Flexible storage for headings, links (SQLite handles JSON well)

### Simpler Alternative (MVP)

For initial MVP, you can skip the separate embeddings table and store everything in `blog_posts`:

```sql
CREATE TABLE blog_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    existing_links TEXT,  -- JSON
    embedding BLOB,
    last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Crawling Strategy

### Safe Crawling Approach

```python
# Pseudocode for crawler
import requests
from bs4 import BeautifulSoup
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

class BlogCrawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.rp = urllib.robotparser.RobotFileParser()
        self.rp.set_url(urljoin(base_url, '/robots.txt'))
        self.rp.read()
        
    def can_fetch(self, url):
        return self.rp.can_fetch('*', url)
    
    def fetch_page(self, url, delay=1):
        if not self.can_fetch(url):
            return None
            
        time.sleep(delay)  # Respect rate limits
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'InternalLinkFinder/1.0 (contact@yourdomain.com)'
            })
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
```

### Content Extraction Strategy

**Why custom extraction vs libraries like trafilatura?**
- Custom extraction gives you control over what to include/exclude
- Simpler to debug when something goes wrong
- Your site structure is predictable

**Extraction Rules:**

```python
def extract_article_content(html, base_url):
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove non-content elements
    for element in soup.find_all(['nav', 'footer', 'header', 'aside', 
                                  'script', 'style', 'noscript', 
                                  'iframe', 'svg', 'comments']):
        element.decompose()
    
    # Remove common sidebar/ad classes
    for element in soup.find_all(class_=re.compile(
        r'(sidebar|advertisement|promo|social|related|comments)')):
        element.decompose()
    
    # Extract main content (adjust selector based on your site)
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    
    if not main_content:
        main_content = soup.body
    
    # Extract text
    title = soup.find('h1') or soup.find('title')
    title = title.get_text(strip=True) if title else ""
    
    # Get headings
    headings = []
    for h in main_content.find_all(['h2', 'h3', 'h4']):
        headings.append({
            'level': h.name,
            'text': h.get_text(strip=True)
        })
    
    # Get paragraphs
    paragraphs = []
    for p in main_content.find_all('p'):
        text = p.get_text(strip=True)
        if len(text) > 50:  # Filter very short paragraphs
            paragraphs.append(text)
    
    # Extract all links
    links = []
    for a in main_content.find_all('a', href=True):
        absolute_url = urljoin(base_url, a['href'])
        links.append(absolute_url)
    
    return {
        'title': title,
        'content': '\n\n'.join(paragraphs),
        'headings': headings,
        'links': links,
        'word_count': sum(len(p.split()) for p in paragraphs)
    }
```

### Rate Limiting & Server Load

- **Delay**: 1-2 seconds between requests (configurable)
- **Respect robots.txt**: Always check first
- **Concurrent requests**: Limit to 1-3 for MVP
- **Timeout**: 10 seconds per request
- **Retry logic**: 3 retries with exponential backoff

### Handling JavaScript-Rendered Content

**For MVP**: Assume static HTML (most blogs are static)

**If JS rendering needed**:
- Use Playwright or Selenium
- Adds complexity and cost
- Only implement if absolutely necessary

---

## 6. URL Normalization Strategy

### Why URL Normalization is Critical

Without normalization, these URLs would be treated as different:
- `https://example.com/page`
- `https://example.com/page/`
- `https://example.com/page?utm_source=blog`
- `http://example.com/page`
- `https://EXAMPLE.COM/page`

### Normalization Function

```python
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def normalize_url(url):
    """
    Normalize URL for reliable comparison.
    Handles: scheme, case, trailing slash, query params, fragments
    """
    parsed = urlparse(url)
    
    # Convert scheme and netloc to lowercase
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if (scheme == 'http' and netloc.endswith(':80')) or \
       (scheme == 'https' and netloc.endswith(':443')):
        netloc = netloc.rsplit(':', 1)[0]
    
    # Remove fragment
    fragment = ''
    
    # Handle query parameters - remove tracking params
    query_params = parse_qs(parsed.query)
    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 
                       'utm_term', 'utm_content', 'fbclid', 'gclid'}
    for param in tracking_params:
        query_params.pop(param, None)
    
    # Rebuild query string
    query = urlencode(query_params, doseq=True) if query_params else ''
    
    # Normalize path - ensure consistent trailing slash
    path = parsed.path
    if path and not path.endswith('/'):
        # For blog posts, typically no trailing slash
        # Adjust based on your site's convention
        pass
    
    # Reconstruct URL
    normalized = urlunparse((scheme, netloc, path, '', query, fragment))
    
    return normalized

# Examples
print(normalize_url("https://EXAMPLE.COM/page?utm_source=blog#section"))
# Output: https://example.com/page

print(normalize_url("http://example.com/page/"))
# Output: http://example.com/page/  (or without / based on your convention)
```

### Canonical URL Handling

```python
def get_canonical_url(soup, current_url):
    """
    Extract canonical URL from HTML if present
    """
    canonical_tag = soup.find('link', rel='canonical')
    if canonical_tag and canonical_tag.get('href'):
        return normalize_url(canonical_tag['href'])
    return normalize_url(current_url)
```

### Why This Approach?

- **Deterministic**: Same URL always normalizes to same result
- **Removes noise**: Tracking params, fragments, case differences
- **Preserves meaning**: Doesn't remove meaningful query params
- **Simple**: Pure Python, no external dependencies

---

## 7. Existing-Link Detection Logic

### Detection Strategy

**Key Principle**: Check during crawl, store results, reuse during analysis

```python
def extract_and_store_links(html, base_url, blog_post_id, db_cursor):
    """
    Extract all links from a blog post and store normalized versions
    """
    soup = BeautifulSoup(html, 'lxml')
    extracted_links = []
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        absolute_url = urljoin(base_url, href)
        normalized = normalize_url(absolute_url)
        extracted_links.append(normalized)
    
    # Store as JSON array
    import json
    db_cursor.execute(
        "UPDATE blog_posts SET existing_links = ? WHERE id = ?",
        (json.dumps(extracted_links), blog_post_id)
    )
    
    return extracted_links

def already_links_to_destination(blog_post_id, destination_url, db_cursor):
    """
    Check if a blog post already links to the destination URL
    """
    db_cursor.execute(
        "SELECT existing_links FROM blog_posts WHERE id = ?",
        (blog_post_id,)
    )
    result = db_cursor.fetchone()
    
    if not result or not result[0]:
        return False
    
    import json
    existing_links = json.loads(result[0])
    normalized_destination = normalize_url(destination_url)
    
    return normalized_destination in existing_links
```

### Edge Cases Handled

| Case | Example | Normalized To |
|------|---------|---------------|
| Trailing slash | `/page` vs `/page/` | Both normalize consistently |
| Query params | `/page?utm=blog` | `/page` (tracking removed) |
| Relative URLs | `../other-page` | Converted to absolute |
| Protocol-relative | `//example.com/page` | `https://example.com/page` |
| Case differences | `/PAGE` vs `/page` | `/page` |
| Fragment | `/page#section` | `/page` |

### Why This Works

- **Pre-computed**: Links extracted once during crawl
- **Fast lookup**: Simple array membership check
- **Reliable**: Normalization handles edge cases
- **No AI needed**: Pure deterministic code

---

## 8. Semantic Search Strategy

### Two-Phase Approach

**Phase 1: Vector Similarity (Cheap, Fast)**
- Use embeddings to find top N candidates
- Cosine similarity between new page and blog posts
- Returns top 100-200 candidates

**Phase 2: AI Ranking (Expensive, Accurate)**
- Send top 20-50 candidates to Gemini
- AI evaluates contextual relevance
- Returns final ranked list

### Embedding Strategy

#### Option A: Local sentence-transformers (Free)

```python
from sentence_transformers import SentenceTransformer

# Load model (runs locally, free)
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions, fast

def generate_embedding(text):
    return model.encode(text)
```

**Pros**: Free, runs locally, no API limits
**Cons**: Less semantic understanding than Gemini embeddings

#### Option B: Gemini Embeddings API (Paid but better)

```python
import google.generativeai as genai

genai.configure(api_key='your-api-key')

def generate_embedding(text):
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return response['embedding']
```

**Pros**: Better semantic understanding, same API as LLM
**Cons**: Costs money ($0.0001 per 1K characters), rate limits

#### Recommendation: Start with Local

**Why?**
- Free for MVP
- Sufficient for initial filtering
- Can upgrade to Gemini embeddings later if accuracy insufficient

### Similarity Search

```python
import numpy as np

def find_similar_posts(new_page_embedding, db_cursor, top_k=100):
    """
    Find top K similar posts using cosine similarity
    """
    # Get all embeddings from database
    db_cursor.execute("SELECT id, title, url, embedding FROM blog_posts")
    posts = db_cursor.fetchall()
    
    similarities = []
    for post_id, title, url, embedding_blob in posts:
        if embedding_blob:
            embedding = np.frombuffer(embedding_blob, dtype=np.float32)
            similarity = cosine_similarity(new_page_embedding, embedding)
            similarities.append((similarity, post_id, title, url))
    
    # Sort by similarity (descending)
    similarities.sort(reverse=True, key=lambda x: x[0])
    
    return similarities[:top_k]

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### Why This Two-Phase Approach?

- **Cost efficiency**: Don't send 5,000 posts to AI
- **Speed**: Vector search is milliseconds, AI is seconds
- **Accuracy**: AI only evaluates strong candidates
- **Scalable**: Works well up to 50K+ posts

### Simpler Alternative (No Embeddings)

For very small sites (<500 posts), you could skip embeddings:

```python
def find_candidates_by_keywords(destination_keywords, db_cursor):
    """
    Simple keyword matching for small sites
    """
    query = f"""
    SELECT id, title, url, content 
    FROM blog_posts 
    WHERE content LIKE '%{keyword1}%' 
       OR content LIKE '%{keyword2}%'
    """
    # This is basic but works for small datasets
```

**Not recommended for your use case** (large site)

---

## 9. AI Model Strategy

### Gemini Model Selection

| Task | Recommended Model | Why |
|------|------------------|-----|
| Destination Page Analysis | Gemini 1.5 Flash | Fast, cheap, sufficient for summarization |
| Blog Relevance Ranking | Gemini 1.5 Flash | Fast ranking, good semantic understanding |
| Anchor Placement Analysis | Gemini 1.5 Pro | More careful for text modification |
| Embedding Generation | embedding-001 or local | Use local for MVP |

### Gemini Free Tier Limits (as of 2024)

- **Gemini 1.5 Flash**: 15 requests/minute, free quota varies by region
- **Gemini 1.5 Pro**: 2 requests/minute, limited free quota
- **Embeddings**: Separate quota, very generous

**When free tier insufficient**:
- Flash: ~$0.00025 per 1K characters (very cheap)
- Pro: ~$0.0025 per 1K characters (still cheap)

### Cost Estimation

For 5,000 blog posts, analyzing 1 new page:

| Stage | Operations | Cost (Flash) |
|-------|-----------|--------------|
| Embedding generation | 5,000 × 1K chars | Free (local) or $0.50 (Gemini) |
| Destination analysis | 1 × 2K chars | $0.0005 |
| Candidate ranking | 20 × 1K chars | $0.005 |
| Anchor placement | 10 × 2K chars | $0.005 |
| **Total per new page** | | **~$0.01** |

**Initial indexing (one-time)**:
- 5,000 posts × 1K chars = $0.50 (if using Gemini embeddings)
- Free if using local sentence-transformers

### Why This Model Strategy?

- **Flash for bulk**: Fast, cheap, good enough for ranking
- **Pro for precision**: More careful for actual text edits
- **Local embeddings**: Free, sufficient for filtering
- **Cost-effective**: <$0.02 per new page analysis

---

## 10. Prompt Architecture

### Prompt A: Destination Page Analysis

```python
DESTINATION_PAGE_PROMPT = """
Analyze this web page and extract key information for internal linking strategy.

PAGE CONTENT:
{content}

ANCHOR TEXT: "{anchor_text}"

Provide a JSON response with this exact structure:
{{
    "main_topic": "brief 2-3 word topic",
    "search_intent": "informational|commercial|transactional|navigational",
    "primary_keywords": ["keyword1", "keyword2", "keyword3"],
    "related_concepts": ["concept1", "concept2", "concept3"],
    "suitable_contexts": [
        "context where this page would be naturally referenced",
        "another context"
    ],
    "anchor_meaning": "what this anchor text represents in context",
    "target_audience": "who would benefit from this page"
}}

Be concise and specific. Focus on SEO-relevant information.
"""
```

### Prompt B: Blog Relevance Analysis

```python
BLOG_RELEVANCE_PROMPT = """
Evaluate whether this blog post is a good candidate for an internal link.

DESTINATION PAGE SUMMARY:
{destination_summary}

BLOG POST:
Title: {title}
Content: {content}

ANCHOR TEXT: "{anchor_text}"

Provide a JSON response:
{{
    "relevance_score": 0-100,
    "topical_match": "exact|strong|moderate|weak",
    "reader_value": "high|medium|low|none",
    "natural_fit": true/false,
    "reasoning": "brief explanation of why this is or isn't relevant",
    "link_would_help_reader": true/false,
    "confidence": 0.0-1.0
}}

Be conservative. If the link wouldn't genuinely help readers, score it low.
"""
```

### Prompt C: Anchor Placement Analysis

```python
ANCHOR_PLACEMENT_PROMPT = """
Analyze this blog post to find the best location for an internal link.

DESTINATION PAGE:
Topic: {destination_topic}
Summary: {destination_summary}

ANCHOR TEXT: "{anchor_text}"

BLOG POST CONTENT:
{content}

INSTRUCTIONS:
1. Check if the exact anchor text "{anchor_text}" exists in the content.
2. If it exists, identify all occurrences and select the best one.
3. If it doesn't exist, identify the best sentence/paragraph where it could be naturally inserted.
4. DO NOT force an insertion if there's no natural fit.

Provide a JSON response:
{{
    "exact_anchor_exists": true/false,
    "anchor_occurrences": [
        {{"paragraph": 1, "sentence": 2, "context": "surrounding text"}}
    ],
    "best_placement": {{
        "paragraph_number": 4,
        "sentence_number": 2,
        "original_text": "the original sentence",
        "modified_text": "sentence with anchor inserted",
        "before_context": "paragraph before",
        "after_context": "paragraph after",
        "insertion_type": "existing|new_insertion|none"
    }},
    "natural_fit_score": 0-100,
    "reasoning": "why this is the best location",
    "confidence": 0.0-1.0
}}

CRITICAL: Only suggest insertion if it flows naturally. If no good fit exists, set insertion_type to "none".
"""
```

### Prompt D: Final Recommendation (Combined)

```python
FINAL_RECOMMENDATION_PROMPT = """
Generate the final internal linking recommendation for this blog post.

DESTINATION PAGE:
URL: {destination_url}
Topic: {destination_topic}
Summary: {destination_summary}

ANCHOR TEXT: "{anchor_text}"

BLOG POST:
URL: {blog_url}
Title: {blog_title}
Relevance Score: {relevance_score}

ANCHOR ANALYSIS:
{anchor_analysis}

Generate a final JSON recommendation:
{{
    "opportunity_score": 0-100,
    "linking_recommended": true/false,
    "blog_url": "{blog_url}",
    "blog_title": "{blog_title}",
    "recommended_anchor": "{actual_anchor_to_use}",
    "recommended_location": {{
        "paragraph_number": 4,
        "sentence_number": 2
    }},
    "original_text": "text before modification",
    "suggested_text": "text after modification with **anchor** highlighted",
    "reason": "why this link should be added",
    "confidence": 0.0-1.0,
    "actionable": true/false
}}

If the score is below 70, set linking_recommended to false.
"""
```

### Why These Prompts?

- **Structured JSON**: Easy to parse, no hallucination risk
- **Conservative instructions**: Explicitly tell AI not to force links
- **Separate concerns**: Different prompts for different tasks
- **Deterministic where possible**: AI only for semantic decisions

---

## 11. JSON Schemas

### Destination Page Analysis Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "main_topic": {
      "type": "string",
      "description": "2-3 word topic description"
    },
    "search_intent": {
      "type": "string",
      "enum": ["informational", "commercial", "transactional", "navigational"]
    },
    "primary_keywords": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3,
      "maxItems": 5
    },
    "related_concepts": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3,
      "maxItems": 7
    },
    "suitable_contexts": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 2,
      "maxItems": 5
    },
    "anchor_meaning": {
      "type": "string",
      "description": "What the anchor represents"
    },
    "target_audience": {
      "type": "string",
      "description": "Who benefits from this page"
    }
  },
  "required": ["main_topic", "search_intent", "primary_keywords", "related_concepts"]
}
```

### Blog Relevance Schema

```json
{
  "type": "object",
  "properties": {
    "relevance_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100
    },
    "topical_match": {
      "type": "string",
      "enum": ["exact", "strong", "moderate", "weak"]
    },
    "reader_value": {
      "type": "string",
      "enum": ["high", "medium", "low", "none"]
    },
    "natural_fit": {
      "type": "boolean"
    },
    "reasoning": {
      "type": "string",
      "maxLength": 200
    },
    "link_would_help_reader": {
      "type": "boolean"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "required": ["relevance_score", "topical_match", "reader_value", "natural_fit", "confidence"]
}
```

### Anchor Placement Schema

```json
{
  "type": "object",
  "properties": {
    "exact_anchor_exists": {
      "type": "boolean"
    },
    "anchor_occurrences": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "paragraph": {"type": "integer"},
          "sentence": {"type": "integer"},
          "context": {"type": "string"}
        }
      }
    },
    "best_placement": {
      "type": "object",
      "properties": {
        "paragraph_number": {"type": "integer"},
        "sentence_number": {"type": "integer"},
        "original_text": {"type": "string"},
        "modified_text": {"type": "string"},
        "before_context": {"type": "string"},
        "after_context": {"type": "string"},
        "insertion_type": {
          "type": "string",
          "enum": ["existing", "new_insertion", "none"]
        }
      }
    },
    "natural_fit_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100
    },
    "reasoning": {"type": "string"},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
  },
  "required": ["exact_anchor_exists", "best_placement", "natural_fit_score", "confidence"]
}
```

### Final Recommendation Schema

```json
{
  "type": "object",
  "properties": {
    "opportunity_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100
    },
    "linking_recommended": {
      "type": "boolean"
    },
    "blog_url": {"type": "string", "format": "uri"},
    "blog_title": {"type": "string"},
    "recommended_anchor": {"type": "string"},
    "recommended_location": {
      "type": "object",
      "properties": {
        "paragraph_number": {"type": "integer"},
        "sentence_number": {"type": "integer"}
      }
    },
    "original_text": {"type": "string"},
    "suggested_text": {"type": "string"},
    "reason": {"type": "string"},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "actionable": {"type": "boolean"}
  },
  "required": ["opportunity_score", "linking_recommended", "blog_url", "recommended_anchor"]
}
```

### Why These Schemas?

- **Validation**: Can validate AI responses
- **Type safety**: Prevents parsing errors
- **Documentation**: Self-documenting structure
- **Extensibility**: Easy to add fields later

---

## 12. UI Design

### Streamlit UI Structure

```python
import streamlit as st

# Page config
st.set_page_config(
    page_title="Internal Link Finder",
    page_icon="🔗",
    layout="wide"
)

# Sidebar
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.header("Database")
    if st.button("Re-index Blog"):
        st.session_state.indexing = True

# Main content
st.title("🔗 Internal Linking Opportunity Finder")

# Input section
st.header("1. Input")
col1, col2, col3 = st.columns(3)
with col1:
    sitemap_url = st.text_input("Blog Sitemap URL", placeholder="https://example.com/blog-sitemap.xml")
with col2:
    new_page_url = st.text_input("New Page URL", placeholder="https://example.com/best-running-shoes")
with col3:
    anchor_text = st.text_input("Anchor Text", placeholder="best running shoes")

if st.button("Analyze Opportunities", type="primary"):
    # Run analysis
    results = analyze_opportunities(sitemap_url, new_page_url, anchor_text)
    st.session_state.results = results

# Results section
if 'results' in st.session_state:
    results = st.session_state.results
    
    # Summary stats
    st.header("2. Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Blog Posts Found", results['total_posts'])
    col2.metric("Already Linked", results['already_linked'])
    col3.metric("Irrelevant", results['irrelevant'])
    col4.metric("Opportunities", len(results['opportunities']))
    
    # Opportunities table
    st.header("3. Top Opportunities")
    for opp in results['opportunities'][:25]:
        with st.expander(f"{opp['blog_title']} (Score: {opp['opportunity_score']})"):
            st.write(f"**URL:** {opp['blog_url']}")
            st.write(f"**Reason:** {opp['reason']}")
            st.write(f"**Recommended Anchor:** {opp['recommended_anchor']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Before:**")
                st.text(opp['original_text'])
            with col2:
                st.write("**After:**")
                st.markdown(opp['suggested_text'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.button("Copy Suggestion", key=f"copy_{opp['blog_url']}")
            with col2:
                st.button("Open Blog Post", key=f"open_{opp['blog_url']}")
```

### UI Mockup

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔗 Internal Linking Opportunity Finder                    [Settings] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Input                                                           │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │
│  │ Sitemap URL     │ │ New Page URL    │ │ Anchor Text     │        │
│  │ [___________]   │ │ [___________]   │ │ [___________]   │        │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│                                                                     │
│  [ Analyze Opportunities ]                                          │
│                                                                     │
│  2. Summary                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Posts:   │ │ Linked:  │ │ Irrelevant│ │ Opps:    │               │
│  │  5,284   │ │   412    │ │  3,901   │ │   971    │               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
│                                                                     │
│  3. Top Opportunities                                               │
│                                                                     │
│  ▶ How to Choose Running Shoes for Beginners (Score: 96)          │
│     URL: https://example.com/choose-shoes                          │
│     Reason: Strong topical relationship, discusses footwear        │
│     Recommended Anchor: best running shoes                          │
│                                                                     │
│     Before: Choosing the right footwear is important...            │
│     After:  Choosing the **best running shoes** is important...    │
│                                                                     │
│     [Copy Suggestion]  [Open Blog Post]                            │
│                                                                     │
│  ▶ Running Tips for Beginners (Score: 91)                          │
│     ...                                                             │
│                                                                     │
│  4. Already Linked (Excluded)                                      │
│  • Blog Post A                                                      │
│  • Blog Post B                                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This UI?

- **Simple**: No complex navigation, single page
- **Actionable**: Clear copy/open buttons
- **Informative**: Shows summary stats
- **Expandable**: Details hidden by default
- **Streamlit**: No frontend code needed

---

## 13. Cost Optimization Strategy

### Multi-Stage Filtering Pipeline

```
5,000 blog posts
    │
    ▼
Stage 1: Vector Similarity (local, free)
    → Top 200 candidates (0.1 seconds)
    │
    ▼
Stage 2: Keyword Filter (local, free)
    → Top 100 candidates (0.05 seconds)
    │
    ▼
Stage 3: Existing-Link Check (local, free)
    → Top 50 candidates (0.02 seconds)
    │
    ▼
Stage 4: AI Relevance Ranking (Gemini Flash)
    → Top 20 candidates ($0.005)
    │
    ▼
Stage 5: AI Anchor Placement (Gemini Pro)
    → Top 10 final recommendations ($0.005)
```

### Cost Breakdown

#### Initial Indexing (One-time)

| Component | Cost (5K posts) | Cost (10K posts) | Cost (50K posts) |
|-----------|-----------------|------------------|------------------|
| Local embeddings | Free | Free | Free |
| Gemini embeddings | $0.50 | $1.00 | $5.00 |
| Storage | Free (SQLite) | Free | Free |
| **Total** | **$0-0.50** | **$0-1.00** | **$0-5.00** |

#### Per New Page Analysis

| Component | Operations | Cost |
|-----------|-----------|------|
| Vector search | 1 | Free |
| Keyword filter | 1 | Free |
| Existing-link check | 50 | Free |
| AI ranking (Flash) | 20 × 1K chars | $0.005 |
| AI anchor placement (Pro) | 10 × 2K chars | $0.005 |
| **Total per analysis** | | **$0.01** |

#### Monthly Estimates

| Activity | Frequency | Monthly Cost |
|----------|-----------|--------------|
| New page analysis | 10 pages | $0.10 |
| New page analysis | 50 pages | $0.50 |
| New page analysis | 100 pages | $1.00 |

### Optimization Techniques

1. **Cache analysis results**: Don't re-analyze same (URL, anchor) combination
2. **Batch AI requests**: Send multiple candidates in one request where possible
3. **Use Flash for ranking**: Pro only for final anchor placement
4. **Local embeddings**: Free, no API calls
5. **Deterministic filtering**: Eliminate candidates before AI

### Why This Cost Structure?

- **Extremely cheap**: <$0.02 per new page
- **Scales linearly**: Predictable costs
- **Free tier sufficient**: Gemini free tier covers moderate usage
- **No hidden costs**: SQLite is free, local embeddings are free

---

## 14. MVP Plan

### MVP Scope

**Features Included:**
1. Sitemap URL parsing
2. Blog content crawling
3. SQLite storage
4. Local embedding generation
5. New page analysis
6. Vector similarity search
7. Existing-link detection
8. AI relevance ranking (top 20)
9. AI anchor placement (top 10)
10. Streamlit UI
11. Results display with before/after

**Features Excluded (Version 2):**
- User authentication
- Scheduled re-crawling
- Export to CSV
- Bulk analysis
- History tracking
- A/B testing suggestions
- Link value estimation

### MVP Success Criteria

- Can index 1,000+ blog posts without crashing
- Returns relevant opportunities within 30 seconds
- Accurately detects existing links
- Provides actionable before/after suggestions
- Total cost per analysis <$0.02

### Why This MVP Scope?

- **Focus on core value**: Finding and ranking opportunities
- **Quick to build**: 1-2 weeks for capable developer
- **Low risk**: No complex infrastructure
- **Easy to validate**: Test on real data immediately

---

## 15. Step-by-Step Implementation

### Phase 1: Setup (Day 1)

**Tasks:**
1. Install Python 3.10+
2. Create virtual environment
3. Install dependencies
4. Get Gemini API key
5. Set up project structure

**Commands:**
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install streamlit beautifulsoup4 requests pandas google-generativeai sentence-transformers numpy
```

**Project Structure:**
```
internal-link-finder/
├── app.py                 # Streamlit UI
├── crawler.py             # Sitemap & blog crawler
├── database.py            # SQLite operations
├── embeddings.py          # Embedding generation
├── analyzer.py            # AI analysis
├── utils.py               # URL normalization, helpers
├── prompts.py             # AI prompts
├── data/
│   └── blog_index.db      # SQLite database (created automatically)
└── requirements.txt
```

### Phase 2: Sitemap Crawler (Day 2)

**File: crawler.py**

```python
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

def parse_sitemap(sitemap_url):
    """Parse sitemap XML and extract URLs"""
    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        # Handle both regular sitemaps and sitemap indexes
        urls = []
        if root.tag.endswith('sitemapindex'):
            # Sitemap index - parse child sitemaps
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                urls.extend(parse_sitemap(sitemap.text))
        else:
            # Regular sitemap
            for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                urls.append(url.text)
        
        return urls
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return []
```

### Phase 3: Blog Crawler (Day 2-3)

**File: crawler.py (continued)**

```python
from bs4 import BeautifulSoup
import time
import json

class BlogCrawler:
    def __init__(self, delay=1):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InternalLinkFinder/1.0'
        })
    
    def extract_content(self, html, base_url):
        """Extract article content from HTML"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove non-content
        for tag in soup.find_all(['nav', 'footer', 'header', 'aside', 'script', 'style']):
            tag.decompose()
        
        # Find main content
        main = soup.find('main') or soup.find('article') or soup.body
        
        # Extract title
        title = soup.find('h1')
        title = title.get_text(strip=True) if title else ""
        
        # Extract paragraphs
        paragraphs = []
        for p in main.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 50:
                paragraphs.append(text)
        
        # Extract links
        links = []
        for a in main.find_all('a', href=True):
            absolute_url = urljoin(base_url, a['href'])
            links.append(absolute_url)
        
        return {
            'title': title,
            'content': '\n\n'.join(paragraphs),
            'links': links,
            'word_count': sum(len(p.split()) for p in paragraphs)
        }
    
    def crawl_blog(self, url):
        """Crawl a single blog post"""
        time.sleep(self.delay)
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return self.extract_content(response.text, url)
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return None
```

### Phase 4: Database (Day 3)

**File: database.py**

```python
import sqlite3
import json
import numpy as np
from datetime import datetime

class BlogDatabase:
    def __init__(self, db_path='data/blog_index.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                normalized_url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                existing_links TEXT,
                embedding BLOB,
                word_count INTEGER,
                last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_normalized_url ON blog_posts(normalized_url)')
        
        conn.commit()
        conn.close()
    
    def save_post(self, url, title, content, links, embedding=None):
        """Save a blog post to database"""
        from utils import normalize_url
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO blog_posts 
                (url, normalized_url, title, content, existing_links, embedding, word_count, last_crawled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                url,
                normalize_url(url),
                title,
                content,
                json.dumps(links),
                embedding.tobytes() if embedding is not None else None,
                len(content.split()),
                datetime.now()
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    
    def get_all_posts(self):
        """Get all blog posts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, url, title, content, embedding FROM blog_posts')
        posts = cursor.fetchall()
        
        conn.close()
        return posts
    
    def already_links_to(self, post_id, destination_url):
        """Check if post already links to destination"""
        from utils import normalize_url
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT existing_links FROM blog_posts WHERE id = ?', (post_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if not result or not result[0]:
            return False
        
        links = json.loads(result[0])
        normalized_dest = normalize_url(destination_url)
        
        return normalized_dest in links
```

### Phase 5: Embeddings (Day 4)

**File: embeddings.py**

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingGenerator:
    def __init__(self):
        # Load local model (free)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def generate_embedding(self, text):
        """Generate embedding for text"""
        # Combine title and content for better representation
        return self.model.encode(text)
    
    def generate_batch_embeddings(self, texts):
        """Generate embeddings for multiple texts"""
        return self.model.encode(texts, show_progress_bar=True)
```

### Phase 6: URL Normalization (Day 4)

**File: utils.py**

```python
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def normalize_url(url):
    """Normalize URL for reliable comparison"""
    parsed = urlparse(url)
    
    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove fragment
    fragment = ''
    
    # Remove tracking params
    query_params = parse_qs(parsed.query)
    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 
                       'utm_term', 'utm_content', 'fbclid', 'gclid'}
    for param in tracking_params:
        query_params.pop(param, None)
    
    query = urlencode(query_params, doseq=True) if query_params else ''
    
    # Normalize path
    path = parsed.path
    
    normalized = urlunparse((scheme, netloc, path, '', query, fragment))
    return normalized

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### Phase 7: New Page Analysis (Day 5)

**File: analyzer.py**

```python
import google.generativeai as genai
import json
from prompts import DESTINATION_PAGE_PROMPT

class PageAnalyzer:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def analyze_destination_page(self, content, anchor_text):
        """Analyze destination page"""
        prompt = DESTINATION_PAGE_PROMPT.format(
            content=content[:5000],  # Limit length
            anchor_text=anchor_text
        )
        
        response = self.model.generate_content(prompt)
        
        try:
            return json.loads(response.text)
        except:
            return {"error": "Failed to parse AI response"}
```

### Phase 8: Candidate Retrieval (Day 5-6)

**File: analyzer.py (continued)**

```python
import numpy as np

class CandidateRetriever:
    def __init__(self, db):
        self.db = db
    
    def find_similar_posts(self, destination_embedding, embedding_generator, top_k=100):
        """Find similar posts using vector similarity"""
        posts = self.db.get_all_posts()
        
        similarities = []
        for post_id, url, title, content, embedding_blob in posts:
            if embedding_blob:
                embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                similarity = cosine_similarity(destination_embedding, embedding)
                similarities.append((similarity, post_id, url, title))
        
        similarities.sort(reverse=True, key=lambda x: x[0])
        return similarities[:top_k]
    
    def filter_existing_links(self, candidates, destination_url):
        """Remove candidates that already link to destination"""
        filtered = []
        for similarity, post_id, url, title in candidates:
            if not self.db.already_links_to(post_id, destination_url):
                filtered.append((similarity, post_id, url, title))
        return filtered
```

### Phase 9: AI Ranking (Day 6)

**File: analyzer.py (continued)**

```python
from prompts import BLOG_RELEVANCE_PROMPT

class RelevanceRanker:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def rank_candidates(self, destination_summary, candidates, anchor_text):
        """Rank candidates by relevance"""
        ranked = []
        
        for similarity, post_id, url, title in candidates:
            # Get post content from DB
            content = self.db.get_post_content(post_id)
            
            prompt = BLOG_RELEVANCE_PROMPT.format(
                destination_summary=json.dumps(destination_summary),
                title=title,
                content=content[:3000],
                anchor_text=anchor_text
            )
            
            response = self.model.generate_content(prompt)
            
            try:
                result = json.loads(response.text)
                result['post_id'] = post_id
                result['url'] = url
                result['title'] = title
                ranked.append(result)
            except:
                continue
        
        # Sort by relevance score
        ranked.sort(key=lambda x: x['relevance_score'], reverse=True)
        return ranked[:20]  # Return top 20
```

### Phase 10: Anchor Placement (Day 7)

**File: analyzer.py (continued)**

```python
from prompts import ANCHOR_PLACEMENT_PROMPT

class AnchorPlacer:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')  # Use Pro for precision
    
    def find_best_placement(self, destination_summary, anchor_text, blog_content):
        """Find best anchor placement in blog post"""
        prompt = ANCHOR_PLACEMENT_PROMPT.format(
            destination_topic=destination_summary['main_topic'],
            destination_summary=json.dumps(destination_summary),
            anchor_text=anchor_text,
            content=blog_content[:5000]
        )
        
        response = self.model.generate_content(prompt)
        
        try:
            return json.loads(response.text)
        except:
            return {"error": "Failed to parse AI response"}
```

### Phase 11: Streamlit UI (Day 8)

**File: app.py**

```python
import streamlit as st
from crawler import BlogCrawler, parse_sitemap
from database import BlogDatabase
from embeddings import EmbeddingGenerator
from analyzer import PageAnalyzer, CandidateRetriever, RelevanceRanker, AnchorPlacer
from utils import normalize_url

# Page config
st.set_page_config(
    page_title="Internal Link Finder",
    page_icon="🔗",
    layout="wide"
)

# Initialize
db = BlogDatabase()
embedding_gen = EmbeddingGenerator()

# Sidebar
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.header("Indexing")
    sitemap_url = st.text_input("Sitemap URL")
    if st.button("Index Blog"):
        with st.spinner("Crawling and indexing..."):
            urls = parse_sitemap(sitemap_url)
            st.write(f"Found {len(urls)} URLs")
            
            crawler = BlogCrawler(delay=1)
            for i, url in enumerate(urls):
                st.progress(i / len(urls))
                content = crawler.crawl_blog(url)
                if content:
                    embedding = embedding_gen.generate_embedding(
                        content['title'] + " " + content['content']
                    )
                    db.save_post(
                        url, 
                        content['title'], 
                        content['content'],
                        content['links'],
                        embedding
                    )
            st.success("Indexing complete!")

# Main content
st.title("🔗 Internal Linking Opportunity Finder")

col1, col2, col3 = st.columns(3)
with col1:
    new_page_url = st.text_input("New Page URL")
with col2:
    anchor_text = st.text_input("Anchor Text")
with col3:
    st.empty()

if st.button("Analyze Opportunities", type="primary") and api_key:
    with st.spinner("Analyzing..."):
        # Analyze destination page
        crawler = BlogCrawler()
        dest_content = crawler.crawl_blog(new_page_url)
        
        analyzer = PageAnalyzer(api_key)
        dest_summary = analyzer.analyze_destination_page(
            dest_content['content'],
            anchor_text
        )
        
        # Generate embedding for destination
        dest_embedding = embedding_gen.generate_embedding(
            dest_content['title'] + " " + dest_content['content']
        )
        
        # Find similar posts
        retriever = CandidateRetriever(db)
        candidates = retriever.find_similar_posts(dest_embedding, embedding_gen)
        
        # Filter existing links
        candidates = retriever.filter_existing_links(candidates, new_page_url)
        
        # Rank with AI
        ranker = RelevanceRanker(api_key)
        ranked = ranker.rank_candidates(dest_summary, candidates, anchor_text)
        
        # Find anchor placements for top 10
        placer = AnchorPlacer(api_key)
        final_results = []
        
        for candidate in ranked[:10]:
            post_content = db.get_post_content(candidate['post_id'])
            placement = placer.find_best_placement(
                dest_summary,
                anchor_text,
                post_content
            )
            
            final_results.append({
                'blog_title': candidate['title'],
                'blog_url': candidate['url'],
                'relevance_score': candidate['relevance_score'],
                'placement': placement
            })
        
        st.session_state.results = final_results

# Display results
if 'results' in st.session_state:
    results = st.session_state.results
    
    st.header("Results")
    for result in results:
        with st.expander(f"{result['blog_title']} (Score: {result['relevance_score']})"):
            st.write(f"**URL:** {result['blog_url']}")
            
            if 'best_placement' in result['placement']:
                placement = result['placement']['best_placement']
                st.write(f"**Paragraph:** {placement['paragraph_number']}")
                st.write(f"**Original:** {placement['original_text']}")
                st.write(f"**Suggested:** {placement['modified_text']}")
```

### Phase 12: Testing (Day 9)

**Test Cases:**

1. **Sitemap Parsing**
   - Test with real sitemap
   - Test with sitemap index
   - Test with invalid URL

2. **Content Extraction**
   - Test with various blog layouts
   - Verify non-content removal
   - Check link extraction

3. **URL Normalization**
   - Test trailing slash variations
   - Test query params
   - Test relative URLs

4. **Existing-Link Detection**
   - Create test post with known link
   - Verify detection works
   - Test normalization edge cases

5. **Embedding Search**
   - Test with known similar content
   - Verify ranking makes sense
   - Check performance

6. **AI Analysis**
   - Test with real destination page
   - Verify JSON parsing
   - Check relevance scores

7. **End-to-End**
   - Full workflow with small sitemap (10 URLs)
   - Verify results are actionable
   - Check cost

---

## 16. Example Code

### Complete Working Example

See the Phase 15 section above for complete code examples for each module.

### Key Integration Example

```python
# Example: Complete workflow
from crawler import parse_sitemap, BlogCrawler
from database import BlogDatabase
from embeddings import EmbeddingGenerator
from analyzer import PageAnalyzer, CandidateRetriever, RelevanceRanker, AnchorPlacer

# Initialize
db = BlogDatabase()
crawler = BlogCrawler()
embedding_gen = EmbeddingGenerator()

# Index blog
urls = parse_sitemap("https://example.com/blog-sitemap.xml")
for url in urls[:10]:  # Test with 10 first
    content = crawler.crawl_blog(url)
    if content:
        embedding = embedding_gen.generate_embedding(content['title'] + " " + content['content'])
        db.save_post(url, content['title'], content['content'], content['links'], embedding)

# Analyze new page
dest_content = crawler.crawl_blog("https://example.com/new-page")
analyzer = PageAnalyzer("your-api-key")
dest_summary = analyzer.analyze_destination_page(dest_content['content'], "anchor text")

# Find opportunities
dest_embedding = embedding_gen.generate_embedding(dest_content['title'] + " " + dest_content['content'])
retriever = CandidateRetriever(db)
candidates = retriever.find_similar_posts(dest_embedding, embedding_gen)
candidates = retriever.filter_existing_links(candidates, "https://example.com/new-page")

ranker = RelevanceRanker("your-api-key")
ranked = ranker.rank_candidates(dest_summary, candidates, "anchor text")

# Get anchor placements
placer = AnchorPlacer("your-api-key")
for candidate in ranked[:5]:
    post_content = db.get_post_content(candidate['post_id'])
    placement = placer.find_best_placement(dest_summary, "anchor text", post_content)
    print(f"{candidate['title']}: {placement}")
```

---

## 17. Example Gemini Prompts

See Section 10 (Prompt Architecture) for complete prompt templates.

### Prompt Testing Example

```python
# Test prompt
import google.generativeai as genai

genai.configure(api_key="your-key")
model = genai.GenerativeModel('gemini-1.5-flash')

prompt = DESTINATION_PAGE_PROMPT.format(
    content="Your blog content here...",
    anchor_text="best running shoes"
)

response = model.generate_content(prompt)
print(response.text)
```

---

## 18. Testing Strategy

### Unit Tests

```python
# test_utils.py
import unittest
from utils import normalize_url, cosine_similarity
import numpy as np

class TestURLNormalization(unittest.TestCase):
    def test_trailing_slash(self):
        url1 = normalize_url("https://example.com/page")
        url2 = normalize_url("https://example.com/page/")
        # Adjust based on your convention
    
    def test_query_params(self):
        url1 = normalize_url("https://example.com/page?utm_source=blog")
        url2 = normalize_url("https://example.com/page")
        self.assertEqual(url1, url2)
    
    def test_case_insensitive(self):
        url1 = normalize_url("https://EXAMPLE.COM/page")
        url2 = normalize_url("https://example.com/page")
        self.assertEqual(url1, url2)

class TestCosineSimilarity(unittest.TestCase):
    def test_identical(self):
        a = np.array([1, 2, 3])
        b = np.array([1, 2, 3])
        self.assertEqual(cosine_similarity(a, b), 1.0)
    
    def test_orthogonal(self):
        a = np.array([1, 0, 0])
        b = np.array([0, 1, 0])
        self.assertEqual(cosine_similarity(a, b), 0.0)

if __name__ == '__main__':
    unittest.main()
```

### Integration Tests

```python
# test_integration.py
def test_end_to_end():
    # Create test database
    db = BlogDatabase(':memory:')
    
    # Add test posts
    db.save_post(
        "https://example.com/post1",
        "Post 1",
        "This is about running shoes and footwear.",
        ["https://example.com/other"],
        None
    )
    
    # Test existing link detection
    assert db.already_links_to(1, "https://example.com/other")
    assert not db.already_links_to(1, "https://example.com/new-page")
    
    print("Integration tests passed!")
```

### Manual Testing Checklist

- [ ] Sitemap with 10 URLs parses correctly
- [ ] Content extraction removes navigation/footer
- [ ] Embeddings generate without errors
- [ ] Vector search returns relevant results
- [ ] Existing links are detected correctly
- [ ] AI ranking returns sensible scores
- [ ] Anchor placement suggestions are natural
- [ ] UI displays results correctly
- [ ] Copy button works
- [ ] Total time per analysis < 30 seconds

---

## 19. Common Failure Cases

### 1. Sitemap Parsing Fails

**Cause**: Invalid XML, network error, sitemap index

**Solution**:
```python
try:
    urls = parse_sitemap(sitemap_url)
except Exception as e:
    st.error(f"Failed to parse sitemap: {e}")
    # Fallback: manual URL input
```

### 2. Content Extraction Returns Empty

**Cause**: JavaScript-rendered content, unusual HTML structure

**Solution**:
```python
if not content or len(content['content']) < 100:
    print(f"Warning: Low content for {url}")
    # Skip or flag for review
```

### 3. AI Returns Invalid JSON

**Cause**: Model hallucination, prompt issues

**Solution**:
```python
try:
    result = json.loads(response.text)
except json.JSONDecodeError:
    # Retry with stricter prompt
    # Or use fallback logic
```

### 4. Embedding Generation Fails

**Cause**: Out of memory, text too long

**Solution**:
```python
def generate_embedding(text):
    # Truncate if too long
    if len(text) > 10000:
        text = text[:10000]
    return model.encode(text)
```

### 5. Database Lock Errors

**Cause**: Concurrent access

**Solution**:
```python
# Use connection per operation
conn = sqlite3.connect(db_path, timeout=30)
```

### 6. Rate Limiting from Website

**Cause**: Too many requests

**Solution**:
```python
# Increase delay
crawler = BlogCrawler(delay=2)  # 2 seconds between requests
```

### 7. Gemini API Quota Exceeded

**Cause**: Free tier limit

**Solution**:
- Switch to local embeddings
- Reduce AI calls
- Upgrade to paid tier ($0.00025/1K chars is cheap)

---

## 20. Version 2 Improvements

### Potential Enhancements

1. **Scheduled Re-crawling**
   - Automatically re-index blog weekly
   - Detect new/updated posts

2. **Bulk Analysis**
   - Analyze multiple new pages at once
   - Export results to CSV

3. **Link Value Estimation**
   - Estimate SEO value of each link
   - Prioritize high-value opportunities

4. **A/B Testing Suggestions**
   - Suggest multiple anchor options
   - Test which performs better

5. **History Tracking**
   - Track which suggestions were implemented
   - Measure impact on traffic

6. **User Authentication**
   - Multi-user support
   - Team collaboration

7. **Advanced Filtering**
   - Filter by category, date, word count
   - Exclude low-quality posts

8. **Integration with CMS**
   - Direct API integration with WordPress/other CMS
   - Auto-apply suggestions

### When to Upgrade

- **Upgrade to PostgreSQL**: When >50K posts or need concurrent access
- **Upgrade to vector DB**: When >100K posts or need sub-second search
- **Upgrade to cloud hosting**: When multiple users need access
- **Add authentication**: When team collaboration needed

---

## Summary: Recommended Implementation

### Start Here Today

**Day 1**: Setup environment, install dependencies, get API key

**Day 2-3**: Build sitemap parser and blog crawler

**Day 4**: Implement database and URL normalization

**Day 5**: Add embeddings and vector search

**Day 6-7**: Implement AI analysis and ranking

**Day 8**: Build Streamlit UI

**Day 9**: Test and iterate

### Technology Stack

- **Python 3.10+**
- **Streamlit** (UI)
- **SQLite** (database)
- **sentence-transformers** (local embeddings)
- **Gemini API** (AI analysis)
- **BeautifulSoup** (web scraping)

### Estimated Cost

- **Initial indexing**: Free (local embeddings) or $0.50 (Gemini embeddings)
- **Per new page analysis**: ~$0.01
- **Monthly (10 pages)**: ~$0.10

### Key Principles

1. **Code handles facts**: URL normalization, link detection, embedding search
2. **AI handles meaning**: Relevance ranking, anchor placement, semantic understanding
3. **Conservative filtering**: Multi-stage pipeline to reduce AI calls
4. **Simplicity first**: Local SQLite, no complex infrastructure

### Next Steps

1. Create project directory
2. Install dependencies
3. Copy code from Phase 15
4. Test with your sitemap
5. Iterate based on results

This blueprint provides everything needed to build a functional, accurate, and cost-effective internal linking opportunity finder.
