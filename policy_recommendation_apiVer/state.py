from typing import TypedDict, Any, Optional, List, Dict

class AgentState(TypedDict):
    messages: list              # Chat history
    
    # --- NEW DYNAMIC FIELDS ---
    current_category: Optional[str]  # E.g., "Health", "Vehicle", "Pet", "Agriculture"
    category_confirmed: bool
    
    collected_data: Dict[str, Any]   # Flexible storage: {"age": 30, "pet_breed": "Labrador"}
    missing_fields: List[str]        # List of fields we still need to ask for
    
    next_step: str              # Router decision
    recommended_plan: Optional[str]
    policy_context: Optional[str]

    logic_context: Optional[str]

    vectorstore: Any
    last_asked_field: Optional[str]