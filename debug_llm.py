
import sys
import os
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

from llm import call_llm
from prompts import ANALYSIS_SYSTEM_PROMPT

def debug_analysis():
    load_dotenv()
    
    test_content = """
    AI Influencer Agency business idea. 
    Use Higgsfield to create AI avatars. 
    Claim: $40k/mo revenue. 
    Cost: Higgsfield subscription + marketing spend.
    """
    
    print("--- RAW LLM CALL START ---")
    try:
        # We call the model with your system prompt and the test content
        result = call_llm(ANALYSIS_SYSTEM_PROMPT, test_content)
        print(result)
    except Exception as e:
        print(f"ERROR: {e}")
    print("--- RAW LLM CALL END ---")

if __name__ == "__main__":
    debug_analysis()
