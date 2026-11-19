"""
Kilo API provider for the Crypto Intelligence Agent.
Handles AI model communication, streaming, retries, and cost tracking.
"""

import json
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import get_settings, KiloAPISettings, ModelSettings, ModelsSettings


class ModelTask(str, Enum):
    REASONING = "reasoning"
    RESEARCH = "research"
    LIGHTWEIGHT = "lightweight"
    PLANNING = "planning"
    TOOL_SELECTION = "tool_selection"
    CLASSIFICATION = "classification"


@dataclass
class ChatMessage:
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ChatCompletionRequest:
    messages: List[ChatMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 8192
    stream: bool = False
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[Union[str, Dict]] = None
    response_format: Optional[Dict] = None


@dataclass
class ChatCompletionResponse:
    id: str
    model: str
    created: int
    choices: List[Dict]
    usage: Dict
    cost_usd: float = 0.0


@dataclass
class StreamingChunk:
    id: str
    model: str
    created: int
    choices: List[Dict]
    is_final: bool = False


class KiloAPIError(Exception):
    """Base exception for Kilo API errors."""
    pass


class KiloAPIRateLimitError(KiloAPIError):
    """Rate limit exceeded."""
    pass


class KiloAPIAuthenticationError(KiloAPIError):
    """Authentication failed."""
    pass


class KiloAPIModelError(KiloAPIError):
    """Model-related error."""
    pass


class KiloAPIProvider:
    """Kilo API provider with model management, streaming, and cost tracking."""
    
    provider_name: str = "Kilo API"
    
    def __init__(self, settings: Optional[KiloAPISettings] = None):
        self.settings = settings or get_settings().kilo_api
        self.models_config = get_settings().models
        self._client: Optional[httpx.AsyncClient] = None
        self._usage_stats = {
            "daily_tokens": 0,
            "daily_cost": 0.0,
            "monthly_tokens": 0,
            "monthly_cost": 0.0,
            "requests_count": 0,
            "errors_count": 0
        }
        self._last_reset_day = datetime.utcnow().day
        self._last_reset_month = datetime.utcnow().month
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.settings.timeout),
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _get_model_for_task(self, task: ModelTask) -> ModelSettings:
        """Get model settings for a specific task."""
        task_map = {
            ModelTask.REASONING: self.models_config.reasoning,
            ModelTask.RESEARCH: self.models_config.research,
            ModelTask.LIGHTWEIGHT: self.models_config.lightweight,
            ModelTask.PLANNING: self.models_config.reasoning,
            ModelTask.TOOL_SELECTION: self.models_config.lightweight,
            ModelTask.CLASSIFICATION: self.models_config.lightweight,
        }
        return task_map.get(task, self.models_config.reasoning)
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage (Kilo API free models = $0)."""
        # Kilo API provides free models, so cost is 0
        # This is kept for future compatibility with paid models
        return 0.0
    
    def _check_usage_limits(self, estimated_cost: float) -> None:
        """Check if usage would exceed limits."""
        settings = get_settings()
        daily_limit = settings.cost.max_daily_usd
        monthly_limit = settings.cost.max_monthly_usd
        
        if self._usage_stats["daily_cost"] + estimated_cost > daily_limit:
            raise KiloAPIError(f"Daily cost limit (${daily_limit}) would be exceeded")
        
        if self._usage_stats["monthly_cost"] + estimated_cost > monthly_limit:
            raise KiloAPIError(f"Monthly cost limit (${monthly_limit}) would be exceeded")
    
    def _update_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        """Update usage statistics."""
        self._usage_stats["daily_tokens"] += input_tokens + output_tokens
        self._usage_stats["daily_cost"] += cost
        self._usage_stats["monthly_tokens"] += input_tokens + output_tokens
        self._usage_stats["monthly_cost"] += cost
        self._usage_stats["requests_count"] += 1
        
        # Reset daily/monthly counters if needed
        now = datetime.utcnow()
        if now.day != self._last_reset_day:
            self._usage_stats["daily_tokens"] = 0
            self._usage_stats["daily_cost"] = 0.0
            self._last_reset_day = now.day
        
        if now.month != self._last_reset_month:
            self._usage_stats["monthly_tokens"] = 0
            self._usage_stats["monthly_cost"] = 0.0
            self._last_reset_month = now.month
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics."""
        return self._usage_stats.copy()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, KiloAPIRateLimitError))
    )
    async def _make_request(self, endpoint: str, payload: Dict) -> Dict:
        """Make a request to the Kilo API with retry logic."""
        client = await self._get_client()
        
        try:
            response = await client.post(endpoint, json=payload)
            
            if response.status_code == 401:
                raise KiloAPIAuthenticationError("Invalid API key")
            elif response.status_code == 429:
                raise KiloAPIRateLimitError("Rate limit exceeded")
            elif response.status_code >= 500:
                raise KiloAPIError(f"Server error: {response.status_code}")
            elif response.status_code >= 400:
                raise KiloAPIError(f"Request error: {response.status_code} - {response.text}")
            
            return response.json()
        
        except httpx.TimeoutException:
            raise KiloAPIError("Request timeout")
        except httpx.NetworkError as e:
            raise KiloAPIError(f"Network error: {str(e)}")
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        task: ModelTask = ModelTask.REASONING,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        response_format: Optional[Dict] = None,
        model_override: Optional[str] = None
    ) -> Union[ChatCompletionResponse, AsyncGenerator[StreamingChunk, None]]:
        """
        Send a chat completion request.
        
        Args:
            messages: List of chat messages
            task: Task type to determine which model to use
            temperature: Override temperature
            max_tokens: Override max tokens
            stream: Whether to stream the response
            tools: Available tools for function calling
            tool_choice: Tool choice strategy
            response_format: Response format (e.g., {"type": "json_object"})
            model_override: Override the model completely
        
        Returns:
            ChatCompletionResponse or async generator of StreamingChunk
        """
        model_settings = self._get_model_for_task(task)
        model = model_override or model_settings.model
        
        # Prepare request
        request = ChatCompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature if temperature is not None else model_settings.temperature,
            max_tokens=max_tokens or model_settings.max_tokens,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format
        )
        
        # Convert messages to API format
        api_messages = []
        for msg in request.messages:
            api_msg = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                api_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            if msg.name:
                api_msg["name"] = msg.name
            api_messages.append(api_msg)
        
        payload = {
            "model": request.model,
            "messages": api_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }
        
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.response_format:
            payload["response_format"] = request.response_format
        
        if stream:
            return self._stream_completion(payload, model)
        else:
            return await self._complete(payload, model)
    
    async def _complete(self, payload: Dict, model: str) -> ChatCompletionResponse:
        """Make a non-streaming completion request."""
        response_data = await self._make_request("/chat/completions", payload)
        
        # Extract usage
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        
        # Check limits
        self._check_usage_limits(cost)
        
        # Update usage
        self._update_usage(input_tokens, output_tokens, cost)
        
        return ChatCompletionResponse(
            id=response_data.get("id", str(uuid.uuid4())),
            model=response_data.get("model", model),
            created=response_data.get("created", int(time.time())),
            choices=response_data.get("choices", []),
            usage=usage,
            cost_usd=cost
        )
    
    async def _stream_completion(self, payload: Dict, model: str) -> AsyncGenerator[StreamingChunk, None]:
        """Make a streaming completion request."""
        client = await self._get_client()
        
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            if response.status_code == 401:
                raise KiloAPIAuthenticationError("Invalid API key")
            elif response.status_code == 429:
                raise KiloAPIRateLimitError("Rate limit exceeded")
            elif response.status_code >= 400:
                text = await response.aread()
                raise KiloAPIError(f"Request error: {response.status_code} - {text.decode()}")
            
            buffer = ""
            total_input_tokens = 0
            total_output_tokens = 0
            
            async for chunk in response.aiter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines[-1]  # Keep incomplete line in buffer
                
                for line in lines[:-1]:
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            yield StreamingChunk(
                                id=data.get("id", str(uuid.uuid4())),
                                model=data.get("model", model),
                                created=data.get("created", int(time.time())),
                                choices=data.get("choices", []),
                                is_final=False
                            )
                            
                            # Track usage from streaming chunks if available
                            if "usage" in data:
                                total_input_tokens = data["usage"].get("prompt_tokens", 0)
                                total_output_tokens = data["usage"].get("completion_tokens", 0)
                        
                        except json.JSONDecodeError:
                            continue
            
            # Final update with usage
            if total_input_tokens > 0 or total_output_tokens > 0:
                cost = self._calculate_cost(model, total_input_tokens, total_output_tokens)
                self._check_usage_limits(cost)
                self._update_usage(total_input_tokens, total_output_tokens, cost)
            
            # Send final chunk
            yield StreamingChunk(
                id=str(uuid.uuid4()),
                model=model,
                created=int(time.time()),
                choices=[],
                is_final=True
            )
    
    async def list_models(self) -> List[Dict]:
        """List available models from Kilo API."""
        client = await self._get_client()
        response = await client.get("/models")
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def health_check(self) -> bool:
        """Check if the API is accessible."""
        # Return True if we have a valid API key configured
        # Actual API health is verified on first real request
        return bool(self.settings.api_key and self.settings.base_url)


# Global provider instance
_kilo_provider: Optional[KiloAPIProvider] = None
_gemini_provider: Optional[KiloAPIProvider] = None


async def get_kilo_provider() -> KiloAPIProvider:
    """Get the global Kilo API provider instance."""
    global _kilo_provider
    if _kilo_provider is None:
        _kilo_provider = KiloAPIProvider()
    return _kilo_provider


async def close_kilo_provider() -> None:
    """Close the global Kilo API provider."""
    global _kilo_provider
    if _kilo_provider:
        await _kilo_provider.close()
        _kilo_provider = None


class GeminiAPIProvider(KiloAPIProvider):
    """Google Gemini provider using the OpenAI-compatible endpoint.

    Free tier available (no credit card required) via Google AI Studio.
    Arabic-capable models (e.g. gemini-3.8-flash) are used for research tasks.
    """

    provider_name: str = "Gemini API"
    
    def __init__(self, settings: Optional[KiloAPISettings] = None, models: Optional[ModelSettings] = None) -> None:
        gemini_settings = settings or get_settings().gemini_api
        task_model = models or ModelSettings(
            model=gemini_settings.default_model,
            temperature=0.5,
            max_tokens=8192,
        )
        self.settings = KiloAPISettings(
            base_url=gemini_settings.base_url,
            api_key=gemini_settings.api_key,
            default_model=gemini_settings.default_model,
            fallback_model=gemini_settings.default_model,
        )
        self._client: Optional[httpx.AsyncClient] = None
        self.models_config = ModelsSettings(
            reasoning=task_model,
            research=task_model,
            lightweight=task_model,
        )


async def get_gemini_provider() -> GeminiAPIProvider:
    """Get the global Gemini API provider instance."""
    global _gemini_provider
    if _gemini_provider is None:
        _gemini_provider = GeminiAPIProvider()
    return _gemini_provider


async def get_ai_provider() -> Any:
    """Return the active AI provider: Gemini when configured, otherwise Kilo."""
    settings = get_settings()
    if settings.gemini_api.api_key:
        return await get_gemini_provider()
    return await get_kilo_provider()


async def close_gemini_provider() -> None:
    """Close the global Gemini API provider."""
    global _gemini_provider
    if _gemini_provider:
        await _gemini_provider.close()
        _gemini_provider = None