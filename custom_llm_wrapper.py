"""
Custom LLM Wrapper Module (LangChain)

This module provides a custom LLM wrapper that allows LangChain to interact
with an external LLM class or function provided by the user.
"""

from typing import Any, List, Optional, Callable, Dict, Tuple

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM

class CustomUserLLM(LLM):
    """
    A custom LangChain LLM wrapper that uses a user-provided function
    to make calls to an external LLM.
    
    The user_llm_call_func is expected to handle the actual API call
    and return the LLM's text response.
    """
    user_llm_call_func: Callable[[str], str]  # Expects a function: (prompt: str) -> llm_response_str
    model_name: str = "custom_user_llm"
    # Add any other parameters your user_llm_call_func might need, e.g., API keys, model specifics
    # These can be passed during initialization and stored as attributes.
    # For example: user_llm_config: Optional[Dict[str, Any]] = None

    @property
    def _llm_type(self) -> str:
        return self.model_name

    def _call(
        self, 
        prompt: str, 
        stop: Optional[List[str]] = None, # LangChain can pass stop sequences
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> str:
        """
        Makes a call to the user-provided LLM function.

        Args:
            prompt: The prompt to send to the LLM.
            stop: (Optional) List of stop sequences for the LLM.
                  The user_llm_call_func should ideally handle this if the underlying LLM supports it.
            run_manager: (Optional) Callback manager for the run.
            **kwargs: Additional keyword arguments that might be passed by LangChain.

        Returns:
            The text response from the LLM.
        """
        # If your user_llm_call_func needs to be aware of stop sequences or other kwargs,
        # you would pass them here. For a simple callable, we just pass the prompt.
        # Example: response = self.user_llm_call_func(prompt, stop=stop, **kwargs_for_user_llm)
        try:
            response = self.user_llm_call_func(prompt)
            return response
        except Exception as e:
            # Log the error or handle it as appropriate
            # print(f"Error calling custom LLM function: {e}")
            raise RuntimeError(f"Custom LLM interaction failed: {e}")

    # If your LLM supports streaming, you would implement _stream or astream here.
    # async def _astream(...) -> AsyncIterator[LLMResult]: ...

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {"model_name": self.model_name, "user_llm_call_func": self.user_llm_call_func.__name__ if hasattr(self.user_llm_call_func, "__name__") else str(self.user_llm_call_func)}

# Example Usage (commented out - for agent testing or direct script run)
# if __name__ == "__main__":
#     # This is a mock user-provided LLM call function
#     def my_external_llm(prompt_text: str) -> str:
#         print(f"\n--- My External LLM Called ---")
#         print(f"Prompt received: 	"{prompt_text[:100]}...	"")
#         if "extract keywords" in prompt_text.lower():
#             # Simulate JSON string output for keyword extraction
#             return '''
#             [
#                 {"keyword": "Python", "category": "technical_skill", "priority": "high"},
#                 {"keyword": "LangChain", "category": "framework", "priority": "high"},
#                 {"keyword": "Project Management", "category": "soft_skill", "priority": "medium"}
#             ]
#             '''
#         elif "comprehensive analysis" in prompt_text.lower():
#             # Simulate JSON string output for analysis report
#             return '''
#             {
#                 "overall_match_score": 85,
#                 "summary_of_fit": "The candidate shows strong potential.",
#                 "strengths": ["Proficient in Python", "Experience with LangChain"],
#                 "weaknesses_or_gaps": ["Needs more experience in large-scale project management"],
#                 "recommendation": "Consider for interview."
#             }
#             '''
#         return f"Mock response to: {prompt_text[:50]}..."

#     print("--- CustomUserLLM Demo ---")
#     try:
#         # Initialize the custom LLM wrapper with the user's function
#         custom_llm = CustomUserLLM(user_llm_call_func=my_external_llm)
        
#         # Test a simple invocation
#         print("\nInvoking custom LLM with a simple prompt...")
#         response1 = custom_llm.invoke("Tell me a joke about AI.")
#         print(f"Response 1: {response1}")

#         # Test invocation for keyword extraction (simulating what a chain might do)
#         print("\nInvoking custom LLM for keyword extraction...")
#         keyword_prompt = "Please extract keywords from the following job description: ..."
#         response2 = custom_llm.invoke(keyword_prompt)
#         print(f"Raw response for keywords: {response2}")
#         # In a real chain, this string response would be parsed (e.g., by a JSONOutputParser)
#         import json
#         try:
#             parsed_keywords = json.loads(response2.strip())
#             print(f"Parsed keywords: {parsed_keywords}")
#             assert isinstance(parsed_keywords, list)
#         except json.JSONDecodeError as e:
#             print(f"Failed to parse keyword response as JSON: {e}")

#     except RuntimeError as re:
#         print(f"RuntimeError: {re}")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")


