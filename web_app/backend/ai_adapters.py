"""
Real AI model adapters for OpenAI, Anthropic, Google, etc.
"""
import os
import httpx
from typing import Optional, Dict, Any
from ai_council.core.interfaces import AIModel


class OpenAIAdapter(AIModel):
    """Adapter for OpenAI models (GPT-4, GPT-3.5)."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1"
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI API."""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate (calls async version)."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


class AnthropicAdapter(AIModel):
    """Adapter for Anthropic Claude models."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic API."""
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


class GoogleGeminiAdapter(AIModel):
    """Adapter for Google Gemini models."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using Google Gemini API."""
        if not self.api_key:
            raise ValueError("Google API key not configured")
        
        # Use v1beta for gemini-pro, or try gemini-1.5-flash for v1
        # Try v1beta first
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 4000),
                "temperature": kwargs.get("temperature", 0.7)
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


class GroqAdapter(AIModel):
    """Adapter for Groq models (Llama, Mixtral)."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using Groq API."""
        if not self.api_key:
            raise ValueError("Groq API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


class MistralAdapter(AIModel):
    """Adapter for Mistral AI models."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1"
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using Mistral API."""
        if not self.api_key:
            raise ValueError("Mistral API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


class XAIAdapter(AIModel):
    """Adapter for xAI Grok models."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        self.model_id = model_id
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.base_url = "https://api.x.ai/v1"
        
    def get_model_id(self) -> str:
        return self.model_id
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response."""
        return await self.generate_async(prompt, **kwargs)
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """Generate response using xAI API."""
        if not self.api_key:
            raise ValueError("xAI API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4000)
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous generate."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, **kwargs))


def create_model_adapter(provider: str, model_id: str, api_key: Optional[str] = None) -> AIModel:
    """Factory function to create appropriate model adapter."""
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "google": GoogleGeminiAdapter,
        "groq": GroqAdapter,
        "mistral": MistralAdapter,
        "xai": XAIAdapter
    }
    
    adapter_class = adapters.get(provider.lower())
    if not adapter_class:
        raise ValueError(f"Unknown provider: {provider}")
    
    return adapter_class(model_id, api_key)
