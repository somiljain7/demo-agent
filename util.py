from pathlib import Path
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, SummaryIndex
from llama_index.core.tools import QueryEngineTool
import logging

logger = logging.getLogger(__name__)


def get_doc_tools(file_path: Path, name: str):
    """
    Create vector search and summary tools for a specific document.
    
    Args:
        file_path: Path to the document file
        name: Name identifier for the tools
        
    Returns:
        tuple: (vector_tool, summary_tool)
    """
    try:
        # Load the document
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        
        if not documents:
            logger.warning(f"No documents loaded from {file_path}")
            return None, None
        
        # Create a vector index for semantic search
        vector_index = VectorStoreIndex.from_documents(documents)
        
        # Create a summary index for document summaries
        summary_index = SummaryIndex.from_documents(documents)
        
        # Create query engines
        vector_query_engine = vector_index.as_query_engine()
        summary_query_engine = summary_index.as_query_engine()
        
        # Create tools with descriptive names and descriptions
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=vector_query_engine,
            name=f"vector_tool_{name}",
            description=f"Useful for retrieving specific information and answering questions about {name}. "
                       f"Use this for detailed queries about the content of {file_path.name}."
        )
        
        summary_tool = QueryEngineTool.from_defaults(
            query_engine=summary_query_engine,
            name=f"summary_tool_{name}",
            description=f"Useful for getting a high-level summary or overview of {name}. "
                       f"Use this to understand the main topics and structure of {file_path.name}."
        )
        
        logger.info(f"Created tools for {file_path.name}")
        return vector_tool, summary_tool
        
    except Exception as e:
        logger.error(f"Error creating tools for {file_path}: {e}")
        raise


def get_doc_tools_with_metadata(file_path: Path, name: str, custom_metadata: dict = None):
    """
    Create vector search and summary tools with custom metadata.
    
    Args:
        file_path: Path to the document file
        name: Name identifier for the tools
        custom_metadata: Optional dictionary of custom metadata to attach to documents
        
    Returns:
        tuple: (vector_tool, summary_tool)
    """
    try:
        # Load the document
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        
        if not documents:
            logger.warning(f"No documents loaded from {file_path}")
            return None, None
        
        # Add custom metadata if provided
        if custom_metadata:
            for doc in documents:
                doc.metadata.update(custom_metadata)
        
        # Create indices
        vector_index = VectorStoreIndex.from_documents(documents)
        summary_index = SummaryIndex.from_documents(documents)
        
        # Create query engines
        vector_query_engine = vector_index.as_query_engine()
        summary_query_engine = summary_index.as_query_engine(
            response_mode="tree_summarize"
        )
        
        # Create tools
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=vector_query_engine,
            name=f"vector_tool_{name}",
            description=f"Useful for retrieving specific information and answering questions about {name}. "
                       f"Use this for detailed queries about the content of {file_path.name}."
        )
        
        summary_tool = QueryEngineTool.from_defaults(
            query_engine=summary_query_engine,
            name=f"summary_tool_{name}",
            description=f"Useful for getting a high-level summary or overview of {name}. "
                       f"Use this to understand the main topics and structure of {file_path.name}."
        )
        
        logger.info(f"Created tools with metadata for {file_path.name}")
        return vector_tool, summary_tool
        
    except Exception as e:
        logger.error(f"Error creating tools for {file_path}: {e}")
        raise


def create_query_tool_from_index(index, name: str, description: str):
    """
    Create a query tool from an existing index.
    
    Args:
        index: LlamaIndex vector or summary index
        name: Tool name
        description: Tool description
        
    Returns:
        QueryEngineTool
    """
    query_engine = index.as_query_engine()
    
    tool = QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=name,
        description=description
    )
    
    return tool