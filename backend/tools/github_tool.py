from github import Github
from datetime import datetime, timedelta
from backend.core.config import settings

def get_github_client() -> Github:
    return Github(settings.github_token)

async def search_github_commits(
    service: str,
    hours_before_incident: int = 24
) -> dict:
    """
    Searches GitHub for recent commits to a service repository.
    Returns commits, authors, and changed files.
    """
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
            "commits_found": len(results),
            "commits": results,
            "searched_service": service,
            "time_range_hours": hours_before_incident
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "commits": []
        }