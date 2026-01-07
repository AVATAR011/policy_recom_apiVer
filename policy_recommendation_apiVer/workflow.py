from langgraph.graph import StateGraph, END
from state import AgentState
from agents import router_node, collector_node, analyst_node, sales_node



# --- 2. CONDITIONAL LOGIC ---
def decide_next_node(state: AgentState):
    """
    Reads the 'next_step' from state and returns the node name.
    """
    if state["next_step"] == "router":
        return "router"
    return state["next_step"]

# --- 3. GRAPH CONSTRUCTION ---
def create_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("collector", collector_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("sales", sales_node)

    # Entry Point
    workflow.set_entry_point("router")

    # --- ROUTER LOGIC ---
    workflow.add_conditional_edges(
        "router",
        decide_next_node,
        {
            "collector": "collector",
            "analyst": "analyst",
            "sales": "sales",
            "router": "router"
        }
    )
    
    # --- END POINTS ---
    workflow.add_edge("collector", END)
    workflow.add_edge("analyst", END)
    
    def route_sales(state):
        if state.get("next_step") == "analyst":
            return "analyst"
        return END

    workflow.add_conditional_edges("sales", route_sales, {"analyst": "analyst", END: END})

    return workflow.compile()