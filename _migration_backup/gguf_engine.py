"""
R1 - GGUF Local LLM Engine
Supports any GGUF model file - load anytime, switch models instantly
"""
import os
import threading
import logging
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger("R1-GGUF")

LLAMA_AVAILABLE = False
try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import LlamaTextCompletionRunner
    LLAMA_AVAILABLE = True
except ImportError:
    logger.warning("llama-cpp-python not installed. Run: pip install llama-cpp-python")
except Exception as e:
    logger.warning(f"Could not load llama-cpp: {e}")


@dataclass
class ChatMessage:
    role: str
    content: str


class GGUFEngine:
    """
    Local GGUF LLM Engine - loads and runs GGUF models
    """
    
    def __init__(self):
        self.model_path: Optional[str] = None
        self.llama: Optional[Llama] = None
        self.model_loaded = False
        self.model_name = "No Model"
        self.context_length = 4096
        self.n_gpu_layers = 0
        self.n_threads = 4
        self.temperature = 0.7
        self.top_p = 0.95
        self.top_k = 40
        self.repeat_penalty = 1.1
        self.lock = threading.Lock()
        
    def set_model_path(self, path: str) -> bool:
        """Set the GGUF model file path"""
        if not os.path.exists(path):
            return False
        self.model_path = path
        self.model_name = os.path.basename(path)
        return True
    
    def load_model(self, model_path: Optional[str] = None, force: bool = False) -> Dict:
        """Load a GGUF model into memory"""
        if model_path:
            if not self.set_model_path(model_path):
                return {"success": False, "error": f"Model file not found: {model_path}"}
        
        if not self.model_path:
            return {"success": False, "error": "No model path specified"}
        
        if self.model_loaded and not force:
            if self.model_path == model_path or model_path is None:
                return {"success": True, "message": f"Model already loaded: {self.model_name}", "loaded": True}
        
        try:
            if not LLAMA_AVAILABLE:
                return {"success": False, "error": "llama-cpp-python not installed. Run: pip install llama-cpp-python"}
            
            with self.lock:
                # Unload existing model
                if self.llama:
                    del self.llama
                    self.llama = None
                
                logger.info(f"Loading GGUF model: {self.model_path}")
                
                self.llama = Llama(
                    model_path=self.model_path,
                    n_ctx=self.context_length,
                    n_gpu_layers=self.n_gpu_layers,
                    n_threads=self.n_threads,
                    n_threads_batch=self.n_threads,
                    rope_freq_base=0,
                    rope_freq_scale=0,
                    verbose=False,
                )
                
                self.model_loaded = True
                self.model_name = os.path.basename(self.model_path)
                
                logger.info(f"✓ Model loaded: {self.model_name}")
                
                return {
                    "success": True, 
                    "model": self.model_name,
                    "context": self.context_length,
                    "loaded": True
                }
                
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return {"success": False, "error": str(e)}
    
    def unload_model(self):
        """Unload the model from memory"""
        with self.lock:
            if self.llama:
                del self.llama
                self.llama = None
            self.model_loaded = False
            logger.info("Model unloaded")
    
    def chat(self, messages: List[ChatMessage], **kwargs) -> Dict:
        """Generate a chat response"""
        if not self.model_loaded or not self.llama:
            return {"success": False, "error": "No model loaded"}
        
        try:
            # Convert messages to llama format
            prompt = self._build_prompt(messages)
            
            # Generation params
            temp = kwargs.get("temperature", self.temperature)
            top_p = kwargs.get("top_p", self.top_p)
            max_tokens = kwargs.get("max_tokens", 2048)
            
            with self.lock:
                output = self.llama(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temp,
                    top_p=top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    echo=False,
                    stream=False,
                )
            
            response = output["choices"][0]["text"].strip()
            
            return {
                "success": True,
                "response": response,
                "model": self.model_name,
                "finish_reason": output.get("choices", [{}])[0].get("finish_reason", "stop")
            }
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {"success": False, "error": str(e)}
    
    def chat_stream(self, messages: List[ChatMessage], **kwargs):
        """Generate a streaming chat response (generator)"""
        if not self.model_loaded or not self.llama:
            yield {"success": False, "error": "No model loaded"}
            return
        
        try:
            prompt = self._build_prompt(messages)
            
            temp = kwargs.get("temperature", self.temperature)
            top_p = kwargs.get("top_p", self.top_p)
            max_tokens = kwargs.get("max_tokens", 2048)
            
            with self.lock:
                stream = self.llama(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temp,
                    top_p=top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    echo=False,
                    stream=True,
                )
            
            for chunk in stream:
                text = chunk.get("choices", [{}])[0].get("text", "")
                if text:
                    yield {"success": True, "text": text, "model": self.model_name}
                    
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"success": False, "error": str(e)}
    
    def _build_prompt(self, messages: List[ChatMessage]) -> str:
        """Build prompt from messages (simple format for now)"""
        # Using simple instruction format
        system = "You are R1 (Orion), an advanced AI assistant. Be helpful, concise, and intelligent."
        
        prompt_parts = [f"System: {system}\n"]
        
        for msg in messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}\n")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}\n")
        
        prompt_parts.append("Assistant: ")
        return "".join(prompt_parts)
    
    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            "model_loaded": self.model_loaded,
            "model_name": self.model_name if self.model_loaded else "No Model",
            "model_path": self.model_path,
            "context_length": self.context_length,
            "n_gpu_layers": self.n_gpu_layers,
            "library_loaded": LLAMA_AVAILABLE
        }
    
    def get_available_models(self, folder: str) -> List[Dict]:
        """Get list of GGUF models in a folder"""
        models = []
        if not os.path.exists(folder):
            return models
        
        for f in os.listdir(folder):
            if f.lower().endswith(".gguf"):
                path = os.path.join(folder, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                models.append({
                    "name": f,
                    "path": path,
                    "size_mb": round(size_mb, 1)
                })
        
        return sorted(models, key=lambda x: x["size_mb"], reverse=True)
    
    def set_params(self, **kwargs):
        """Update generation parameters"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Global engine instance
_gguf_engine = GGUFEngine()


def get_gguf_engine() -> GGUFEngine:
    return _gguf_engine


def init_gguf(model_path: Optional[str] = None, default_folder: str = None) -> Dict:
    """Initialize GGUF engine with optional auto-load"""
    engine = get_gguf_engine()
    
    if default_folder:
        models = engine.get_available_models(default_folder)
        if models and not model_path:
            model_path = models[0]["path"]
    
    if model_path:
        return engine.load_model(model_path)
    
    return {"success": True, "loaded": False, "message": "GGUF engine ready. No model loaded."}
