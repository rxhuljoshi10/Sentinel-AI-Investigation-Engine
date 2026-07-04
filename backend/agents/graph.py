from langgraph.graph import StateGraph, END
from backend.agents.state import InvestigationState
from backend.agents.nodes import (
    planner_node,
    log_analyzer_node,
    rag_searcher_node,
    reasoner_node,
    memory_node
)

async def join_node(state: InvestigationState) -> dict:
    """Empty node that acts as a join point before reasoning."""
    return {}

def build_investigation_graph():
    """
    Builds and compiles the investigation graph.
    """

    graph = StateGraph(InvestigationState)

    # Register all nodes
    graph.add_node("planner", planner_node)
    graph.add_node("log_analyzer", log_analyzer_node)
    graph.add_node("rag_searcher", rag_searcher_node)
    graph.add_node("reasoner", reasoner_node)
    graph.add_node("memory", memory_node)
    graph.add_node("join", join_node)

    # Entry point
    graph.set_entry_point("planner")

    graph.add_edge("planner", "log_analyzer")


    graph.add_edge("log_analyzer", "rag_searcher")
    graph.add_edge("log_analyzer", "memory")

    graph.add_edge("rag_searcher", "reasoner")
    graph.add_edge("memory", "reasoner")
    
    graph.add_edge("reasoner", END)

    return graph.compile()

# Compile once at module load time
investigation_graph = build_investigation_graph()