"""
R1 v1 - Vector Memory with Embeddings
Semantic search using local embeddings via Ollama.
"""
import json
import hashlib
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("R1")


class VectorMemory:
    """
    Vector-based memory storage with semantic search.
    Uses Ollama embeddings API for generating embeddings.
    """

    def __init__(self, db_path: str = ""):
        from ..config.settings import settings
        self.db_path = Path(db_path or Path.home() / ".r1" / "vectors.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Ollama settings
        self.ollama_endpoint = settings.ollama_endpoint
        self.embedding_model = getattr(settings, 'embedding_model', 'nomic-embed-text')

        # In-memory storage (loaded from disk)
        self.vectors: Dict[str, List[float]] = {}
        self.texts: Dict[str, str] = {}
        self.metadata: Dict[str, Dict] = {}

        self._load()

    def _load(self):
        """Load vectors from disk."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.vectors = data.get('vectors', {})
                    self.texts = data.get('texts', {})
                    self.metadata = data.get('metadata', {})
                logger.info(f"Loaded {len(self.vectors)} vectors from {self.db_path}")
            except Exception as e:
                logger.warning(f"Failed to load vectors: {e}")

    def _save(self):
        """Save vectors to disk."""
        try:
            with open(self.db_path, 'w') as f:
                json.dump({
                    'vectors': self.vectors,
                    'texts': self.texts,
                    'metadata': self.metadata,
                    'updated_at': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vectors: {e}")

    async def _get_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding using Ollama embeddings API.
        Falls back to hash-based deterministic embedding if Ollama fails.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_endpoint}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": text[:8192]  # Limit text length
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get('embedding', [])
                    if embedding:
                        return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.debug(f"Ollama embedding failed, using fallback: {e}")

        # Fallback: deterministic hash-based embedding (for demo/testing)
        # In production, this should use a proper local embedding model
        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> np.ndarray:
        """
        Deterministic fallback embedding using text hashing.
        Creates a consistent 384-dimensional vector.
        """
        import hashlib

        # Use multiple hash passes for better distribution
        dim = 384
        embedding = np.zeros(dim, dtype=np.float32)

        # Hash the text multiple times with different prefixes
        for i in range(dim // 32):
            hash_input = f"{i}:{text}".encode()
            hash_bytes = hashlib.sha256(hash_input).digest()
            for j in range(min(32, dim - i * 32)):
                embedding[i * 32 + j] = (hash_bytes[j] / 255.0) * 2 - 1  # Normalize to [-1, 1]

        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    async def add(self, text: str, metadata: Dict = None, id: str = None) -> str:
        """
        Add text with embedding to vector store.

        Args:
            text: Text to store
            metadata: Optional metadata dict
            id: Optional ID (generated from hash if not provided)

        Returns:
            ID of the stored item
        """
        if not text or not text.strip():
            return None

        if id is None:
            id = hashlib.md5(text.encode()).hexdigest()[:12]

        # Skip if already exists
        if id in self.vectors:
            return id

        # Generate embedding
        embedding = await self._get_embedding(text)

        # Store
        self.vectors[id] = embedding.tolist()
        self.texts[id] = text
        self.metadata[id] = {
            **(metadata or {}),
            'added_at': datetime.now().isoformat()
        }

        self._save()
        logger.debug(f"Added vector memory: {id[:8]}... (text: {text[:50]}...)")

        return id

    async def add_batch(self, items: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple items in batch.

        Args:
            items: List of dicts with 'text' and optional 'metadata', 'id'

        Returns:
            List of IDs
        """
        ids = []
        for item in items:
            id = await self.add(
                text=item['text'],
                metadata=item.get('metadata'),
                id=item.get('id')
            )
            if id:
                ids.append(id)
        return ids

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search using cosine similarity.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of results with id, text, metadata, and similarity score
        """
        if not self.vectors:
            return []

        # Generate query embedding synchronously (using fallback)
        query_vec = self._fallback_embedding(query)

        # Calculate cosine similarity
        scores = []
        for id, vec_list in self.vectors.items():
            vec = np.array(vec_list, dtype=np.float32)

            # Cosine similarity
            dot_product = np.dot(query_vec, vec)
            query_norm = np.linalg.norm(query_vec)
            vec_norm = np.linalg.norm(vec)

            if query_norm > 0 and vec_norm > 0:
                similarity = dot_product / (query_norm * vec_norm)
                scores.append((id, float(similarity)))

        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for id, score in scores[:top_k]:
            if score > 0.3:  # Minimum similarity threshold
                results.append({
                    'id': id,
                    'text': self.texts.get(id, ''),
                    'metadata': self.metadata.get(id, {}),
                    'similarity': round(score, 4)
                })

        return results

    async def search_with_embedding(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search using proper embedding generation for query.
        Use this for production quality search.
        """
        if not self.vectors:
            return []

        # Generate proper embedding for query
        query_vec = await self._get_embedding(query)

        # Calculate cosine similarity
        scores = []
        for id, vec_list in self.vectors.items():
            vec = np.array(vec_list, dtype=np.float32)

            dot_product = np.dot(query_vec, vec)
            query_norm = np.linalg.norm(query_vec)
            vec_norm = np.linalg.norm(vec)

            if query_norm > 0 and vec_norm > 0:
                similarity = dot_product / (query_norm * vec_norm)
                scores.append((id, float(similarity)))

        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for id, score in scores[:top_k]:
            if score > 0.3:
                results.append({
                    'id': id,
                    'text': self.texts.get(id, ''),
                    'metadata': self.metadata.get(id, {}),
                    'similarity': round(score, 4)
                })

        return results

    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        if id in self.vectors:
            del self.vectors[id]
            del self.texts[id]
            del self.metadata[id]
            self._save()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return {
            'total_vectors': len(self.vectors),
            'db_path': str(self.db_path),
            'embedding_model': self.embedding_model
        }
