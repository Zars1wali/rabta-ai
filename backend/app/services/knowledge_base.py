"""
Knowledge Base Service — Hybrid RAG Catalog Engine for Rabta AI
================================================================
Combines SQL token matching (exact keyword/model retrieval) with semantic
vector search (Gemini Embeddings) stored in PostgreSQL JSONB.

Features:
  - Exact token matching for specific model names (e.g., 'Taurus G3', 'Glock 19', 'Beretta 92FS')
  - Semantic vector search for conceptual/descriptive queries (e.g., 'tactical 9mm pistol for concealed carry')
  - Hybrid scoring: 0.6 * text_relevance + 0.4 * semantic_similarity
  - Verified product image resolution ensuring exact variant delivery
"""
from __future__ import annotations
import logging
import math
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_

from app.db.session import AsyncSessionLocal
from app.models.database import CatalogItem
from app.services.embedding_service import embedding_service
from app.core.config import settings

logger = logging.getLogger(__name__)


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two 1D vectors with zero-division safety."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


class KnowledgeBaseService:
    """PostgreSQL-consolidated Hybrid Vector & Catalog Search Service."""

    def __init__(self):
        self.dimensions = settings.GEMINI_EMBEDDING_DIM

    async def init_collection(self):
        """Vector storage initialization hook."""
        logger.info("[KnowledgeBase] PostgreSQL hybrid vector & catalog storage initialized.")

    async def search_catalog(
        self,
        tenant_id: str,
        query: str,
        query_vector: Optional[List[float]] = None,
        category: Optional[str] = None,
        origin: Optional[str] = None,
        caliber: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search across catalog items for the specified tenant.
        
        Args:
            tenant_id: UUID of the business tenant.
            query: Free-text search string (e.g., "Taurus G3", "9mm Turkish shotgun").
            query_vector: Optional pre-computed embedding vector.
            category: Optional filter ("Pistols", "Rifles", "Shotguns", "Ammunition").
            origin: Optional country filter ("USA", "Austria", "Turkey", "Pakistan", etc.).
            caliber: Optional caliber filter ("9mm", "7.62x39", "12 Gauge", etc.).
            limit: Maximum items to return.
        """
        try:
            t_uuid = uuid.UUID(tenant_id)
        except (ValueError, TypeError):
            logger.error("[KnowledgeBase] Invalid tenant_id: %s", tenant_id)
            return []

        tokens = [tok.lower().strip() for tok in query.split() if len(tok.strip()) >= 2]
        query_lower = query.lower().strip()

        async with AsyncSessionLocal() as session:
            conditions = [CatalogItem.tenant_id == t_uuid, CatalogItem.in_stock == True]

            if category:
                cat_root = category.strip().rstrip("sS")
                conditions.append(
                    or_(
                        CatalogItem.category.ilike(f"%{category.strip()}%"),
                        CatalogItem.category.ilike(f"%{cat_root}%"),
                    )
                )

            # Build broad candidate retrieval query
            token_conditions = []
            for tok in tokens:
                token_conditions.append(CatalogItem.name.ilike(f"%{tok}%"))
                token_conditions.append(CatalogItem.description.ilike(f"%{tok}%"))

            if token_conditions:
                stmt = select(CatalogItem).where(*conditions, or_(*token_conditions)).limit(30)
            else:
                stmt = select(CatalogItem).where(*conditions).limit(30)

            res = await session.execute(stmt)
            candidates = res.scalars().all()

            # If no matches with token conditions, fallback to general tenant catalog sample
            if not candidates:
                fallback_stmt = select(CatalogItem).where(*conditions).limit(15)
                res = await session.execute(fallback_stmt)
                candidates = res.scalars().all()

            if not candidates:
                return []

            # Optional: generate query vector if not supplied and candidates have embeddings
            has_any_embedding = any(bool(c.embedding_data and "vector" in c.embedding_data) for c in candidates)
            if has_any_embedding and not query_vector:
                try:
                    query_vector = await embedding_service.embed_text(query)
                except Exception as e:
                    logger.warning("[KnowledgeBase] Failed to generate query vector: %s", e)

            # Score each candidate using hybrid ranker
            scored_items = []
            for item in candidates:
                name_lower = (item.name or "").lower()
                desc_lower = (item.description or "").lower()
                meta = item.metadata_json or {}
                it_origin = (meta.get("origin") or "").lower()
                it_caliber = (meta.get("caliber") or "").lower()

                # Filter checks if explicitly passed
                if origin and origin.lower() not in it_origin and origin.lower() not in name_lower:
                    continue
                if caliber and caliber.lower() not in it_caliber and caliber.lower() not in name_lower:
                    continue

                # 1. Text Relevance Score (0.0 to 1.0)
                # Exact phrase match is top tier (e.g. "taurus g3" matches "taurus g3")
                if query_lower in name_lower:
                    text_score = 1.0
                else:
                    # Token overlap score with heavy weighting on product name
                    name_tok_matches = sum(1 for tok in tokens if tok in name_lower)
                    desc_tok_matches = sum(1 for tok in tokens if tok in desc_lower)
                    denom = max(1, len(tokens))
                    text_score = min(1.0, (name_tok_matches * 0.8 + desc_tok_matches * 0.2) / denom)

                # 2. Semantic Similarity Score (0.0 to 1.0)
                semantic_score = 0.0
                if query_vector and item.embedding_data and "vector" in item.embedding_data:
                    item_vec = item.embedding_data["vector"]
                    semantic_score = max(0.0, _cosine_similarity(query_vector, item_vec))

                # 3. Hybrid Score
                if semantic_score > 0.0:
                    hybrid_score = (0.6 * text_score) + (0.4 * semantic_score)
                else:
                    hybrid_score = text_score

                # Resolve verified image URLs
                image_urls = []
                if item.images and isinstance(item.images, list):
                    for img in item.images:
                        if isinstance(img, str) and img.strip():
                            url = img.strip()
                            if url.startswith("/"):
                                url = f"http://65.20.90.130{url}"
                            image_urls.append(url)

                scored_items.append({
                    "score": hybrid_score,
                    "text_score": text_score,
                    "semantic_score": semantic_score,
                    "id": str(item.id),
                    "name": item.name,
                    "name_urdu": item.name_urdu,
                    "price": float(item.price) if item.price is not None else 0.0,
                    "currency": item.currency or "PKR",
                    "category": item.category or "General",
                    "description": item.description or "",
                    "origin": meta.get("origin") or "Imported",
                    "caliber": meta.get("caliber") or "",
                    "capacity": meta.get("capacity") or "",
                    "action": meta.get("action") or "",
                    "in_stock": item.in_stock,
                    "images": image_urls,
                    "has_photo": len(image_urls) > 0,
                    "primary_photo": image_urls[0] if image_urls else None,
                })

            # Sort descending by hybrid score
            scored_items.sort(key=lambda x: x["score"], reverse=True)
            return scored_items[:limit]

    async def search_by_image(
        self,
        tenant_id: str,
        query_vector: List[float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search catalog by image embedding."""
        try:
            t_uuid = uuid.UUID(tenant_id)
        except (ValueError, TypeError):
            return []

        if not query_vector:
            return []

        async with AsyncSessionLocal() as session:
            stmt = select(CatalogItem).where(
                CatalogItem.tenant_id == t_uuid,
                CatalogItem.in_stock == True,
            ).limit(50)
            res = await session.execute(stmt)
            items = res.scalars().all()

            results = []
            for item in items:
                if item.embedding_data and "vector" in item.embedding_data:
                    sim = _cosine_similarity(query_vector, item.embedding_data["vector"])
                    if sim > 0.4:
                        results.append({
                            "similarity": sim,
                            "id": str(item.id),
                            "name": item.name,
                            "price": float(item.price) if item.price is not None else 0.0,
                            "category": item.category,
                            "primary_photo": item.images[0] if item.images else None,
                        })
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

    async def upsert_catalog_embedding(self, tenant_id: str, item_id: str, text_to_embed: str) -> bool:
        """Compute and store embedding for a catalog item."""
        if not text_to_embed:
            return False
        vec = await embedding_service.embed_text(text_to_embed)
        if not vec:
            return False

        try:
            item_uuid = uuid.UUID(item_id)
            tenant_uuid = uuid.UUID(tenant_id)
        except (ValueError, TypeError):
            return False

        async with AsyncSessionLocal() as session:
            stmt = select(CatalogItem).where(
                CatalogItem.id == item_uuid,
                CatalogItem.tenant_id == tenant_uuid,
            )
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                return False
            item.embedding_data = {
                "vector": vec,
                "model": settings.GEMINI_EMBEDDING_MODEL,
                "dim": len(vec),
            }
            await session.commit()
            return True


kb_service = KnowledgeBaseService()
