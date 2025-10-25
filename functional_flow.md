#  System Flow & Functionality

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow Diagram](#data-flow-diagram)
4. [Detailed Component Flows](#detailed-component-flows)

---

## System Overview

This is a **LiveKit-based AI Voice Agent** system that enables real-time voice conversations with an AI assistant that has access to a knowledge base extracted from websites.

### Core Components
- **FastAPI Backend** (`main.py`) - REST API server
- **Agent Worker** (`agent.py`) - LiveKit voice agent with RAG capabilities
- **Web Scraper** (`sitemap.py`) - Website-to-markdown converter
- **Vector DB** (`vector_db_init.py`) - Knowledge base storage & retrieval

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                        │
│                    (HTML Demo Page in FastAPI)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   /token     │  │    /demo     │  │ /extract-kb  │      │
│  │   endpoint   │  │   endpoint   │  │   endpoint   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
         │                                      │
         │                                      ▼
         │                          ┌──────────────────────┐
         │                          │   SITEMAP SCRAPER    │
         │                          │  (WebsiteToMD)       │
         │                          └──────────────────────┘
         │                                      │
         │                                      ▼
         │                          ┌──────────────────────┐
         │                          │   VECTOR DB INIT     │
         │                          │  (Qdrant + Embeddings)│
         │                          └──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                      LIVEKIT ROOM                            │
│                    (Real-time Voice)                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENT WORKER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Speech-to-  │  │     LLM      │  │  Text-to-    │      │
│  │     Text     │  │   (openAI)   │  │    Speech    │      │
│  │  (Deepgram)  │  │              │  │  (Cartesia)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                          │                                   │
│                          ▼                                   │
│                  ┌──────────────┐                           │
│                  │  RAG Lookup  │                           │
│                  │   Function   │                           │
│                  └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### Flow 1: Knowledge Base Extraction

```
User Input (Website URL)
        │
        ▼
POST /extract-knowledge-base
        │
        ├─► WebsiteToMarkdownPipeline.run()
        │         │
        │         ├─► Discover sitemaps (robots.txt)
        │         │
        │         ├─► Extract all URLs from sitemaps
        │         │
        │         ├─► For each URL:
        │         │     │
        │         │     ├─► Fetch HTML content
        │         │     │
        │         │     ├─► Parse with BeautifulSoup
        │         │     │
        │         │     ├─► Clean & convert to Markdown
        │         │     │
        │         │     └─► Save to knowledge_base/
        │         │
        │         └─► Create INDEX.md
        │
        ▼
MarkdownToVectorDB.init()
        │
        ├─► Read all .md files from knowledge_base/
        │
        ├─► Split texts into chunks (1000 chars)
        │
        ├─► Generate embeddings (SentenceTransformer)
        │
        ├─► Create Qdrant collection
        │
        └─► Upload vectors to Qdrant
              │
              ▼
        Knowledge Base Ready ✅
```

---

### Flow 2: Voice Conversation Setup

```
User clicks "Start Voice Call"
        │
        ▼
POST /token (roomName, userName)
        │
        ├─► Generate unique participant identity
        │
        ├─► Create LiveKit AccessToken
        │     │
        │     ├─► Set identity & name
        │     ├─► Set TTL (2 hours)
        │     └─► Grant permissions (publish, subscribe)
        │
        ├─► Return JWT token + LiveKit URL
        │
        ▼
Client connects to LiveKit Room
        │
        ├─► Enable microphone
        ├─► Setup audio visualizer
        └─► Wait for agent
              │
              ▼
        Agent Worker spawns
              │
              ├─► Initialize AgentSession
              │     │
              │     ├─► STT: Deepgram Nova-3
              │     ├─► LLM: OpenAI GPT-4.1-mini
              │     └─► TTS: Cartesia Sonic-2
              │
              ├─► Connect to room
              │
              ├─► Say greeting
              │
              └─► Listen for user speech
```

---

### Flow 3: Real-time Voice Interaction with RAG

```
User speaks into microphone
        │
        ▼
Audio stream → LiveKit Room
        │
        ▼
Agent receives audio
        │
        ├─► Deepgram STT converts to text
        │
        ▼
Text → LLM (GPT-4.1-mini)
        │
        ├─► LLM analyzes query
        │
        ├─► Decides if RAG lookup needed
        │
        ▼
[If knowledge needed]
        │
        ├─► Call rag_lookup() function
        │         │
        │         ├─► Convert query to embedding
        │         │
        │         ├─► Search Qdrant (cosine similarity)
        │         │
        │         ├─► Retrieve top 5 relevant chunks
        │         │
        │         └─► Return formatted results
        │
        ▼
LLM generates response
        │
        ├─► Incorporates RAG context
        │
        ├─► Formats conversational answer
        │
        ▼
Response text → Cartesia TTS
        │
        ├─► Convert to natural speech
        │
        ▼
Audio stream → User's speakers
        │
        ▼
User hears AI response 🔊
```

---

## Detailed Component Flows

### 1️⃣ FastAPI Backend (`main.py`)

#### Endpoints

**`GET /`** - Health check & info
```python
Returns: Service status, components, available endpoints
```

**`POST /token`** - Generate LiveKit access token
```python
Input:
  - room_name: string
  - participant_name: string

Process:
  1. Generate unique identity (name + random hex)
  2. Create AccessToken with API credentials
  3. Set permissions (publish, subscribe, join)
  4. Generate JWT token

Output:
  - token: JWT string
  - url: LiveKit server URL
  - room_name: string
```

**`POST /extract-knowledge-base`** - Scrape website
```python
Input:
  - website_url: string
  - max_pages: int (default: 50)

Process:
  1. Run WebsiteToMarkdownPipeline in background thread
  2. Scrape website → markdown files
  3. Initialize vector database
  4. Convert markdown → embeddings → Qdrant

Output:
  - status: "completed"
  - message: success message
  - output_dir: "knowledge_base"
```

**`GET /demo`** - Serve interactive HTML page

---

### 2️⃣ Agent Worker (`agent.py`)

#### VoiceAssistant Class

```python
Inherits from: livekit.agents.Agent

Features:
  - System instructions for conversational AI
  - RAG lookup function tool
  - Integration with STT/LLM/TTS

@function_tool: rag_lookup(query, limit=5)
  │
  ├─► Initialize MarkdownToVectorDB
  ├─► Search similar documents
  ├─► Format results with title + text
  └─► Return to LLM as context
```

#### Entry Point Flow

```python
async def entrypoint(ctx: JobContext):
  │
  ├─► Parse room metadata (optional configs)
  │
  ├─► Create AgentSession
  │     ├─► STT: "deepgram/nova-3-general"
  │     ├─► LLM: "openai/gpt-4.1-mini"
  │     ├─► TTS: "cartesia/sonic-2:..."
  │     └─► preemptive_generation: True
  │
  ├─► Setup metrics collection
  │
  ├─► Start session with VoiceAssistant
  │     └─► room_input_options: noise_cancellation
  │
  ├─► Connect to room
  │
  └─► Say initial greeting
```

---

### 3️⃣ Web Scraper (`sitemap.py`)

#### WebsiteToMarkdownPipeline Flow

```python
run(website_url, max_pages):
  │
  ├─► discover_sitemaps(base_url)
  │     ├─► Check robots.txt for sitemap URLs
  │     └─► Try common sitemap locations
  │
  ├─► extract_all_urls(sitemap_url)
  │     ├─► Recursively parse sitemap XML
  │     ├─► Handle sitemap indexes
  │     └─► Collect all page URLs
  │
  ├─► For each URL (up to max_pages):
  │     │
  │     ├─► fetch_url() with rate limiting
  │     │
  │     ├─► clean_html_to_markdown()
  │     │     ├─► Parse with BeautifulSoup
  │     │     ├─► Remove scripts, styles, nav, footer
  │     │     ├─► Find main content area
  │     │     ├─► Convert to markdown (html2text)
  │     │     └─► Add metadata header
  │     │
  │     └─► save_markdown()
  │           ├─► Convert URL to safe filename
  │           ├─► Create directory structure
  │           └─► Write .md file
  │
  └─► create_index()
        └─► Generate INDEX.md with all pages
```

---

### 4️⃣ Vector Database (`vector_db_init.py`)

#### MarkdownToVectorDB Flow

```python
process_markdown_files():
  │
  ├─► extract_all_markdown_texts()
  │     ├─► Scan knowledge_base/ directory
  │     ├─► Read all .md and .markdown files
  │     └─► Return dict {filepath: text}
  │
  ├─► split_texts_into_chunks()
  │     ├─► Use RecursiveCharacterTextSplitter
  │     │     ├─► chunk_size: 1000 characters
  │     │     └─► chunk_overlap: 200 characters
  │     │
  │     └─► Create chunk documents with metadata:
  │           ├─► text (content)
  │           ├─► source (file path)
  │           ├─► title (extracted from markdown)
  │           ├─► chunk_id (unique ID)
  │           └─► char_count, word_count
  │
  ├─► create_embeddings()
  │     ├─► Load SentenceTransformer model
  │     │     └─► "all-MiniLM-L6-v2" (384 dimensions)
  │     │
  │     ├─► Process in batches (32 texts/batch)
  │     └─► Generate numpy embeddings
  │
  ├─► setup_qdrant_collection()
  │     ├─► Connect to Qdrant (localhost:6333)
  │     ├─► Delete existing collection (if exists)
  │     └─► Create new collection with:
  │           ├─► Vector size: 384
  │           └─► Distance metric: COSINE
  │
  └─► upload_to_qdrant()
        ├─► Create PointStruct for each chunk
        │     ├─► id: sequential integer
        │     ├─► vector: embedding array
        │     └─► payload: metadata dict
        │
        └─► Upload in batches (100 points/batch)
```

#### Search Flow

```python
search_similar(query, limit=5):
  │
  ├─► Encode query with SentenceTransformer
  │
  ├─► Search Qdrant with cosine similarity
  │
  └─► Return top results with:
        ├─► text (truncated to 200 chars)
        ├─► score (similarity score)
        ├─► source (original file)
        ├─► title (heading)
        └─► chunk_id
```

---

## 🔄 User Journey

### Scenario: User asks about a product

```
1. User opens demo page at http://localhost:8000/demo
        │
        ▼
┌─────────────────────────────────────────────────┐
│  📚 Knowledge Base Extraction Section           │
│                                                  │
│  Website URL: [https://example.com        ]     │
│  Max Pages:   [50                        ]     │
│                                                  │
│  [🔍 Extract Knowledge Base]  ← User clicks     │
└─────────────────────────────────────────────────┘
        │
        ▼
POST /extract-knowledge-base
  {
    "website_url": "https://example.com",
    "max_pages": 50
  }
        │
        ├─► Status shows: "⏳ Extracting knowledge base..."
        │
        ▼
┌─────────────────────────────────────────────────┐
│         BACKGROUND PROCESSING STARTS            │
│         (User can continue browsing)            │
└─────────────────────────────────────────────────┘
        │
        ├─► WebsiteToMarkdownPipeline.run()
        │     │
        │     ├─► 🔍 Discovering sitemaps...
        │     │     └─► Found sitemap.xml
        │     │
        │     ├─► 📄 Extracting URLs...
        │     │     └─► Found 150 pages (limiting to 50)
        │     │
        │     ├─► 🌐 Scraping pages... (1/50)
        │     │     ├─► Fetching https://example.com/
        │     │     ├─► Converting to Markdown
        │     │     └─► Saved: knowledge_base/index.md
        │     │
        │     ├─► 🌐 Scraping pages... (2/50)
        │     │     └─► Processing...
        │     │
        │     └─► ... continues for all 50 pages
        │
        ▼
vector_db_init.init()
        │
        ├─► 📖 Reading markdown files...
        │     └─► Found 50 .md files
        │
        ├─► ✂️ Splitting into chunks...
        │     └─► Created 342 chunks (1000 chars each)
        │
        ├─► 🧮 Creating embeddings...
        │     ├─► Loading SentenceTransformer model
        │     └─► Generated 342 embeddings (384-dim)
        │
        ├─► 🗄️ Setting up Qdrant collection...
        │     └─► Collection "markdown_knowledge_base" ready
        │
        └─► ⬆️ Uploading to Qdrant...
              └─► Uploaded 342 vectors
        │
        ▼
┌─────────────────────────────────────────────────┐
│  ✅ Success Message Appears:                    │
│                                                  │
│  "Successfully extracted knowledge base from    │
│   https://example.com and pushed to vectorDB"  │
│                                                  │
│  Output saved to: knowledge_base                │
└─────────────────────────────────────────────────┘

2. Connection Phase
   ├─► User opens demo page
   ├─► Enters room name & username
   ├─► Clicks "Start Voice Call"
   ├─► Gets LiveKit token
   ├─► Connects to room
   └─► Agent joins and greets

3. Conversation Phase
   ├─► User: "What's your best IEM under $100?"
   │
   ├─► STT transcribes to text
   │
   ├─► LLM analyzes query
   │     └─► Determines RAG needed
   │
   ├─► rag_lookup("best IEM under $100", limit=5)
   │     ├─► Query embedding created
   │     ├─► Qdrant searches vectors
   │     ├─► Returns 5 relevant chunks about IEMs
   │     └─► Formatted context returned
   │
   ├─► LLM generates answer using RAG context
   │     └─► "Based on our catalog, I'd recommend..."
   │
   ├─► TTS converts to speech
   │
   └─► User hears natural response

4. Follow-up Questions
   └─► Process repeats with conversation history
```

---

## 🔧 Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI | REST API server |
| **Voice Platform** | LiveKit | Real-time audio/video |
| **STT** | Deepgram Nova-3 | Speech-to-text |
| **LLM** | OpenAI GPT-4.1-mini | Conversational AI |
| **TTS** | Cartesia Sonic-2 | Text-to-speech |
| **Embeddings** | SentenceTransformer | Vector representation |
| **Vector DB** | Qdrant | Similarity search |
| **Scraping** | BeautifulSoup | HTML parsing |
| **Markdown** | html2text | HTML → Markdown |
| **Text Splitting** | LangChain | Chunking strategy |

---

##  Key Design Patterns

1. **Microservices Architecture**: Separate FastAPI backend and Agent worker
3. **Function Calling**: LLM triggers `rag_lookup()` when needed
4. **Streaming Audio**: Real-time bidirectional voice communication
5. **Vector Similarity Search**: Semantic retrieval from knowledge base
6. **Metadata Enrichment**: Store source, title, and context with vectors
7. **Preemptive Generation**: Agent starts generating while user speaks
8. **Rate Limiting**: Controlled website scraping (1s delay)
9. **Noise Cancellation**: Background voice cancellation (BVC)
11. **Async Operations**: Non-blocking knowledge base extraction
