from github import Github
from datetime import datetime, timedelta
from backend.core.config import settings

def get_github_client() -> Github:
    return Github(settings.github_token)

# Catalog of simulated commits for showcase/demo purposes
MOCK_COMMITS = {
    "payment-service": [
        {
            "sha": "cf78e12",
            "message": "Reduce HikariCP maximumPoolSize from 100 to 10 to conserve DB connections",
            "author": "alice-sre",
            "offset_hours": 2,
            "files_changed": ["payment-service/src/main/resources/application.yml"]
        },
        {
            "sha": "a10bc39",
            "message": "Implement fallback channel for payment transaction retries",
            "author": "bob-dev",
            "offset_hours": 12,
            "files_changed": ["payment-service/src/main/java/com/sentinel/payment/Gateway.java"]
        }
    ],
    "order-service": [
        {
            "sha": "d89ef23",
            "message": "Upgrade order processing batch size to 5000 records for speed",
            "author": "bob-dev",
            "offset_hours": 3,
            "files_changed": ["order-service/src/main/java/com/sentinel/order/BatchConfig.java"]
        },
        {
            "sha": "b55fd82",
            "message": "Refactor heap allocation limits on order validation loops",
            "author": "charlie-dev",
            "offset_hours": 8,
            "files_changed": ["order-service/pom.xml"]
        }
    ],
    "auth-service": [
        {
            "sha": "e90f124",
            "message": "Bump security token validation retry timeout to 30s to mitigate network slowness",
            "author": "charlie-sec",
            "offset_hours": 1,
            "files_changed": ["auth-service/config/jwt.json"]
        },
        {
            "sha": "f332c91",
            "message": "Update session cookies security policy headers",
            "author": "alice-sre",
            "offset_hours": 5,
            "files_changed": ["auth-service/src/main/resources/bootstrap.yml"]
        }
    ]
}

async def search_github_commits(
    service: str,
    hours_before_incident: int = 24
) -> dict:
    """
    Searches GitHub for recent commits to a service repository.
    Falls back to simulated realistic commits for demo/showcase service names.
    """
    cleaned_service = service.lower().strip()
    
    # If GitHub token/repo is missing, or we explicitly want to mock demo services, use simulated data
    use_mock = not settings.github_token or cleaned_service in MOCK_COMMITS or settings.github_repo == "rxhuljoshi10/Sentinel-AI-Investigation-Engine"

    if use_mock:
        commits = MOCK_COMMITS.get(cleaned_service, [
            {
                "sha": "0000000",
                "message": f"Initial deployment of {service}",
                "author": "system-ci",
                "offset_hours": 24,
                "files_changed": []
            }
        ])
        
        now = datetime.utcnow()
        results = []
        for c in commits:
            if c["offset_hours"] <= hours_before_incident:
                results.append({
                    "sha": c["sha"],
                    "message": c["message"],
                    "author": c["author"],
                    "timestamp": (now - timedelta(hours=c["offset_hours"])).isoformat(),
                    "files_changed": c["files_changed"]
                })
                
        return {
            "success": True,
            "simulated": True,
            "commits_found": len(results),
            "commits": results,
            "searched_service": service,
            "time_range_hours": hours_before_incident
        }

    try:
        g = get_github_client()
        repo = g.get_repo(settings.github_repo)

        since = datetime.utcnow() - timedelta(hours=hours_before_incident)
        commits = repo.get_commits(since=since)

        results = []
        for commit in list(commits)[:10]:
            results.append({
                "sha": commit.sha[:7],
                "message": commit.commit.message.split("\n")[0],
                "author": commit.commit.author.name,
                "timestamp": commit.commit.author.date.isoformat(),
                "files_changed": [f.filename for f in commit.files[:5]]
            })

        return {
            "success": True,
            "simulated": False,
            "commits_found": len(results),
            "commits": results,
            "searched_service": service,
            "time_range_hours": hours_before_incident
        }

    except Exception as e:
        # Fallback to simulated on failure rather than failing the whole tool
        commits = MOCK_COMMITS.get(cleaned_service, [])
        now = datetime.utcnow()
        results = []
        for c in commits:
            if c["offset_hours"] <= hours_before_incident:
                results.append({
                    "sha": c["sha"],
                    "message": c["message"],
                    "author": c["author"],
                    "timestamp": (now - timedelta(hours=c["offset_hours"])).isoformat(),
                    "files_changed": c["files_changed"]
                })
        return {
            "success": True,
            "simulated": True,
            "commits_found": len(results),
            "commits": results,
            "searched_service": service,
            "time_range_hours": hours_before_incident,
            "error_fallback_reason": str(e)
        }