import chromadb
import httpx
import json
from datetime import datetime
from backend.core.config import settings
from backend.models.schemas import InvestigationReport, SimilarIncident

# Initialize ChromaDB client with disk persistence
client = chromadb.PersistentClient(path=settings.chroma_path)

# Get or create our incidents collection
collection = client.get_or_create_collection(
    name="incidents",
    metadata={"hnsw:space": "cosine"}
)

async def generate_embedding(text: str) -> list[float]:
    """
    Converts text to a vector using nomic-embed-text via Ollama.
    """
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={
                "model": settings.ollama_embed_model,
                "prompt": text
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]


def _build_search_text(service: str, cause: str, severity: str, log_excerpt: str) -> str:
    """
    Builds the canonical text used for BOTH storing and querying.

    Using the exact same format on both sides is critical — any divergence between
    the storage embedding and the query embedding degrades similarity accuracy.
    """
    return (
        f"Service: {service}\n"
        f"Severity: {severity}\n"
        f"Cause: {cause}\n"
        f"Log: {log_excerpt[:500]}"
    ).strip()


async def store_incident(
    incident_id: str,
    log_content: str,
    report: InvestigationReport
) -> None:
    """
    Stores a completed incident and its embedding in ChromaDB.

    Called after every successful investigation so the collection grows over time
    and future RAG searches have past incidents to compare against.
    """
    text_to_embed = _build_search_text(
        service=report.affected_service,
        cause=report.probable_cause,
        severity=report.severity,
        log_excerpt=log_content
    )

    embedding = await generate_embedding(text_to_embed)

    collection.add(
        ids=[incident_id],
        embeddings=[embedding],
        documents=[log_content[:1000]],
        metadatas=[{
            "affected_service": report.affected_service,
            "probable_cause": report.probable_cause,
            "severity": report.severity,
            "immediate_actions": json.dumps(report.immediate_actions),
            "created_at": datetime.utcnow().isoformat()
        }]
    )
    print(
        f"[RAG] Stored incident {incident_id[:8]} in ChromaDB "
        f"(service={report.affected_service}, collection_size={collection.count()})"
    )


async def search_similar_incidents(
    service: str,
    cause: str,
    severity: str,
    log_content: str,
    top_k: int = 3,
    exclude_id: str | None = None,
    similarity_threshold: float = 0.85
) -> list[SimilarIncident]:
    """
    Finds the most similar past incidents to the current one using vector similarity.

    Takes explicit structured fields (service, cause, severity) extracted by the
    Log Analyzer — NOT raw user text — so the query embedding matches the schema
    used when incidents were stored.

    ChromaDB cosine distance is in [0, 1] where 0 = identical, 1 = orthogonal.
    Similarity = 1.0 - distance.
    Default threshold of 0.85 means at least 85% cosine similarity is required.
    """
    count = collection.count()
    if count == 0:
        print("[RAG] Collection is empty — no past incidents to compare against yet.")
        return []

    text_to_embed = _build_search_text(
        service=service,
        cause=cause,
        severity=severity,
        log_excerpt=log_content
    )

    embedding = await generate_embedding(text_to_embed)

    # Request one extra result to account for possible self-exclusion.
    # Guard ensures n_results is always >= 1 and <= collection size.
    n_results = max(1, min(top_k + 1, count))

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["metadatas", "distances"]
    )

    similar = []
    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for record_id, metadata, distance in zip(ids, metadatas, distances):
        # Skip the current investigation (comparing against itself)
        if exclude_id and record_id == exclude_id:
            continue

        # ChromaDB cosine distance ∈ [0, 1], so similarity = 1.0 - distance
        similarity_score = round(1.0 - distance, 3)

        if similarity_score < similarity_threshold:
            print(
                f"[RAG] Below threshold: id={record_id[:8]} "
                f"score={similarity_score:.3f} < {similarity_threshold}"
            )
            continue

        print(
            f"[RAG] Match: service={metadata.get('affected_service')} "
            f"score={similarity_score:.3f}"
        )

        similar.append(SimilarIncident(
            id=record_id,
            similarity_score=similarity_score,
            affected_service=metadata["affected_service"],
            probable_cause=metadata["probable_cause"],
            immediate_actions=json.loads(metadata["immediate_actions"]),
            created_at=datetime.fromisoformat(metadata["created_at"])
        ))

        if len(similar) >= top_k:
            break

    return similar