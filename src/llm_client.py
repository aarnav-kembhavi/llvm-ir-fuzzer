import os
import json
import time
from typing import Optional
from abc import ABC, abstractmethod

class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> Optional[str]:
        pass

class MockClient(LLMClient):
    """A deterministic mock client for testing."""
    def generate(self, prompt: str) -> Optional[str]:
        if "MOCK_FAIL" in prompt:
            return None
        if "MOCK_NON_JSON" in prompt:
            return "This is just text, not json."
            
        return json.dumps({
            "description": "Mock mutation changing add to sub",
            "line_number": 3,
            "original_line": "  %add = add i32 %a, %b",
            "mutated_line": "  %add = sub i32 %a, %b"
        })

class GeminiClient(LLMClient):
    """Client for Google's Gemini API."""
    def __init__(self, model_name=None, temperature=0.7, max_retries=3):
        from google import genai
        from google.genai import types
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
            
        # Prioritize environment variable over config/default
        env_model = os.environ.get("GEMINI_MODEL")
        self.model_name = env_model if env_model else (model_name if model_name else "gemini-1.5-flash")
        
        self.client = genai.Client(api_key=api_key)
        self.temperature = temperature
        self.types = types
        self.max_retries = max_retries

    def generate(self, prompt: str) -> Optional[str]:
        from google.genai import errors
        for attempt in range(self.max_retries):
            try:
                # Wrap generation in try-except for network stability
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.types.GenerateContentConfig(temperature=self.temperature)
                )
                return response.text
            except errors.ClientError as e:
                # Handle specific client errors that shouldn't be retried
                # The google-genai SDK ClientError has status_code attribute
                status_code = getattr(e, 'status_code', None)
                
                if status_code == 404:
                    print(f"[GeminiClient] Fatal Error: Model '{self.model_name}' not found (404). Please update your configuration.")
                    return None
                if status_code == 429:
                    error_msg = str(e).lower()
                    if "spending cap" in error_msg or "monthly spending" in error_msg:
                        print(f"[GeminiClient] Fatal Error: Spending cap exceeded (429). Please check AI Studio.")
                        return None
                    print(f"[GeminiClient] Rate limit hit (429). Retrying in {2 ** attempt}s...")
                else:
                    print(f"[GeminiClient] Client Error {status_code}: {e}")
                
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"[GeminiClient] Unexpected error on attempt {attempt+1}: {e}")
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(2 ** attempt)
        return None

class OpenAIClient(LLMClient):
    """Client for OpenAI's API."""
    def __init__(self, model_name="gpt-4o", temperature=0.7, max_retries=3, base_url=None):
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
            
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        # Prioritize environment variable
        env_model = os.environ.get("OPENAI_MODEL")
        self.model_name = env_model if env_model else model_name
        self.temperature = temperature
        self.max_retries = max_retries

    def generate(self, prompt: str) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"[OpenAIClient] Error on attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
        return None

class AnthropicClient(LLMClient):
    """Client for Anthropic's Claude API."""
    def __init__(self, model_name="claude-3-5-sonnet-latest", temperature=0.7, max_retries=3):
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        # Prioritize environment variable
        env_model = os.environ.get("ANTHROPIC_MODEL")
        self.model_name = env_model if env_model else model_name
        self.temperature = temperature
        self.max_retries = max_retries

    def generate(self, prompt: str) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=4096,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except Exception as e:
                print(f"[AnthropicClient] Error on attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
        return None

class GrokClient(OpenAIClient):
    """Client for xAI's Grok API (OpenAI compatible)."""
    def __init__(self, model_name="grok-beta", temperature=0.7, max_retries=3):
        # xAI uses OpenAI SDK with a custom base URL
        api_key = os.environ.get("GROK_API_KEY")
        if not api_key:
            raise ValueError("GROK_API_KEY environment variable not set")
            
        # We temporarily set OPENAI_API_KEY to GROK_API_KEY for the parent constructor
        # or we just override the initialization logic
        import openai
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        env_model = os.environ.get("GROK_MODEL")
        self.model_name = env_model if env_model else model_name
        self.temperature = temperature
        self.max_retries = max_retries

class GroqAIClient(OpenAIClient):
    """Client for Groq's free, high-speed API (OpenAI compatible). Uses open-weight models like Llama."""
    def __init__(self, model_name="llama-3.3-70b-versatile", temperature=0.7, max_retries=3):
        import openai
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        env_model = os.environ.get("GROQ_MODEL")
        self.model_name = env_model if env_model else model_name
        self.temperature = temperature
        self.max_retries = max_retries


def create_client(config_dict: dict) -> LLMClient:
    """Factory to create an LLM client based on config and environment."""
    # 1. Try environment variable LLM_BACKEND
    backend = os.environ.get("LLM_BACKEND")
    
    # 2. Try config file backend
    if not backend:
        backend = config_dict.get("backend")
        
    # 3. Smart Auto-Detection: Check for available API keys if no backend specified
    if not backend:
        if os.environ.get("GEMINI_API_KEY"):
            backend = "gemini"
        elif os.environ.get("GROQ_API_KEY"):   # Groq: free, fast, open-weight models
            backend = "groq_ai"
        elif os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            backend = "claude"
        elif os.environ.get("GROK_API_KEY"):
            backend = "grok"
        else:
            backend = "mock"
            
    backend = backend.lower()
    
    # Common parameters
    temp = float(os.environ.get("LLM_TEMPERATURE", config_dict.get("temperature", 0.7)))
    retries = int(os.environ.get("LLM_MAX_RETRIES", config_dict.get("max_retries", 3)))
    
    # Resolve model name:
    # 1. Check models dictionary for specific backend
    # 2. Fallback to top-level model field
    models_dict = config_dict.get("models", {})
    model = models_dict.get(backend, config_dict.get("model"))
    
    if backend == "gemini":
        return GeminiClient(model_name=model, temperature=temp, max_retries=retries)
    elif backend == "groq_ai" or backend == "groq":
        # Distinguish between Groq (free, open-weight) and Grok (xAI)
        if backend == "groq_ai":
            return GroqAIClient(model_name=model if model else "llama-3.3-70b-versatile", temperature=temp, max_retries=retries)
        return GrokClient(model_name=model if model else "grok-beta", temperature=temp, max_retries=retries)
    elif backend == "openai":
        return OpenAIClient(model_name=model if model else "gpt-4o", temperature=temp, max_retries=retries)
    elif backend == "claude" or backend == "anthropic":
        return AnthropicClient(model_name=model if model else "claude-3-5-sonnet-latest", temperature=temp, max_retries=retries)
    elif backend == "mock":
        return MockClient()
    else:
        print(f"[Warning] Unknown backend '{backend}', falling back to MockClient.")
        return MockClient()
