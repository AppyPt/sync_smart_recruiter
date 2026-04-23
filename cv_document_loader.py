"""
CV Document Loader and Segmenter Module (LangChain)

This module provides functions to load documents (specifically PDFs for CVs)
and segment their text content using LangChain components.
"""

from typing import List, Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def load_pdf_documents(file_path: str) -> List[Document]:
    """
    Loads a PDF file and returns its content as a list of LangChain Documents.
    Each page of the PDF is typically treated as a separate Document by PyPDFLoader.

    Args:
        file_path: The absolute path to the PDF file.

    Returns:
        A list of LangChain Document objects, where each Document represents a page
        or the entire content if structured that way by the loader.

    Raises:
        FileNotFoundError: If the PDF file does not exist (handled by PyPDFLoader).
        Exception: Any exception raised by PyPDFLoader during loading.
    """
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load() # Returns a list of Document objects
        if not documents:
            # This case might occur if the PDF is empty or unreadable in a way that returns no docs
            print(f"Warning: No documents were loaded from PDF: {file_path}. The PDF might be empty or corrupted.")
            return []
        # print(f"Loaded {len(documents)} document(s) from {file_path}.")
        # for i, doc in enumerate(documents):
        #     print(f"  Document {i} (Page {doc.metadata.get("page", "N/A") if doc.metadata else "N/A"}) - Chars: {len(doc.page_content)}")
        return documents
    except FileNotFoundError:
        raise # Re-raise FileNotFoundError to be explicit
    except Exception as e:
        # Catch other potential errors from PyPDFLoader (e.g., malformed PDF)
       raise RuntimeError(f"Failed to load PDF '{file_path}'. Error: {e}")
def split_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: Optional[List[str]] = None,
    keep_separator: bool = True
) -> List[Document]:
    """
    Splits a list of LangChain Documents into smaller chunks using RecursiveCharacterTextSplitter.

    Args:
        documents: A list of LangChain Document objects to be split.
        chunk_size: The maximum size of each chunk (in characters).
        chunk_overlap: The number of characters to overlap between consecutive chunks.
        separators: (Optional) A list of strings to use as separators, in order of preference.
                    If None, RecursiveCharacterTextSplitter uses its default separators.
        keep_separator: Whether to keep the separators in the chunks.

    Returns:
        A list of LangChain Document objects, representing the smaller text chunks.
        Metadata from the original documents is typically preserved in the chunks.
    """
    if not documents:
        # print("Warning: No documents provided to split_documents. Returning empty list.")
        return []

    if separators is None:
        # Default separators from LangChain documentation, can be customized
        separators = ["\n\n", "\n", " ", ""]

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False, # Treat separators as literal strings
        separators=separators,
        keep_separator=keep_separator
    )

    split_docs = text_splitter.split_documents(documents)
    # print(f"Split {len(documents)} document(s) into {len(split_docs)} chunks.")
    # for i, chunk_doc in enumerate(split_docs):
    #     print(f"  Chunk {i} - Chars: {len(chunk_doc.page_content)}, Metadata: {chunk_doc.metadata}")
    return split_docs

# Example Usage (commented out - for agent testing or direct script run)
# if __name__ == "__main__":
#     import os
#     # This example requires fpdf2 to create a dummy PDF: pip install fpdf2
#     # And langchain_community for PyPDFLoader: pip install langchain-community
#     try:
#         from fpdf import FPDF
#         dummy_pdf_path = "/tmp/dummy_cv_langchain.pdf"
#         pdf = FPDF()
#         pdf.add_page()
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt="Curriculum Vitae of Jane Smith.\n\nProfessional Experience:\n- Lead Data Scientist at Innovate Corp. (2021-Present)\n  - Developed machine learning models for predictive analytics.\n  - Managed a team of 3 data analysts.\n\n- Software Engineer at Tech Solutions (2019-2021)\n  - Worked on backend development using Python and Django.\n\nSkills:\n- Python, R, SQL, Machine Learning, Deep Learning, NLP, Django, Flask, AWS, Docker.")
#         pdf.add_page()
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt="Education:\n- M.Sc. in Data Science, Major University (2019)\n- B.Sc. in Computer Engineering, State College (2017)\n\nPublications:\n- Smith, J. (2020). A Novel Approach to Anomaly Detection. Journal of Data Science.")
#         pdf.output(dummy_pdf_path, "F")
#         print(f"Dummy PDF created at {dummy_pdf_path}")

#         print("\n--- Testing PDF Loading ---")
#         loaded_docs = load_pdf_documents(dummy_pdf_path)
#         if loaded_docs:
#             print(f"Successfully loaded {len(loaded_docs)} documents (pages) from the PDF.")
#             for i, doc in enumerate(loaded_docs):
#                 print(f"  Document {i+1} (Page {doc.metadata.get("page", "N/A")}): {len(doc.page_content)} characters.")
#                 # print(f"    Content snippet: {doc.page_content[:100].replace("\n", " ")}...")
        
#             print("\n--- Testing Document Splitting ---")
#             # Using smaller chunk_size for demo to see more chunks
#             chunked_documents = split_documents(loaded_docs, chunk_size=200, chunk_overlap=30)
#             print(f"Split into {len(chunked_documents)} chunks.")
#             for i, chunk in enumerate(chunked_documents):
#                 print(f"  Chunk {i+1} (Source Page: {chunk.metadata.get("page", "N/A")}): {len(chunk.page_content)} characters.")
#                 # print(f"    Chunk content snippet: {chunk.page_content[:80].replace("\n", " ")}...")
#         else:
#             print("No documents were loaded, skipping splitting test.")

#     except ImportError as ie:
#         print(f"ImportError: {ie}. Please ensure fpdf2 and langchain-community are installed for this example.")
#     except RuntimeError as re:
#         print(f"RuntimeError: {re}")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#     # finally:
#     #     if os.path.exists(dummy_pdf_path):
#     #         # os.remove(dummy_pdf_path)
#     #         # print(f"\nCleaned up dummy PDF: {dummy_pdf_path}")
#     #         pass # Keep for inspection

