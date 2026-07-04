from langgraph.graph import StateGraph, END
from backend.agents.state import InvestigationState
from backend.agents.nodes import (
    planner_node,
    log_analyzer_node,
    rag_searcher_node,
    reasoner_node
)

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

    # Entry point
    graph.set_entry_point("planner")

    # Planner always fans out to all evidence collectors in parallel
    graph.add_edge("planner", "log_analyzer")
    graph.add_edge("planner", "rag_searcher")


    # All evidence collectors feed into reasoner
    graph.add_edge("log_analyzer", "reasoner")
    graph.add_edge("rag_searcher", "reasoner")

    # Reasoner always ends the investigation
    graph.add_edge("reasoner", END)

    return graph.compile()

# Compile once at module load time
investigation_graph = build_investigation_graph()