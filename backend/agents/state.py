from typing import TypedDict, Annotated
from operator import add

class InvestigationState(TypedDict):
    # Input
    incident_description: str
    log_content: str

    # Collected evidence - uses add operator so each agent appends
    evidence: Annotated[list[str], add]

    # Individual agent outputs
    log_findings: dict
    similar_incidents: list
    github_commits: list

    # Control flow
    failed_tools: Annotated[list[str], add]
    completed_tools: Annotated[list[str], add]

    # Final output
    final_report: dict
    investigation_id: str