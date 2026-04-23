"""
Keyword Extraction and Vectorization Chain Module (LangChain)

This module provides functionalities to:
1. Extract keywords (along with categories and priorities) from a job description
   using a RunnableSequence with a custom LLM wrapper.
2. Vectorize these extracted keywords using a consistent embedding function.
"""

from typing import List, Dict, Any, Tuple, Optional
import json
import numpy as np

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_huggingface import HuggingFaceEmbeddings
from custom_llm_wrapper import CustomUserLLM

DEFAULT_KEYWORD_EXTRACTION_PROMPT_TEMPLATE = (
    "Analyze the following job description and extract key skills, qualifications, and experience requirements. "
    "For each item, identify the keyword or phrase, categorize it (e.g., 'technical_skill', 'soft_skill', "
    "'experience_years', 'education', 'certification', 'tool', 'framework', 'methodology'), "
    "and assign a priority (e.g., 'high', 'medium', 'low') based on its apparent importance in the text. "
    "Return your response as a single, valid JSON array of objects, where each object has 'keyword', "
    "'category', and 'priority' keys. Do not include any text or explanations outside of this JSON array.\n\n"
    "Job Description:\n{job_description_text}"
)

class KeywordExtractionAndVectorizationChain:
    """A class that encapsulates the keyword extraction and vectorization process."""
    
    def __init__(
        self, 
        llm: CustomUserLLM, 
        embedding_function: HuggingFaceEmbeddings, 
        prompt_template_str: Optional[str] = None
    ):
        if not hasattr(llm, "invoke"):
            raise TypeError("llm must be a valid LangChain LLM instance with an invoke method.")
        if not hasattr(embedding_function, "embed_documents") or not hasattr(embedding_function, "embed_query"):
            raise TypeError("embedding_function must be a valid LangChain Embeddings instance.")

        self.llm = llm
        self.embedding_function = embedding_function
        
        template_str = prompt_template_str if prompt_template_str else DEFAULT_KEYWORD_EXTRACTION_PROMPT_TEMPLATE
        self.prompt = PromptTemplate(input_variables=["job_description_text"], template=template_str)
        self.chain = self.prompt | self.llm

    def _parse_llm_response_for_keywords(self, llm_response_str: str) -> List[Dict[str, Any]]:
        try:
            cleaned_response = llm_response_str.strip()
            
            # Handle markdown code block formatting
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
                
            cleaned_response = cleaned_response.strip()
            
            keywords_data = json.loads(cleaned_response)
            if not isinstance(keywords_data, list):
                raise ValueError("LLM response for keywords, after JSON parsing, is not a list.")
            
            valid_keywords_data = []
            for item in keywords_data:
                if isinstance(item, dict) and all(k in item for k in ["keyword", "category", "priority"]):
                    valid_keywords_data.append(item)
            
            return valid_keywords_data
            
        except json.JSONDecodeError as e:
            error_context = llm_response_str[:500]
            raise ValueError(
                f"Failed to parse LLM keyword extraction response as JSON. Error: {e}. "
                f"Response (first 500 chars): '{error_context}...'"
            )
        except Exception as e:
            raise RuntimeError(f"Error processing LLM keyword response: {e}")

    def _vectorize_keywords(self, keywords_data: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
        if not keywords_data:
            return {}
            
        keyword_texts = [
            item["keyword"] 
            for item in keywords_data 
            if isinstance(item.get("keyword"), str)
        ]
        unique_keyword_texts = sorted(list(set(keyword_texts)))
        
        if not unique_keyword_texts:
            return {}
            
        embeddings_list = self.embedding_function.embed_documents(unique_keyword_texts)
        keyword_to_embedding_map = {
            text: np.array(emb, dtype=np.float32) 
            for text, emb in zip(unique_keyword_texts, embeddings_list)
        }
        
        return keyword_to_embedding_map

    def run(self, job_description_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, np.ndarray]]:
        if not job_description_text or not job_description_text.strip():
            raise ValueError("Job description text cannot be empty.")

        llm_response_obj = self.chain.invoke({"job_description_text": job_description_text})
        llm_response_str = ""

        if isinstance(llm_response_obj, str):
            llm_response_str = llm_response_obj
        elif isinstance(llm_response_obj, dict) and "text" in llm_response_obj:
            llm_response_str = llm_response_obj["text"]
        elif hasattr(llm_response_obj, 'content') and isinstance(llm_response_obj.content, str):
            llm_response_str = llm_response_obj.content
        else:
            if isinstance(llm_response_obj, dict):
                for val in llm_response_obj.values():
                    if isinstance(val, str):
                        llm_response_str = val
                        break
                        
            if not llm_response_str:
                raise ValueError(
                    f"Unexpected chain response type or structure: {type(llm_response_obj)}. "
                    f"Content: {str(llm_response_obj)[:200]}"
                )

        extracted_keywords_data = self._parse_llm_response_for_keywords(llm_response_str)
        keyword_embeddings_map = self._vectorize_keywords(extracted_keywords_data)
        
        return extracted_keywords_data, keyword_embeddings_map