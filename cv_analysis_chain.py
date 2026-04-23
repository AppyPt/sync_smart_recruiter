"""
CV Analysis Chain Module (LangChain)

This module provides functionalities to:
1. Take ranked CV matches and job description
2. Perform deep analysis of the CV content versus job requirements
3. Generate structured reports with scoring and detailed feedback
"""

from typing import List, Dict, Any, Optional, Tuple
import json
import traceback

# Remove LLMChain import and add RunnableSequence
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence

class CVAnalysisChain:
    """
    Analyzes CV content in relation to job requirements and generates a structured report.
    Uses an LLM to perform deep analysis beyond simple keyword matching.
    """

    def __init__(self, llm, output_parser=None):
        """
        Initialize the CV analysis chain.
        
        Args:
            llm: A LangChain LLM (e.g., CustomUserLLM instance)
            output_parser (Optional): A LangChain output parser (defaults to JsonOutputParser)
        """
        self.llm = llm
        
        # Use provided parser or create a JsonOutputParser
        self.output_parser = output_parser if output_parser else JsonOutputParser()
        
        # Define the analysis prompt
        self.analysis_prompt = PromptTemplate(
            template="""
You are an expert CV Analyst. Your task is to analyze a candidate's CV/resume against a job description and provide a structured assessment.

# Job Description
{job_description}

# CV Content
{cv_content}

# Context from Semantic Search
Key matches found from this CV:
{semantic_search_context}

Analyze this CV in detail against the job description and provide a comprehensive evaluation.
Return your analysis in the following JSON structure:
{{ 
    "overall_match_score": <0-100 score>,
    "summary_of_fit": "<concise assessment of candidate's fit>",
    "strengths": ["<strength 1>", "<strength 2>", ...],
    "weaknesses_or_gaps": ["<gap 1>", "<gap 2>", ...],
    "skill_assessments": {{
        "<skill1>": {{
            "score": <0-100>,
            "evidence": "<quote or evidence from CV>",
            "comment": "<your assessment>"
        }},
        "<skill2>": {{
            "score": <0-100>,
            "evidence": "<quote or evidence from CV>",
            "comment": "<your assessment>"
        }}
    }},
    "experience_assessment": "<analysis of relevant experience>",
    "education_assessment": "<analysis of education relevance>",
    "recommendation": "<hire/interview/reject recommendation with rationale>"
}}

Focus on providing substantive, evidence-based assessment rather than general statements. Quote specific parts of the CV that support your evaluation.
Be direct and objective in your assessment.
            """,
            input_variables=["job_description", "cv_content", "semantic_search_context"]
        )
        
        # Replace LLMChain with RunnableSequence
        self.analysis_chain = self.analysis_prompt | self.llm | self.output_parser

    def analyze_cv(self, 
                  cv_content: str, 
                  job_description: str, 
                  semantic_search_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes CV content against job requirements and generates a structured report.
        
        Args:
            cv_content: The full text content of the CV
            job_description: The job description or requirements
            semantic_search_context: Optional context from semantic search stage
            
        Returns:
            Dict with structured analysis report
        """
        if not cv_content or not cv_content.strip():
            return {
                "error": "CV content is empty", 
                "overall_match_score": 0,
                "summary_of_fit": "Cannot analyze an empty CV"
            }
            
        if not job_description or not job_description.strip():
            return {
                "error": "Job description is empty",
                "overall_match_score": 0, 
                "summary_of_fit": "Cannot analyze without job requirements"
            }
        
        # If no semantic search context provided, use a placeholder
        if not semantic_search_context:
            semantic_search_context = "No semantic search context available."
            
        try:
            # Update the chain invocation
            result = self.analysis_chain.invoke({
                "cv_content": cv_content,
                "job_description": job_description,
                "semantic_search_context": semantic_search_context
            })
            
            # The result should already be parsed as JSON by the output parser
            if not isinstance(result, dict):
                return {
                    "error": "LLM output is not a dictionary",
                    "raw_output": str(result),
                    "overall_match_score": 0
                }
                
            # Check if result has overall_match_score
            if "overall_match_score" not in result:
                result["overall_match_score"] = 0
                result["error"] = "Missing overall_match_score in LLM output"
                
            return result
            
        except Exception as e:
            traceback_str = traceback.format_exc()
            error_message = f"Error analyzing CV: {str(e)}"
            print(f"{error_message}\n{traceback_str}")
            
            return {
                "error": error_message,
                "traceback": traceback_str,
                "overall_match_score": 0,
                "summary_of_fit": "Analysis failed due to an error"
            }
            
    def generate_summary_report(self, analyses: List[Dict[str, Any]], 
                              include_full_analyses: bool = False) -> Dict[str, Any]:
        """
        Generates a summary report from multiple CV analyses.
        
        Args:
            analyses: List of analysis results from analyze_cv method
            include_full_analyses: Whether to include full analysis details in the report
            
        Returns:
            Dict with summary report
        """
        if not analyses:
            return {"error": "No analyses provided"}
            
        try:
            # Sort analyses by overall_match_score in descending order
            sorted_analyses = sorted(
                analyses, 
                key=lambda x: x.get("overall_match_score", 0), 
                reverse=True
            )
            
            # Create summary for each candidate
            candidate_summaries = []
            for analysis in sorted_analyses:
                candidate_name = analysis.get("candidate_name", "Unknown Candidate")
                summary = {
                    "candidate_name": candidate_name,
                    "overall_match_score": analysis.get("overall_match_score", 0),
                    "summary_of_fit": analysis.get("summary_of_fit", "No summary provided"),
                    "recommendation": analysis.get("recommendation", "No recommendation"),
                    "cv_filename": analysis.get("cv_filename", "Unknown file")
                }
                
                if include_full_analyses:
                    summary["full_analysis"] = analysis
                    
                candidate_summaries.append(summary)
                
            # Create the final summary report
            report = {
                "total_candidates_analyzed": len(analyses),
                "average_match_score": sum(a.get("overall_match_score", 0) for a in analyses) / len(analyses),
                "top_candidates": candidate_summaries[:3] if len(candidate_summaries) > 3 else candidate_summaries,
                "all_candidates": candidate_summaries
            }
            
            return report
            
        except Exception as e:
            traceback_str = traceback.format_exc()
            error_message = f"Error generating summary report: {str(e)}"
            print(f"{error_message}\n{traceback_str}")
            
            return {
                "error": error_message,
                "traceback": traceback_str
            }
