"""
Embedding Generation and Vector Store Module (LangChain)

This module provides functions to generate text embeddings using LangChain's HuggingFaceEmbeddings
(suitable for local SentenceTransformer models) and to create/manage a FAISS vector store
for efficient similarity search on LangChain Documents.
"""

from typing import List, Optional

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import os # For saving/loading FAISS index


def create_embedding_function(
    model_name: str = "all-MiniLM-L6-v2", 
    model_kwargs: Optional[dict] = None,
    encode_kwargs: Optional[dict] = None
) -> HuggingFaceEmbeddings:
    """
    Creates and returns a LangChain HuggingFaceEmbeddings object for generating embeddings.
    This wrapper can use SentenceTransformer models locally.

    Args:
        model_name: The name of the SentenceTransformer model from HuggingFace Model Hub
                    (e.g., 'all-MiniLM-L6-v2', 'sentence-transformers/all-mpnet-base-v2').
        model_kwargs: (Optional) Dictionary of keyword arguments to pass to the model.
                      Example: {"device": "cuda"} for GPU usage if available.
        encode_kwargs: (Optional) Dictionary of keyword arguments to pass to the encode method.
                       Example: {"normalize_embeddings": True}.

    Returns:
        An instance of HuggingFaceEmbeddings.

    Raises:
        ImportError: If sentence_transformers or other dependencies are not installed.
        Exception: If the model fails to load.
    """
    if model_kwargs is None:
        model_kwargs = {"device": "cpu"} # Default to CPU, can be changed
    if encode_kwargs is None:
        encode_kwargs = {"normalize_embeddings": True} # Normalization is good for cosine similarity

    try:
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        # Test if the embedding function is working by embedding a dummy text
        # This also helps in getting the embedding dimension if needed elsewhere, though FAISS handles it.
        # _ = embeddings.embed_query("test") 
        # print(f"Successfully initialized HuggingFaceEmbeddings with model: {model_name}")
        return embeddings
    except ImportError as ie:
        raise ImportError(f"Failed to import HuggingFaceEmbeddings or its dependencies (likely sentence_transformers). Error: {ie}. Please ensure 'pip install langchain-community sentence-transformers' is run.")
    except Exception as e:
        raise RuntimeError(f"Failed to load or initialize HuggingFaceEmbeddings model '{model_name}'. Error: {e}")

def create_faiss_vectorstore(
    documents: List[Document],
    embedding_function: HuggingFaceEmbeddings,
    index_path: Optional[str] = None
) -> FAISS:
    """
    Creates a FAISS vector store from a list of LangChain Documents and an embedding function.
    If an index_path is provided and exists, it attempts to load the index; otherwise, it creates a new one.

    Args:
        documents: A list of LangChain Document objects (e.g., text chunks from a CV).
        embedding_function: An initialized LangChain embedding function (e.g., HuggingFaceEmbeddings).
        index_path: (Optional) Path to save the FAISS index to or load from. 
                    If None, the index is created in memory.

    Returns:
        An instance of LangChain's FAISS vector store.

    Raises:
        ValueError: If documents list is empty and no existing index_path is provided to load from.
        Exception: Any exception raised during FAISS index creation or loading.
    """
    if not documents and (index_path is None or not os.path.exists(f"{index_path}.faiss")):
        raise ValueError("Documents list cannot be empty if not loading an existing FAISS index.")

    if index_path and os.path.exists(f"{index_path}.faiss") and os.path.exists(f"{index_path}.pkl"):
        try:
            # print(f"Loading existing FAISS index from: {index_path}")
            vector_store = FAISS.load_local(folder_path=os.path.dirname(index_path), embeddings=embedding_function, index_name=os.path.basename(index_path), allow_dangerous_deserialization=True)
            # print(f"Successfully loaded FAISS index with {vector_store.index.ntotal} vectors.")
            # If new documents are provided, you might want to add them to the loaded index:
            if documents:
                # print(f"Adding {len(documents)} new documents to the loaded FAISS index.")
                vector_store.add_documents(documents)
                if index_path: # Re-save if new documents were added
                    vector_store.save_local(folder_path=os.path.dirname(index_path), index_name=os.path.basename(index_path))
                    # print(f"Re-saved FAISS index to {index_path} after adding new documents.")
            return vector_store
        except Exception as e:
            raise RuntimeError(f"Failed to load FAISS index from '{index_path}'. Error: {e}. Will attempt to create a new one.")
    
    # Create a new index if no path or existing index found, or if loading failed
    if not documents:
        # This case should ideally be caught earlier or handled by ensuring documents are always present for new index creation.
        raise ValueError("Cannot create a new FAISS index with an empty list of documents.")

    try:
        # print(f"Creating new FAISS index from {len(documents)} documents...")
        vector_store = FAISS.from_documents(documents=documents, embedding=embedding_function)
        # print(f"Successfully created FAISS index with {vector_store.index.ntotal} vectors.")
        if index_path:
            vector_store.save_local(folder_path=os.path.dirname(index_path), index_name=os.path.basename(index_path))
            # print(f"Saved FAISS index to: {index_path}")
        return vector_store
    except Exception as e:
        raise RuntimeError(f"Failed to create FAISS vector store. Error: {e}")

# Example Usage (commented out - for agent testing or direct script run)
# if __name__ == "__main__":
#     # This example requires fpdf2, langchain-community, sentence-transformers, faiss-cpu
#     from cv_document_loader import load_pdf_documents, split_documents # Assuming it's in the same directory
#     try:
#         from fpdf import FPDF
#         dummy_pdf_path = "/tmp/dummy_cv_langchain_faiss.pdf"
#         # Create a dummy PDF
#         pdf = FPDF()
#         pdf.add_page()
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt="John Doe - Python Expert. Experienced in Django and Flask for web development. Also skilled in data analysis with Pandas and NumPy. Interested in machine learning roles.")
#         pdf.add_page()
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt="Jane Smith - Java Specialist. Proficient in Spring Boot and microservices architecture. Strong background in SQL databases and cloud platforms like AWS.")
#         pdf.output(dummy_pdf_path, "F")
#         print(f"Dummy PDF created at {dummy_pdf_path}")

#         # 1. Load and split documents
#         print("\n--- Loading and Splitting PDF ---")
#         raw_docs = load_pdf_documents(dummy_pdf_path)
#         chunked_docs = split_documents(raw_docs, chunk_size=150, chunk_overlap=20)
#         if not chunked_docs:
#             print("No documents were chunked. Exiting.")
#             exit()
#         print(f"PDF split into {len(chunked_docs)} chunks.")

#         # 2. Create embedding function
#         print("\n--- Creating Embedding Function ---")
#         # Using a small, fast model for testing. Ensure it's available or SentenceTransformers can download it.
#         # For a truly offline test, the model would need to be pre-downloaded.
#         embedding_model_name = "all-MiniLM-L6-v2"
#         embeddings = create_embedding_function(model_name=embedding_model_name, encode_kwargs={"normalize_embeddings": True})
#         print(f"Embedding function created with model: {embedding_model_name}")

#         # 3. Create FAISS Vector Store (in memory for this example)
#         print("\n--- Creating FAISS Vector Store (In-Memory) ---")
#         vector_store_memory = create_faiss_vectorstore(documents=chunked_docs, embedding_function=embeddings)
#         print(f"In-memory FAISS store created with {vector_store_memory.index.ntotal} vectors.")

#         # Perform a similarity search (example)
#         query = "Python and Django experience"
#         print(f"\nPerforming similarity search for query: 	"{query}	"...")
#         results = vector_store_memory.similarity_search_with_score(query, k=2)
#         for doc, score in results:
#             print(f"  Score: {score:.4f} (Higher is more similar with normalized embeddings and default FAISS IP)")
#             print(f"  Content: {doc.page_content[:100].replace(	"\n	", 	" 	")}...")
#             print(f"  Metadata: {doc.metadata}")

#         # 4. Create/Load FAISS Vector Store (with persistence)
#         faiss_index_dir = "/tmp/my_faiss_index_lc"
#         faiss_index_name = "cv_index"
#         full_faiss_path = os.path.join(faiss_index_dir, faiss_index_name)
#         if not os.path.exists(faiss_index_dir):
#             os.makedirs(faiss_index_dir)
        
#         print(f"\n--- Creating/Loading FAISS Vector Store (Persistent at {full_faiss_path}) ---")
#         # First time, it will create and save. Subsequent runs (if files exist) will load.
#         vector_store_persistent = create_faiss_vectorstore(
#             documents=chunked_docs, # Provide documents for initial creation or if you want to add them
#             embedding_function=embeddings,
#             index_path=full_faiss_path
#         )
#         print(f"Persistent FAISS store ready with {vector_store_persistent.index.ntotal} vectors.")
        
#         # Test search on persistent store
#         query2 = "Java and Spring Boot"
#         print(f"\nPerforming similarity search on persistent store for query: 	"{query2}	"...")
#         results_persistent = vector_store_persistent.similarity_search_with_score(query2, k=2)
#         for doc, score in results_persistent:
#             print(f"  Score: {score:.4f}")
#             print(f"  Content: {doc.page_content[:100].replace(	"\n	", 	" 	")}...")

#         # Example of loading again (simulating a new session)
#         if os.path.exists(f"{full_faiss_path}.faiss"):
#             print("\n--- Simulating Load of Persistent FAISS Vector Store ---")
#             # Pass empty documents list if you only want to load and not add new ones initially
#             vector_store_loaded = create_faiss_vectorstore(
#                 documents=[], 
#                 embedding_function=embeddings, 
#                 index_path=full_faiss_path
#             )
#             print(f"Loaded persistent FAISS store with {vector_store_loaded.index.ntotal} vectors.")
#             results_loaded = vector_store_loaded.similarity_search("AWS cloud skills", k=1)
#             if results_loaded:
#                 print(f"Search result from loaded index: {results_loaded[0].page_content[:100]}...")

#     except ImportError as ie:
#         print(f"ImportError: {ie}. Please ensure all dependencies are installed (fpdf2, langchain-community, sentence-transformers, faiss-cpu).")
#     except RuntimeError as re:
#         print(f"RuntimeError: {re}")
#     except Exception as e:
#         import traceback
#         print(f"An unexpected error occurred: {e}")
#         traceback.print_exc()
#     finally:
#         # Clean up dummy files and directories for the example
#         if os.path.exists(dummy_pdf_path):
#             # os.remove(dummy_pdf_path)
#             pass # Keep for inspection
#         if os.path.exists(faiss_index_dir):
#             # import shutil
#             # shutil.rmtree(faiss_index_dir)
#             pass # Keep for inspection
#         print("\nExample finished. Check /tmp for artifacts if not cleaned up.")

