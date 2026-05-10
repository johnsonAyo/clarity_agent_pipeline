
import sys
import os
import logging
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

from llm.router import call_llm
from prompts.analysis import system_prompt

logging.basicConfig(level=logging.INFO)

def test_full_flow():
    print("Starting Pipeline Verification Test...")
    
    # 1. Sample business idea (AI Influencer Marketing)
    test_content = """
    I want to build an AI Influencer marketing agency. 
    The idea is to use Higgsfield Marketing Studio to create hyper-realistic AI avatars that promote mobile apps. 
    The goal is to hit $40k/month in revenue by scaling these avatars across TikTok and Instagram.
    I've seen claims that this can make $480k/year with just one person.
    """
    
    print(" Calling LLM (DeepSeek-V3.1:671b)... This will take a moment for reasoning and web search.")
    
    try:
        # Run the full analysis pipeline
        model_label, result = call_llm(system_prompt(), test_content)
        
        print("\n Analysis received from LLM!")
        print("-" * 50)
        print(result[:500] + "...") # Preview
        print("-" * 50)
        
        # 2. Test the Telegram delivery logic
        print("\n Testing Telegram delivery logic...")
        from bot import messenger
        messenger.send_to_output(result)
        print(" Analysis sent to Telegram! Check your Output Bot.")
        
    except Exception as e:
        print(f" Test Failed: {e}")

if __name__ == "__main__":
    load_dotenv()
    test_full_flow()
