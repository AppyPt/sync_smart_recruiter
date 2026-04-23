"""
CV Matching Orchestration Module (LangChain)

This module provides the main orchestration for the CV matching process:
1. Loads PDF CVs
2. Extracts keywords from job descriptions
3. Creates embeddings and vector store
4. Performs semantic search and ranking
5. Runs deep analysis on matched CVs
6. Generates structured reports
"""

from typing import List, Dict, Any, Optional, Union, Tuple
import os
import json
import pandas as pd
import traceback
from datetime import datetime
import uuid

# Import component modules
from cv_document_loader import load_pdf_documents, split_documents
from embedding_and_vectorstore import create_embedding_function, create_faiss_vectorstore # Uses new HuggingFaceEmbeddings
from keyword_extraction_chain import KeywordExtractionAndVectorizationChain # Uses new RunnableSequence
from semantic_search_and_ranking import SemanticSearchAndRanker
from cv_analysis_chain import CVAnalysisChain # Will also need update for LLMChain -> RunnableSequence
from custom_llm_wrapper import CustomUserLLM
# Import AzureLLMClient para type hinting se necessário, ou para instanciar se não vier de fora
# from azure_llm_client import AzureLLMClient


class CVMatchingOrchestrator:
    """
    Orchestrates the complete CV matching and analysis workflow.
    """
    
    def __init__(self, azure_llm_client=None, embedding_model_name="all-MiniLM-L6-v2", output_dir="data"):
        """
        Initialize the orchestrator.
        
        Args:
            azure_llm_client: Instance of AzureLLMClient or similar
            embedding_model_name: Model name for embeddings
            output_dir: Directory to save outputs (reports, etc.)
        """
        self.azure_llm_client = azure_llm_client
        self.embedding_model_name = embedding_model_name
        self.output_dir = output_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        self.embedding_function = None
        self.custom_llm = None
        self.keyword_chain = None
        self.cv_vector_store = None
        self.search_ranker = None
        self.analysis_chain = None
        
        self.extracted_keywords = []
        self.keyword_embeddings = {}
        self.semantic_matches = []
        self.ranked_matches = []
        self.cv_analyses = []
        
        self.run_id = str(uuid.uuid4())[:8]
        self.log_msgs = []
        
    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.log_msgs.append(log_entry)
        
    def initialize_components(self):
        try:
            self.log("Initializing embedding function...")
            self.embedding_function = create_embedding_function(
                model_name=self.embedding_model_name,
                encode_kwargs={"normalize_embeddings": True}
            )
            
            if self.azure_llm_client:
                self.log("Initializing custom LLM wrapper with adapter...")

                # Adaptador para compatibilizar CustomUserLLM._call (str) com AzureLLMClient.get_completion (List[Dict])
                def llm_adapter_for_custom_llm(prompt_string: str) -> str:
                    messages_for_azure = [{"role": "user", "content": prompt_string}]
                    # Nota: max_tokens não é passado por CustomUserLLM._call.
                    # Se for crucial, CustomUserLLM precisaria ser modificado ou um valor fixo usado aqui.
                    # Por exemplo, para extração de keywords, um valor menor pode ser suficiente.
                    # Para análise de CV, pode ser maior.
                    # Para simplificar, vamos deixar get_completion usar seu default ou o que for passado externamente.
                    response_content = self.azure_llm_client.get_completion(messages_for_azure) # max_tokens pode ser adicionado aqui se necessário
                    return response_content if response_content is not None else ""

                self.custom_llm = CustomUserLLM(
                    user_llm_call_func=llm_adapter_for_custom_llm
                )
                
                self.log("Initializing keyword extraction chain...")
                self.keyword_chain = KeywordExtractionAndVectorizationChain(
                    llm=self.custom_llm,
                    embedding_function=self.embedding_function
                )
                
                self.log("Initializing CV analysis chain...")
                # CVAnalysisChain também usa CustomUserLLM, então o mesmo adapter funcionará.
                self.analysis_chain = CVAnalysisChain(llm=self.custom_llm)
            else:
                raise ValueError("No LLM client (azure_llm_client) provided to orchestrator.")
                
            return True
            
        except Exception as e:
            self.log(f"Error initializing components: {str(e)}")
            traceback_str = traceback.format_exc()
            self.log(traceback_str)
            return False
            
    # ... (restante dos métodos de CVMatchingOrchestrator permanecem os mesmos) ...
    # ... (process_job_description, load_and_process_cvs, perform_semantic_search, etc.) ...

    def process_job_description(self, job_description: str) -> bool:
        if not self.keyword_chain:
            self.log("Error: Keyword chain not initialized.")
            return False
        if not job_description or not job_description.strip():
            self.log("Error: Empty job description")
            return False
        try:
            self.log("Extracting keywords from job description...")
            self.extracted_keywords, self.keyword_embeddings = self.keyword_chain.run(job_description)
            self.log(f"Extracted {len(self.extracted_keywords)} keywords")
            self.log(f"Created embeddings for {len(self.keyword_embeddings)} unique keywords")
            return True
        except Exception as e:
            self.log(f"Error processing job description: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def load_and_process_cvs(
        self, 
        cv_file_paths: List[str], 
        chunk_size: int = 500, 
        chunk_overlap: int = 50
    ) -> bool:
        """
        Loads and processes CV documents, creating chunks and a vector store.
        
        Args:
            cv_file_paths: List of paths to CV PDF files
            chunk_size: Size of text chunks for document splitting
            chunk_overlap: Number of characters to overlap between chunks
        """
        if not self.embedding_function:
            self.log("Error: Embedding function not initialized.")
            return False
        if not cv_file_paths:
            self.log("Error: No CV file paths provided")
            return False
            
        try:
            all_cv_docs = []
            self.log(f"Orchestrator_CVLoad: Processing CVs with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
            
            for cv_path in cv_file_paths:
                if not os.path.exists(cv_path):
                    self.log(f"Warning: CV file not found: {cv_path}")
                    continue
                    
                self.log(f"Loading CV: {os.path.basename(cv_path)}")
                try:
                    docs = load_pdf_documents(cv_path)
                    for doc in docs:
                        doc.metadata["source_file"] = os.path.basename(cv_path)
                        
                    # Pass both chunk_size and chunk_overlap to split_documents
                    chunks = split_documents(
                        docs, 
                        chunk_size=chunk_size, 
                        chunk_overlap=chunk_overlap
                    )
                    all_cv_docs.extend(chunks)
                    self.log(f"Processed {os.path.basename(cv_path)}: {len(chunks)} chunks")
                    
                except Exception as e_cv:
                    self.log(f"Error processing {cv_path}: {str(e_cv)}")
                    
            if not all_cv_docs:
                self.log("Warning: No CV documents were successfully loaded")
                return False
                
            self.log(f"Creating vector store with {len(all_cv_docs)} CV chunks...")
            self.cv_vector_store = create_faiss_vectorstore(
                documents=all_cv_docs,
                embedding_function=self.embedding_function
            )
            
            self.log("CV vector store created successfully")
            return True
            
        except Exception as e:
            self.log(f"Error loading and processing CVs: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def perform_semantic_search(
        self, 
        similarity_threshold: float = 0.6,
        k_neighbors: int = 5,
        debug_target_cv_filename: Optional[str] = None
    ) -> bool:
        """
        Performs semantic search on CV documents using extracted keywords.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) for matches
            k_neighbors: Number of nearest neighbors to retrieve per keyword
            debug_target_cv_filename: Optional filename to track specific CV in debug logs
        """
        if not self.cv_vector_store:
            self.log("Orchestrator_SSR_Error: CV vector store not created yet")
            return False
        if not self.extracted_keywords or not self.keyword_embeddings:
            self.log("Orchestrator_SSR_Error: Keywords not extracted yet")
            return False
            
        try:
            self.log(f"Orchestrator_SSR: Initializing semantic search. Threshold: {similarity_threshold}, K-Neighbors: {k_neighbors}")
            self.search_ranker = SemanticSearchAndRanker(cv_vector_store=self.cv_vector_store)
            
            keywords_for_search = [kw_info['keyword'] for kw_info in self.extracted_keywords]
            self.log(f"Orchestrator_SSR: Keywords for search: {keywords_for_search}")

            self.semantic_matches = self.search_ranker.find_semantic_matches(
                extracted_keywords_data=self.extracted_keywords,
                keyword_embeddings_map=self.keyword_embeddings,
                k_neighbors=k_neighbors,
                similarity_threshold=similarity_threshold,
                debug_target_cv_filename=debug_target_cv_filename
            )
            
            self.log(f"Orchestrator_SSR: Found {len(self.semantic_matches)} semantic matches after threshold filtering.")
            
            priority_weights = {"high": 1.5, "medium": 1.0, "low": 0.7, "unknown": 0.5}
            self.log("Orchestrator_SSR: Ranking and filtering matches...")
            
            self.ranked_matches = self.search_ranker.rank_and_filter_matches(
                raw_matches=self.semantic_matches,
                priority_weights=priority_weights,
                min_relevance_score=0.4
            )
            
            self.log(f"Orchestrator_SSR: Ranked matches: {len(self.ranked_matches)}")
            
            self.aggregated_matches = self.search_ranker.aggregate_matches_by_category(
                self.ranked_matches
            )
            
            self.log(f"Orchestrator_SSR: Aggregated matches into {len(self.aggregated_matches)} categories")
            return True
            
        except Exception as e:
            self.log(f"Orchestrator_SSR_Error: Error in semantic search: {str(e)}")
            self.log(traceback.format_exc())
            return False

    def analyze_cv_matches(self, cv_mapping: Dict[str, str], job_description: str) -> List[Dict[str, Any]]:
        if not self.ranked_matches:
            self.log("Error: No ranked matches available for analysis")
            return []
        if not self.analysis_chain:
            self.log("Error: Analysis chain not initialized")
            return []
        try:
            matches_by_file = {}
            for match in self.ranked_matches:
                source_file = match["cv_document"].metadata.get("source_file", "unknown")
                if source_file not in matches_by_file:
                    matches_by_file[source_file] = []
                matches_by_file[source_file].append(match)
            self.log(f"Analyzing CVs for {len(matches_by_file)} unique files")
            analysis_results = []
            for source_file, file_matches in matches_by_file.items():
                candidate_name = cv_mapping.get(source_file, "Unknown Candidate")
                cv_chunks = set(match["cv_document"].page_content for match in file_matches)
                cv_content = "\n\n".join(cv_chunks)
                match_context_parts = []
                for match in file_matches[:10]:
                    keyword = match["keyword"]
                    category = match["keyword_category"]
                    score = match["similarity_score"]
                    text_snippet = match["cv_document"].page_content[:100] + "..."
                    match_context_parts.append(f"- Keyword: '{keyword}' (Category: {category}, Score: {score:.2f})")
                    match_context_parts.append(f"  Text: {text_snippet}")
                semantic_search_context = "\n".join(match_context_parts)
                self.log(f"Analyzing CV for: {candidate_name} ({source_file})")
                analysis = self.analysis_chain.analyze_cv(
                    cv_content=cv_content,
                    job_description=job_description,
                    semantic_search_context=semantic_search_context
                )
                analysis["candidate_name"] = candidate_name
                analysis["cv_filename"] = source_file
                analysis["semantic_matches_count"] = len(file_matches)
                analysis_results.append(analysis)
                self.log(f"Analysis complete for {candidate_name}: Match score {analysis.get('overall_match_score', 0)}")
            analysis_results.sort(key=lambda x: x.get("overall_match_score", 0), reverse=True)
            self.cv_analyses = analysis_results
            return analysis_results
        except Exception as e:
            self.log(f"Error analyzing CV matches: {str(e)}")
            self.log(traceback.format_exc())
            return []

    def generate_excel_report(self, output_path: Optional[str] = None) -> str:
        if not self.cv_analyses:
            self.log("Error: No CV analyses available for report")
            return ""
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(self.output_dir, f"cv_analysis_report_{timestamp}.xlsx")
            summary_data = []
            for analysis in self.cv_analyses:
                summary_data.append({
                    "Candidate Name": analysis.get("candidate_name", "Unknown"),
                    "CV Filename": analysis.get("cv_filename", "Unknown"),
                    "Match Score": analysis.get("overall_match_score", 0),
                    "Summary": analysis.get("summary_of_fit", "No summary"),
                    "Recommendation": analysis.get("recommendation", "No recommendation"),
                    "Strengths": ", ".join(analysis.get("strengths", [])),
                    "Gaps/Weaknesses": ", ".join(analysis.get("weaknesses_or_gaps", []))
                })
            df_summary = pd.DataFrame(summary_data)
            with pd.ExcelWriter(output_path) as writer:
                df_summary.to_excel(writer, sheet_name="Summary", index=False)
                for analysis in self.cv_analyses:
                    candidate_name = analysis.get("candidate_name", "Unknown")
                    safe_name = "".join(c if c.isalnum() or c.isspace() else "_" for c in candidate_name)
                    sheet_name = f"{safe_name[:28]}"
                    basic_info_data = {
                        "Attribute": ["Candidate Name", "CV Filename", "Match Score", "Recommendation"],
                        "Value": [
                            analysis.get("candidate_name", "Unknown"),
                            analysis.get("cv_filename", "Unknown"),
                            analysis.get("overall_match_score", 0),
                            analysis.get("recommendation", "No recommendation")
                        ]
                    }
                    df_basic = pd.DataFrame(basic_info_data)
                    strengths = analysis.get("strengths", [])
                    weaknesses = analysis.get("weaknesses_or_gaps", [])
                    max_items = max(len(strengths), len(weaknesses))
                    strengths_weaknesses_data = {
                        "Strengths": strengths + [""] * (max_items - len(strengths)),
                        "Weaknesses/Gaps": weaknesses + [""] * (max_items - len(weaknesses))
                    }
                    df_str_weak = pd.DataFrame(strengths_weaknesses_data)
                    skill_data = []
                    for skill, assessment in analysis.get("skill_assessments", {}).items():
                        skill_data.append({
                            "Skill": skill,
                            "Score": assessment.get("score", 0),
                            "Evidence": assessment.get("evidence", ""),
                            "Comment": assessment.get("comment", "")
                        })
                    df_skills = pd.DataFrame(skill_data) if skill_data else pd.DataFrame({"Skill": ["N/A"], "Score": [0], "Evidence": [""], "Comment": [""]})
                    summary_assessment_data = {
                        "Summary of Fit": [analysis.get("summary_of_fit", "N/A")],
                        "Experience Assessment": [analysis.get("experience_assessment", "N/A")],
                        "Education Assessment": [analysis.get("education_assessment", "N/A")]
                    }
                    df_summary_assessment = pd.DataFrame(summary_assessment_data)

                    start_row = 0
                    df_basic.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
                    start_row += len(df_basic) + 2
                    df_str_weak.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
                    start_row += len(df_str_weak) + 2
                    df_skills.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
                    start_row += len(df_skills) + 2
                    df_summary_assessment.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)

            self.log(f"Excel report generated: {output_path}")
            return output_path
        except Exception as e:
            self.log(f"Error generating Excel report: {str(e)}")
            self.log(traceback.format_exc())
            return ""

    def run_full_pipeline(
        self, 
        job_description: str,
        cv_file_paths: List[str],
        cv_mapping: Dict[str, str],
        output_path: Optional[str] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 80,
        similarity_threshold: float = 0.5,
        k_neighbors: int = 10,
        min_relevance_score: float = 0.4,
        debug_target_cv_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs the complete CV matching pipeline.
        
        Args:
            job_description: Job description text
            cv_file_paths: List of paths to CV PDF files
            cv_mapping: Dict mapping CV filenames to candidate names
            output_path: Optional path for Excel report
            chunk_size: Size of text chunks for CV processing
            chunk_overlap: Overlap between chunks
            similarity_threshold: Minimum similarity score for matches
            k_neighbors: Number of nearest neighbors per keyword
            min_relevance_score: Minimum relevance score for ranking
            debug_target_cv_filename: Optional CV filename to track in debug logs
        """
        self.log(f"Starting CV matching pipeline (Run ID: {self.run_id})")
        
        if not self.initialize_components():
            return {"success": False, "error": "Failed to initialize components", "logs": self.log_msgs}
            
        if not self.process_job_description(job_description):
            return {"success": False, "error": "Failed to process job description", "logs": self.log_msgs}
            
        if not self.load_and_process_cvs(cv_file_paths, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            return {"success": False, "error": "Failed to load and process CVs", "logs": self.log_msgs}
            
        semantic_search_success = self.perform_semantic_search(
            similarity_threshold=similarity_threshold,
            k_neighbors=k_neighbors,
            debug_target_cv_filename=debug_target_cv_filename
        )

        if not semantic_search_success:
            self.log("Semantic search step indicated issues or found no matches to rank/analyze.")
            return {
                "success": False, 
                "error": "Semantic search phase failed or encountered an error.",
                "analyses": [],
                "report_path": None,
                "logs": self.log_msgs
            }

        # Check if we have any ranked matches
        if not self.ranked_matches:
            self.log("No ranked matches found after semantic search.")
            return {
                "success": True, 
                "message": "Pipeline completed: No relevant CVs found to analyze.", 
                "analyses": [], 
                "report_path": None, 
                "logs": self.log_msgs
            }

        # Attempt CV analysis
        analysis_results = self.analyze_cv_matches(cv_mapping, job_description)
        
        # Check if analysis failed despite having matches
        if not analysis_results:
            self.log("CV analysis produced no results despite having ranked matches.")
            return {
                "success": False, 
                "error": "Analysis phase failed: No results produced from ranked matches.", 
                "analyses": [],
                "report_path": None,
                "logs": self.log_msgs
            }

        # Generate report if we have analysis results
        report_path = self.generate_excel_report(output_path)
        
        # Final status determination
        if not report_path:
            return {
                "success": True,  # Still consider successful if only report generation failed
                "message": "Pipeline completed with analysis, but report generation failed.",
                "analyses": analysis_results,
                "report_path": None,
                "logs": self.log_msgs
            }

        # Everything succeeded
        return {
            "success": True,
            "message": "CV matching pipeline completed successfully.",
            "analyses": analysis_results,
            "report_path": report_path,
            "logs": self.log_msgs
        }

