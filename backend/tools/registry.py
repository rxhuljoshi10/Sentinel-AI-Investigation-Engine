from backend.tools.github_tool import search_github_commits
from backend.tools.database_tool import query_incidents_db
from backend.tools.filesystem_tool import read_log_file

# Tool definitions — what the LLM sees
TOOL_DEFINITIONS = [
    {
        "name": "search_github_commits",
        "description": """Search GitHub for recent commits to a service repository.
Use this when the incident might be caused by a recent code change or deployment.
Best for: deployment issues, sudden behavior changes, new bugs after releases.""",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Name of the service to search commits for e.g. payment-service"
                },
                "hours_before_incident": {
                    "type": "integer",
                    "description": "How many hours back to search. Default 24."
                }
            },
            "required": ["service"]
        }
    },
    {
        "name": "query_incidents_db",
        "description": """Query the incidents database for past incidents related to a service.
Use this to find historical patterns and previous resolutions.
Best for: recurring issues, finding if this happened before, pattern analysis.""",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service name to query incidents for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of past incidents to return. Default 5."
                }
            },
            "required": ["service"]
        }
    },
    {
        "name": "read_log_file",
        "description": """Read a log file from the filesystem.
Use this when a specific log file path is mentioned in the incident.
Best for: reading specific service logs, application error logs.""",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Full path to the log file to read"
                }
            },
            "required": ["file_path"]
        }
    }
]

# Maps tool name to actual function
TOOL_EXECUTOR = {
    "search_github_commits": search_github_commits,
    "query_incidents_db": query_incidents_db,
    "read_log_file": read_log_file,
}

async def execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    Executes a tool by name with given arguments.
    Returns result or error dict.
    """
    if tool_name not in TOOL_EXECUTOR:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }

    tool_fn = TOOL_EXECUTOR[tool_name]

    try:
        result = await tool_fn(**arguments)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }