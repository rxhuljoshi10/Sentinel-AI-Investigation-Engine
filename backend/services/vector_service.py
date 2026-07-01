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
    top_k: int = 3
) -> list[SimilarIncident]:
    """
    Finds the most similar past incidents to the current one.
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

    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances"]
    )

    similar = []
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for metadata, distance in zip(metadatas, distances):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity score: 1 = identical, 0 = opposite
        similarity_score = 1 - (distance / 2)

        # Only include genuinely similar incidents
        if similarity_score < 0.5:
            continue

        similar.append(SimilarIncident(
            id=results["ids"][0][metadatas.index(metadata)],
            similarity_score=round(similarity_score, 3),
            affected_service=metadata["affected_service"],
            probable_cause=metadata["probable_cause"],
            immediate_actions=json.loads(metadata["immediate_actions"]),
            created_at=datetime.fromisoformat(metadata["created_at"])
        ))

    return similar