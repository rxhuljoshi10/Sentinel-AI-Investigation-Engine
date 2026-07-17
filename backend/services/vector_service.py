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

async def store_incident(
    incident_id: str,
    log_content: str,
    report: InvestigationReport
) -> None:
    """
    Stores an incident and its embedding in ChromaDB.
    """

    # Text we embed = combination of log + key findings
    # More context = better similarity matching
    text_to_embed = f"""
    Service: {report.affected_service}
    Cause: {report.probable_cause}
    Severity: {report.severity}
    Log excerpt: {log_content[:500]}
    """.strip()

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

async def search_similar_incidents(
    log_content: str,
    report: InvestigationReport,
    top_k: int = 3,
    exclude_id: str | None = None,
    service_name: str | None = None
) -> list[SimilarIncident]:
    """
    Finds the most similar past incidents to the current one.
    When service_name is provided, restricts search to that service only
    (prevents cross-service false positives from generic SRE vocabulary).
    """

    # Check if we have anything stored yet
    if collection.count() == 0:
        return []

    # Embed the same way we embedded during storage
    text_to_embed = f"""
    Service: {report.affected_service}
    Cause: {report.probable_cause}
    Severity: {report.severity}
    Log excerpt: {log_content[:500]}
    """.strip()

    embedding = await generate_embedding(text_to_embed)

    # Query top candidates
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances"]
    )


    similar = []
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i, (metadata, distance) in enumerate(zip(metadatas, distances)):
        similarity_score = 1 - (distance / 2)
        record_id = results["ids"][0][i]

        # Skip self
        if exclude_id and record_id == exclude_id:
            continue

        # A single threshold works better than service-name filtering.
        # From observed data:
        #   - Same failure pattern (e.g. DB pool vs DB pool): 0.93-0.95 → pass
        #   - Different failure type (e.g. Redis vs DB pool):  0.86-0.89 → fail
        # Service name is intentionally ignored: a DB pool exhaustion on
        # payment-service IS a useful similar incident for user-service.
        if similarity_score < 0.92:
            continue

        print(
            f"[RAG] Similar incident: service={metadata.get('affected_service')} "
            f"score={similarity_score:.3f}"
        )

        similar.append(SimilarIncident(
            id=results["ids"][0][i],
            similarity_score=round(similarity_score, 3),
            affected_service=metadata["affected_service"],
            probable_cause=metadata["probable_cause"],
            immediate_actions=json.loads(metadata["immediate_actions"]),
            created_at=datetime.fromisoformat(metadata["created_at"])
        ))

    return similar