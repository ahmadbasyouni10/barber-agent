#!/usr/bin/env python3
"""
Simple test script to verify LangSmith integration.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_ollama import Ollama

# Load environment variables
load_dotenv()

def main():
    """Run a simple LangSmith test."""
    print("Testing LangSmith integration...")
    
    # Check if we have the necessary environment variables
    required_vars = [
        'LANGSMITH_TRACING', 
        'LANGSMITH_API_KEY'
    ]
    
    for var in required_vars:
        if not os.environ.get(var):
            print(f"Error: {var} environment variable is not set.")
            print("Please set all required environment variables in your .env file.")
            return
    
    try:
        # Try to use Ollama (free and open source)
        try:
            print("\nAttempting to use Ollama (local open-source model)...")
            llm = Ollama(model="llama2")
            using_model = "Ollama (llama2)"
        except Exception as e:
            print(f"\nCouldn't connect to Ollama: {e}")
            print("Falling back to OpenAI...")
            
            # Check if we have OpenAI API key
            if not os.environ.get('OPENAI_API_KEY'):
                print("Error: OPENAI_API_KEY environment variable is not set.")
                print("Please either:")
                print("1. Set up Ollama (https://ollama.ai/)")
                print("2. Add your OpenAI API key to the .env file")
                return
                
            llm = ChatOpenAI()
            using_model = "OpenAI"
        
        # Invoke the LLM
        print(f"\nSending a test message using {using_model}...")
        response = llm.invoke("Hello! I'm testing my integration with LangSmith. Please respond with a short greeting.")
        
        if using_model == "Ollama (llama2)":
            print(f"\nLLM Response: {response}")
        else:
            print(f"\nLLM Response: {response.content}")
            
        print("\nIf LangSmith is configured correctly, you should see this run in your LangSmith dashboard.")
        print("Visit: https://smith.langchain.com/projects")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nPlease check your environment variables and try again.")

if __name__ == "__main__":
    main() 