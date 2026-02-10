"""Ollama client for local LLM integration."""

import json
from typing import AsyncGenerator, Dict, List, Optional, Any

import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings


class OllamaClient:
    """Client for interacting with local Ollama instance."""
    
    def __init__(self):
        self.base_url = settings.ollama_host.rstrip("/")
        self.host = self.base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.max_tokens = settings.ollama_max_tokens
        
        logger.info(f"Ollama client initialized: {self.base_url} (model: {self.model})")

    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[List[int]] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            system: Optional system message
            context: Optional conversation context
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            
        Returns:
            Response dictionary from Ollama
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream
        }
        
        if system:
            payload["system"] = system
        
        if context:
            payload["context"] = context
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")
                    
                    if stream:
                        return await self._handle_streaming_response(response)
                    else:
                        return await response.json()
                        
        except aiohttp.ClientError as e:
            logger.error(f"Ollama connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.9,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Chat with the LLM using message format.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            
        Returns:
            Response dictionary from Ollama
        """
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
            "options": {
                "num_predict": self.max_tokens
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")
                    
                    if stream:
                        return await self._handle_streaming_response(response)
                    else:
                        return await response.json()
                        
        except aiohttp.ClientError as e:
            logger.error(f"Ollama connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise
    
    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Stream generate response from LLM.
        
        Yields:
            Chunks of the generated response
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "temperature": temperature,
            "stream": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")
                    
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Ollama."""
        url = f"{self.base_url}/api/tags"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("models", [])
                    else:
                        logger.error(f"Failed to list models: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    async def check_connection(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception as e:
            logger.error(f"Ollama connection check failed: {e}")
            return False
    
    async def _handle_streaming_response(self, response) -> Dict[str, Any]:
        """Handle streaming response and collect full output."""
        full_response = ""
        context = None
        
        async for line in response.content:
            if line:
                try:
                    data = json.loads(line)
                    if "response" in data:
                        full_response += data["response"]
                    if "context" in data:
                        context = data["context"]
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
        
        return {
            "response": full_response,
            "context": context,
            "done": True
        }
    
    async def structured_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        output_format: str = "json",
        temperature: float = 0.3
    ) -> Any:
        """
        Generate structured output (JSON) from LLM.
        
        Args:
            prompt: The user prompt
            system: Optional system message
            output_format: Expected output format
            temperature: Lower temperature for more deterministic output
            
        Returns:
            Parsed structured output
        """
        format_instruction = f"\n\nYou must respond with valid {output_format.upper()} only. No other text."
        
        full_prompt = prompt + format_instruction
        
        try:
            response = await self.generate(
                prompt=full_prompt,
                system=system,
                temperature=temperature,
                stream=False
            )
            
            output = response.get("response", "").strip()
            
            # Try to extract JSON if wrapped in code blocks
            if "```json" in output:
                output = output.split("```json")[1].split("```")[0].strip()
            elif "```" in output:
                output = output.split("```")[1].split("```")[0].strip()
            
            if output_format.lower() == "json":
                return json.loads(output)
            else:
                return output
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse structured output: {e}")
            logger.debug(f"Raw output: {output}")
            raise
        except Exception as e:
            logger.error(f"Structured generation error: {e}")
            raise


# Global Ollama client instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get or create global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
