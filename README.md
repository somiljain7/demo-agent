### Voice Assistant with LiveKit and Sitemap Scraping

This project implements an intelligent voice assistant for e-commerce websites using LiveKit for real-time voice communication and a robust sitemap scraping system for knowledge base creation. The system is designed to respect website scraping limits while providing comprehensive product information to users.

## System Components

### 1. Backend Server (`backend.py`)
- FastAPI server handling token generation and LiveKit room management
- Endpoints:
  - `/token`: Generate access tokens for LiveKit rooms
  - `/extract-knowledge-base`: Initiate website scraping for knowledge base creation
  - `/demo`: Demo page for testing the voice assistant

### 2. Voice Assistant Agent (`agent.py`)
- Implements LiveKit agent for voice interaction
- Features:
  - Natural language processing using GPT models
  - Speech-to-text using Deepgram
  - Text-to-speech using Cartesia
  - RAG (Retrieval Augmented Generation) for context-aware responses
  - Noise cancellation for better voice quality

### 3. Website Scraping System (`sitemap.py`)
-  sitemap discovery and scraping with built-in protections:
  - Rate limiting and delay between requests
  - Configurable page limit to prevent excessive scraping
  - Robust error handling and retry mechanisms
  - Support for robots.txt compliance

## Knowledge Base Creation Flow

1. **Sitemap Discovery**
   ```python
   sitemaps = pipeline.discover_sitemaps(website_url)
   ```
   - Checks robots.txt for sitemap locations
   - Tries common sitemap paths
   - Handles multiple sitemap formats

2. **Protected Scraping**
   - Implements rate limiting:
     ```python
     time.sleep(delay)  # Rate limiting between requests
     ```
   - Respects max pages limit:
     ```python
     if max_pages:
         all_urls = all_urls[:max_pages]
     ```
   - User-agent identification for transparency

3. **Content Processing**
   - Converts HTML to clean Markdown
   - Preserves essential product information
   - Creates structured knowledge base files

## E-commerce Protection Measures

1. **Rate Limiting**
   - Configurable delay between requests
   - Session-based requests to maintain consistency
   - Automatic throttling on detection of rate limits

2. **Page Limitations**
   - Default demo limit of 5 pages
   - Configurable max_pages parameter
   - Prioritizes important product pages

3. **Respectful Scraping**
   - Follows robots.txt directives
   - Uses proper user-agent identification
   - Implements progressive backoff on errors

## Voice Assistant Integration

1. **Knowledge Base Integration**
   ```python
   async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
       rag_content = my_rag_lookup(new_message.text_content)
       turn_ctx.add_message(role="assistant", content=f"Additional information: {rag_content}")
   ```

2. **Real-time Voice Interaction**
   - Low-latency responses using LiveKit
   - Background noise cancellation
   - Natural conversation flow

## Getting Started

1. **Environment Setup**
   ```bash
   # Create a .env file with:
   LIVEKIT_URL=your_livekit_url
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Start Vector Database (Qdrant)**

   ```bash
   # Run Qdrant using Docker with persistent storage
   docker run -d \
     -p 6333:6333 \
     -p 6334:6334 \
     -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
     qdrant/qdrant
   ```

4. **Run the System**

   ```bash
   # Start the backend server
   python backend.py

   # Start the agent
   python agent.py
   ```



## Limitations and Protections

1. **E-commerce Site Limitations**
   - Many large e-commerce sites block aggressive scraping
   - Some sitemaps may require authentication
   - Dynamic content may not be captured

2. **System Protections**
   - Maximum page limit enforcement
   - Request rate limiting
   - Error handling and logging
   - Session management

3. **Recommendations**
   - Start with small page limits for testing
   - Increase limits gradually if needed
   - Monitor site's robots.txt for changes
   - Respect website's scraping policies

## Best Practices

1. **Responsible Scraping**
   - Always set reasonable page limits
   - Implement sufficient delays between requests
   - Monitor and log all scraping activities
   - Respect robots.txt and site policies

2. **Knowledge Base Management**
   - Regularly update scraped content
   - Remove outdated product information
   - Maintain structured data format
   - Backup knowledge base regularly

## Error Handling

The system includes comprehensive error handling for:

- Failed requests
- Rate limiting responses
- Malformed sitemaps
- Invalid URLs
- Connection timeouts

## Future Improvements

- Add support for authenticated sitemaps
- Implement adaptive rate limiting
- Enhance content prioritization
- Add support for dynamic content
- Improve error recovery mechanisms

