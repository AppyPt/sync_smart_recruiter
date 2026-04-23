"""
Semantic Search and Ranking Module (LangChain)

This module provides functionalities to:
1. Perform semantic similarity search using a FAISS vector store and keyword embeddings.
2. Process, rank, and filter the search results based on similarity scores and keyword priorities.
3. Aggregate the ranked matches by category for further analysis.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import os  # Added for os.linesep
import traceback  # For error logging

from langchain_community.vectorstores import FAISS  # For type hinting, actual instance passed
from langchain_core.documents import Document  # For type hinting

class SemanticSearchAndRanker:
    """Handles semantic search in a FAISS vector store and ranks the results."""

    def __init__(self, cv_vector_store: FAISS):
        """
        Initializes the SemanticSearchAndRanker.

        Args:
            cv_vector_store: An initialized LangChain FAISS vector store containing CV document chunks.
        """
        if not isinstance(cv_vector_store, FAISS):
            raise TypeError("cv_vector_store must be an instance of langchain_community.vectorstores.FAISS")
        self.cv_vector_store = cv_vector_store

    def find_semantic_matches(
        self,
        extracted_keywords_data: List[Dict[str, Any]],  # List of {"keyword": str, "category": str, "priority": str}
        keyword_embeddings_map: Dict[str, np.ndarray],  # Map of keyword_text to its embedding vector
        k_neighbors: int = 3,
        similarity_threshold: Optional[float] = 0.5,  # For cosine similarity with normalized embeddings (0 to 1)
        debug_target_cv_filename: Optional[str] = None  # New parameter for debugging
    ) -> List[Dict[str, Any]]:
        """
        Finds CV chunks semantically similar to the provided keyword embeddings.

        Args:
            extracted_keywords_data: A list of dictionaries, where each dictionary contains information
                                     about an extracted keyword (text, category, priority).
            keyword_embeddings_map: A dictionary mapping unique keyword strings to their numpy embeddings.
            k_neighbors: The number of nearest CV chunks to retrieve for each keyword.
            similarity_threshold: (Optional) Minimum similarity score for a match to be considered.
                                  Assumes embeddings are normalized and FAISS uses inner product (cosine similarity).
                                  If None, all k_neighbors are returned before ranking.

        Returns:
            A list of dictionaries, where each dictionary represents a raw match and includes:
            - "keyword": The matched keyword string.
            - "keyword_category": Category of the keyword.
            - "keyword_priority": Priority of the keyword.
            - "cv_document": The LangChain Document object of the matched CV chunk.
            - "similarity_score": The similarity score (e.g., cosine similarity).
        """
        if not extracted_keywords_data:
            print("SSR_DEBUG: No extracted keywords data provided for semantic search.")
            return []
        if not keyword_embeddings_map:
            print("SSR_DEBUG: No keyword embeddings map provided for semantic search.")
            return []

        all_raw_matches = []
        print(f"SSR_DEBUG: Starting semantic search. k_neighbors={k_neighbors}, similarity_threshold={similarity_threshold}")
        if debug_target_cv_filename:
            print(f"SSR_DEBUG: Looking specifically for mentions of CV '{debug_target_cv_filename}' in logs.")

        for keyword_info in extracted_keywords_data:
            keyword_text = keyword_info.get("keyword")
            keyword_category = keyword_info.get("category", "unknown")
            keyword_priority = keyword_info.get("priority", "low")

            if not keyword_text or keyword_text not in keyword_embeddings_map:
                print(f"SSR_DEBUG: Keyword '{keyword_text}' has no embedding or is invalid. Skipping.")
                continue

            query_embedding = keyword_embeddings_map[keyword_text]
            print(f"SSR_DEBUG: Searching for KW: '{keyword_text}' (Cat: {keyword_category}, Prio: {keyword_priority}). Embedding (first 3): {query_embedding[:3]}")

            try:
                results_with_scores = self.cv_vector_store.similarity_search_with_score_by_vector(
                    embedding=query_embedding.tolist(), 
                    k=k_neighbors
                )
                
                print(f"SSR_DEBUG: KW '{keyword_text}': Found {len(results_with_scores)} raw neighbors BEFORE threshold.")

                for i, (doc, score) in enumerate(results_with_scores):
                    doc_filename = doc.metadata.get("source_file", "N/A")
                    # Clean the content first, then use in f-string
                    clean_content = doc.page_content[:150].replace(os.linesep, ' ').replace('\n', ' ')
                    # Detailed logging for each found neighbor
                    print(f"SSR_DEBUG:  KW '{keyword_text}' | Neighbor {i+1}/{len(results_with_scores)} | Score: {score:.4f} | CV Chunk: '{clean_content}...' | Source: {doc_filename}")

                    # Specific logging if target CV is found
                    if debug_target_cv_filename and doc_filename == debug_target_cv_filename:
                        clean_debug_content = doc.page_content[:100].replace(os.linesep, ' ').replace('\n', ' ')
                        print(f"SSR_DEBUG_TARGET_CV: KW '{keyword_text}' found chunk from CV '{doc_filename}' with score {score:.4f}. Content: '{clean_debug_content}...'")
                    
                    # Apply similarity threshold
                    if similarity_threshold is None or score >= similarity_threshold:
                        all_raw_matches.append({
                            "keyword": keyword_text,
                            "keyword_category": keyword_category,
                            "keyword_priority": keyword_priority,
                            "cv_document": doc, 
                            "similarity_score": float(score) 
                        })
                        if debug_target_cv_filename and doc_filename == debug_target_cv_filename:
                            print(f"SSR_DEBUG_TARGET_CV: KW '{keyword_text}' in CV '{doc_filename}' (Score: {score:.4f}) PASSED threshold.")
                    else:
                        print(f"SSR_DEBUG:  KW '{keyword_text}' | Neighbor {i+1} (Score: {score:.4f}, Source: {doc_filename}) DISCARDED by threshold < {similarity_threshold}.")
                        if debug_target_cv_filename and doc_filename == debug_target_cv_filename:
                            print(f"SSR_DEBUG_TARGET_CV: KW '{keyword_text}' in CV '{doc_filename}' (Score: {score:.4f}) FAILED threshold.")
                            
            except Exception as e:
                print(f"SSR_ERROR: Error during similarity search for keyword '{keyword_text}': {e}")
                traceback.print_exc() 
                continue
        
        print(f"SSR_DEBUG: Total raw matches after search and threshold: {len(all_raw_matches)}")
        return all_raw_matches

    def rank_and_filter_matches(
        self,
        raw_matches: List[Dict[str, Any]],
        priority_weights: Optional[Dict[str, float]] = None,
        min_relevance_score: Optional[float] = 0.0 
    ) -> List[Dict[str, Any]]:
        """
        Ranks matches based on similarity score and keyword priority, then filters.

        Args:
            raw_matches: A list of raw match dictionaries from find_semantic_matches.
            priority_weights: (Optional) A dictionary mapping priority strings (e.g., "high", "medium", "low")
                              to numerical weights. Defaults to {"high": 1.5, "medium": 1.0, "low": 0.7}.
            min_relevance_score: (Optional) Minimum relevance score to keep a match after ranking.

        Returns:
            A list of ranked and filtered match dictionaries, with an added "relevance_score".
            Sorted by relevance_score in descending order.
        """
        if not raw_matches:
            return []

        if priority_weights is None:
            priority_weights = {"high": 1.5, "medium": 1.0, "low": 0.7, "unknown": 0.5}

        ranked_matches = []
        print(f"SSR_DEBUG_RANK: Starting ranking for {len(raw_matches)} raw matches. Min relevance: {min_relevance_score}")
        
        for match in raw_matches:
            priority = match.get("keyword_priority", "low").lower()
            weight = priority_weights.get(priority, 0.5) # Default weight for unknown priorities
            
            # Relevance score can be a simple product or a more complex function
            relevance_score = match["similarity_score"] * weight
            
            if min_relevance_score is None or relevance_score >= min_relevance_score:
                ranked_match = match.copy()
                ranked_match["relevance_score"] = relevance_score
                ranked_matches.append(ranked_match)
        
        # Sort by relevance_score in descending order
        ranked_matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        print(f"SSR_DEBUG_RANK: {len(ranked_matches)} matches after ranking and relevance filtering.")
        return ranked_matches

    def aggregate_matches_by_category(
        self, 
        ranked_matches: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregates ranked matches by their keyword category.

        Args:
            ranked_matches: A list of ranked match dictionaries.

        Returns:
            A dictionary where keys are keyword categories and values are dictionaries
            containing a list of matches for that category, unique keywords found, 
            average relevance score, and match count.
        """
        if not ranked_matches:
            return {}

        aggregated_results: Dict[str, Dict[str, Any]] = {}
        print(f"SSR_DEBUG_AGG: Aggregating {len(ranked_matches)} ranked matches.")

        for match in ranked_matches:
            category = match.get("keyword_category", "unknown_category")
            if category not in aggregated_results:
                aggregated_results[category] = {
                    "matches": [],
                    "unique_keywords_found": set(),
                    "total_relevance_score": 0.0,
                    "match_count": 0
                }
            
            # Store a simplified version of the match for aggregation to avoid deep Document objects if not needed
            # Or store the full match if the downstream process needs the Document object
            simplified_match = {
                "keyword": match["keyword"],
                "cv_chunk_text": match["cv_document"].page_content, # Extract text content
                "cv_chunk_metadata": match["cv_document"].metadata, # Keep metadata (e.g., page number)
                "similarity_score": match["similarity_score"],
                "relevance_score": match["relevance_score"],
                "keyword_priority": match["keyword_priority"]
            }
            aggregated_results[category]["matches"].append(simplified_match)
            aggregated_results[category]["unique_keywords_found"].add(match["keyword"])
            aggregated_results[category]["total_relevance_score"] += match["relevance_score"]
            aggregated_results[category]["match_count"] += 1

        # Finalize aggregation: convert set to list and calculate average score
        for category_data in aggregated_results.values():
            category_data["unique_keywords_found"] = sorted(list(category_data["unique_keywords_found"]))
            if category_data["match_count"] > 0:
                category_data["average_relevance_score"] = round(category_data["total_relevance_score"] / category_data["match_count"], 3)
            else:
                category_data["average_relevance_score"] = 0.0
            # Sort matches within each category by relevance score
            category_data["matches"].sort(key=lambda x: x["relevance_score"], reverse=True)

        print(f"SSR_DEBUG_AGG: Aggregation complete. Categories found: {list(aggregated_results.keys())}")
        return aggregated_results

# Example Usage (commented out)
# if __name__ == "__main__":
#     from embedding_and_vectorstore import create_embedding_function, create_faiss_vectorstore
#     from cv_document_loader import load_pdf_documents, split_documents
#     from keyword_extraction_chain import KeywordExtractionAndVectorizationChain # For keyword data
#     from custom_llm_wrapper import CustomUserLLM # For keyword data
#     import os
#     from fpdf import FPDF # To create dummy PDF for testing

#     # Mock user-provided LLM call function for keyword extraction
#     def my_mock_llm_for_keywords(prompt_text: str) -> str:
#         return json.dumps([
#             {"keyword": "Python", "category": "technical_skill", "priority": "high"},
#             {"keyword": "Django", "category": "framework", "priority": "high"},
#             {"keyword": "Data Analysis", "category": "technical_skill", "priority": "medium"},
#             {"keyword": "Communication", "category": "soft_skill", "priority": "low"}
#         ])

#     print("--- SemanticSearchAndRanker Demo ---")
#     try:
#         # 1. Setup: Create dummy PDF, load/split, create embeddings and FAISS store
#         dummy_pdf_path = "/tmp/dummy_cv_semantic_search.pdf"
#         pdf = FPDF()
#         pdf.add_page()
#         pdf.set_font("Arial", size=12)
#         pdf.multi_cell(0, 10, txt="Experienced Python developer skilled in Django and web apps. Strong data analysis capabilities using Pandas. Excellent communication skills.")
#         pdf.multi_cell(0, 10, txt="Another section about Python and SQL. Also mentions project management with Python.")
#         pdf.output(dummy_pdf_path, "F")

#         raw_docs = load_pdf_documents(dummy_pdf_path)
#         chunked_cv_docs = split_documents(raw_docs, chunk_size=100, chunk_overlap=15)
        
#         embedding_fn = create_embedding_function(model_name="all-MiniLM-L6-v2", encode_kwargs={"normalize_embeddings": True})
#         cv_faiss_store = create_faiss_vectorstore(documents=chunked_cv_docs, embedding_function=embedding_fn)
#         print(f"CV FAISS store created with {cv_faiss_store.index.ntotal} vectors.")

#         # 2. Setup: Get extracted keywords and their embeddings (from keyword_extraction_chain)
#         mock_llm = CustomUserLLM(user_llm_call_func=my_mock_llm_for_keywords)
#         keyword_pipeline = KeywordExtractionAndVectorizationChain(llm=mock_llm, embedding_function=embedding_fn)
#         sample_jd = "Looking for a Python Django developer with data analysis and communication skills."
#         extracted_kws_data, kw_embeddings_map = keyword_pipeline.run(sample_jd)
#         print(f"Extracted {len(extracted_kws_data)} keywords, vectorized {len(kw_embeddings_map)} unique keywords.")

#         # 3. Initialize SemanticSearchAndRanker
#         search_ranker = SemanticSearchAndRanker(cv_vector_store=cv_faiss_store)
#         print("SemanticSearchAndRanker initialized.")

#         # 4. Find semantic matches
#         print("\nFinding semantic matches...")
#         raw_matches_found = search_ranker.find_semantic_matches(
#             extracted_keywords_data=extracted_kws_data,
#             keyword_embeddings_map=kw_embeddings_map,
#             k_neighbors=2,
#             similarity_threshold=0.3 # Adjust as needed
#         )
#         print(f"Found {len(raw_matches_found)} raw matches initially.")
#         # for i, match in enumerate(raw_matches_found[:2]): # Print first 2 raw matches
#         #     print(f"  Raw Match {i+1}: Keyword 	"{match["keyword"]}	", Score: {match["similarity_score"]:.3f}, CV Chunk: 	"{match["cv_document"].page_content[:50]}...	"")

#         # 5. Rank and filter matches
#         print("\nRanking and filtering matches...")
#         ranked_and_filtered_matches = search_ranker.rank_and_filter_matches(raw_matches_found, min_relevance_score=0.2)
#         print(f"Have {len(ranked_and_filtered_matches)} matches after ranking and filtering.")
#         # for i, match in enumerate(ranked_and_filtered_matches[:3]): # Print first 3 ranked matches
#         #     print(f"  Ranked Match {i+1}: Keyword 	"{match["keyword"]}	", Relevance: {match["relevance_score"]:.3f}, CV Chunk: 	"{match["cv_document"].page_content[:50]}...	"")

#         # 6. Aggregate matches by category
#         print("\nAggregating matches by category...")
#         aggregated_data = search_ranker.aggregate_matches_by_category(ranked_and_filtered_matches)
#         print("Aggregated Data:")
#         for category, data in aggregated_data.items():
#             print(f"  Category: {category}")
#             print(f"    Unique Keywords: {data["unique_keywords_found"]}")
#             print(f"    Match Count: {data["match_count"]}")
#             print(f"    Avg. Relevance Score: {data["average_relevance_score"]}")
#             # print(f"    Top match in category: {data["matches"][0] if data["matches"] else 	"None	"}")
        
#         assert "technical_skill" in aggregated_data
#         if "technical_skill" in aggregated_data:
#             assert "Python" in aggregated_data["technical_skill"]["unique_keywords_found"]

#         print("\nDemo completed successfully!")

#     except ImportError as ie:
#         print(f"ImportError: {ie}. Ensure all dependencies are installed.")
#     except ValueError as ve:
#         print(f"ValueError: {ve}")
#     except RuntimeError as rte:
#         print(f"RuntimeError: {rte}")
#     except Exception as e:
#         import traceback
#         print(f"An unexpected error occurred: {e}")
#         traceback.print_exc()
#     finally:
#         if os.path.exists(dummy_pdf_path):
#             # os.remove(dummy_pdf_path)
#             pass # Keep for inspection

