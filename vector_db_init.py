import os
import logging
from typing import List, Dict, Any
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarkdownToVectorDB:
    def __init__(self, 
                 knowledge_base_dir: str = "knowledge_base",
                 collection_name: str = "markdown_knowledge_base",
                 model_name: str = "all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """
        Initialize the Markdown to Vector DB converter
        
        Args:
            knowledge_base_dir: Path to directory containing markdown files
            collection_name: Name for the Qdrant collection
            model_name: Sentence transformer model name
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.collection_name = collection_name
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize components
        logger.info(f"Loading embedding model: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        
        # Initialize Qdrant client (in-memory for this example)
        self.qdrant_client = QdrantClient(url="http://localhost:6333")
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

    def get_markdown_files(self) -> List[Path]:
        """Get all markdown files from the knowledge base directory"""
        if not self.knowledge_base_dir.exists():
            raise FileNotFoundError(f"Directory not found: {self.knowledge_base_dir}")
        
        md_extensions = ['.md', '.markdown']
        md_files = []
        
        for ext in md_extensions:
            md_files.extend(self.knowledge_base_dir.rglob(f"*{ext}"))
        
        logger.info(f"Found {len(md_files)} markdown files in {self.knowledge_base_dir}")
        return sorted(md_files)

    def extract_text_from_markdown(self, file_path: Path) -> str:
        """Extract text from a markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return text
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return ""

    def extract_all_markdown_texts(self) -> Dict[str, str]:
        """Extract text from all markdown files"""
        logger.info("Extracting text from markdown files")
        
        md_files = self.get_markdown_files()
        markdown_texts = {}
        
        for md_file in tqdm(md_files, desc="Reading markdown files"):
            text = self.extract_text_from_markdown(md_file)
            if text.strip():
                # Use relative path as key
                rel_path = md_file.relative_to(self.knowledge_base_dir)
                markdown_texts[str(rel_path)] = text
        
        total_chars = sum(len(text) for text in markdown_texts.values())
        logger.info(f"Extracted {total_chars} characters from {len(markdown_texts)} files")
        
        return markdown_texts

    def split_texts_into_chunks(self, markdown_texts: Dict[str, str]) -> List[Dict[str, Any]]:
        """Split texts into chunks with metadata"""
        logger.info("Splitting texts into chunks")
        
        all_chunks = []
        chunk_id = 0
        
        for file_path, text in markdown_texts.items():
            chunks = self.text_splitter.split_text(text)
            
            for chunk in chunks:
                # Extract title from markdown (first # heading if exists)
                title = self._extract_title_from_chunk(chunk)
                
                chunk_doc = {
                    "text": chunk.strip(),
                    "chunk_id": chunk_id,
                    "source": file_path,
                    "title": title,
                    "char_count": len(chunk),
                    "word_count": len(chunk.split())
                }
                all_chunks.append(chunk_doc)
                chunk_id += 1
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(markdown_texts)} files")
        return all_chunks

    def _extract_title_from_chunk(self, chunk: str) -> str:
        """Extract the first heading from a markdown chunk"""
        lines = chunk.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Remove markdown heading symbols
                title = line.lstrip('#').strip()
                if title:
                    return title
        return "No title"

    def create_embeddings(self, chunks: List[Dict[str, Any]]) -> List[np.ndarray]:
        """Create embeddings for text chunks"""
        logger.info("Creating embeddings")
        
        texts = [chunk["text"] for chunk in chunks]
        
        # Create embeddings in batches for efficiency
        batch_size = 32
        embeddings = []
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Creating embeddings"):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self.embedding_model.encode(
                batch_texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            embeddings.extend(batch_embeddings)
        
        logger.info(f"Created {len(embeddings)} embeddings with dimension {len(embeddings[0])}")
        return embeddings

    def setup_qdrant_collection(self, vector_size: int):
        """Setup Qdrant collection"""
        logger.info(f"Setting up Qdrant collection: {self.collection_name}")
        
        try:
            # Try to delete existing collection
            self.qdrant_client.delete_collection(collection_name=self.collection_name)
            logger.info("Deleted existing collection")
        except:
            pass  # Collection might not exist
        
        # Create new collection
        self.qdrant_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        
        logger.info("Created new collection successfully")

    def upload_to_qdrant(self, chunks: List[Dict[str, Any]], embeddings: List[np.ndarray]):
        """Upload chunks and embeddings to Qdrant"""
        logger.info("Uploading to Qdrant")
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=i,
                vector=embedding.tolist(),
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "chunk_id": chunk["chunk_id"],
                    "char_count": chunk["char_count"],
                    "word_count": chunk["word_count"]
                }
            )
            points.append(point)
        
        # Upload in batches
        batch_size = 100
        for i in tqdm(range(0, len(points), batch_size), desc="Uploading to Qdrant"):
            batch_points = points[i:i + batch_size]
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=batch_points
            )
        
        logger.info(f"Successfully uploaded {len(points)} points to Qdrant")

    def process_markdown_files(self):
        """Main method to process markdown files and create vector database"""
        try:
            # Step 1: Extract text from all markdown files
            markdown_texts = self.extract_all_markdown_texts()
            
            if not markdown_texts:
                logger.error("No markdown files found or all files are empty")
                return False
            
            # Step 2: Split into chunks
            chunks = self.split_texts_into_chunks(markdown_texts)
            
            # Step 3: Create embeddings
            embeddings = self.create_embeddings(chunks)
            
            # Step 4: Setup Qdrant collection
            vector_size = len(embeddings[0])
            self.setup_qdrant_collection(vector_size)
            
            # Step 5: Upload to Qdrant
            self.upload_to_qdrant(chunks, embeddings)
            
            logger.info("✅ Markdown processing completed successfully!")
            
            # Print summary
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            print(f"\n📊 Summary:")
            print(f"   📁 Source directory: {self.knowledge_base_dir}")
            print(f"   📄 Markdown files processed: {len(markdown_texts)}")
            print(f"   🔢 Total chunks: {len(chunks)}")
            print(f"   📏 Vector dimension: {vector_size}")
            print(f"   🗃️  Collection: {self.collection_name}")
            print(f"   💾 Points in DB: {collection_info.points_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing markdown files: {e}")
            return False

    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for similar text chunks"""
        query_embedding = self.embedding_model.encode([query])
        
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding[0].tolist(),
            limit=limit
        )
        
        results = []
        for hit in search_result:
            results.append({
                "text": hit.payload["text"][:200] + "..." if len(hit.payload["text"]) > 200 else hit.payload["text"],
                "score": hit.score,
                "source": hit.payload["source"],
                "title": hit.payload["title"],
                "chunk_id": hit.payload["chunk_id"]
            })
        
        return results

def init():
    converter = MarkdownToVectorDB(
    knowledge_base_dir="knowledge_base",
    collection_name="markdown_knowledge_base"
    )
    success = converter.process_markdown_files()
    
    if success:
        print("\n🎉 Success! Your knowledge base is now in a vector database!")
    return success,converter

def main():
    """Main function"""
    print("📚 Markdown Knowledge Base to Vector Database Converter")
    print("=" * 60)
    
    # Initialize converter
    success,converter = init()
    
    if success:
        print("\n🎉 Success! Your knowledge base is now in a vector database!")
        print("\nTesting search functionality...")
        
        # Test search
        test_queries = [
            "best iem?",
            "cheapest iem?"
        ]
        
        for query in test_queries:
            results = converter.search_similar(query, limit=10)
            print(f"\n🔍 Search: '{query}'")
            list_all_answer=""
            results = converter.search_similar(query, limit=10)
            for i, result in enumerate(results, 5):
                list_all_answer+="Title: {result['title']}\n"+"text : {result['text']}\n"
    else:
        print("❌ Failed to process markdown files")

if __name__ == "__main__":
    main()