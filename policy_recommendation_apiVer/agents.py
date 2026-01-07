import json
import re
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from state import AgentState
from schemas import get_required_fields, get_broad_category_options, get_specific_categories_for_broad

# Load environment variables from .env file
load_dotenv()

# Initialize Gemini 2.5 Flash
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7
)

# --- HELPER: ROBUST JSON PARSER ---

def load_rules():
    if os.path.exists("policy_rules.json"):
        with open("policy_rules.json", "r") as f:
            return json.load(f)
    return {}

POLICY_RULES = load_rules()

def get_logic_for_file(filename):
    """
    Robustly finds the rule even if path or extension differs slightly.
    """
    # 1. Try exact match
    if filename in POLICY_RULES:
        return POLICY_RULES[filename]['rule_text']
    
    # 2. Try matching just the base name (e.g., "policy.pdf" matches "policies/policy.pdf")
    basename = os.path.basename(filename)
    if basename in POLICY_RULES:
        return POLICY_RULES[basename]['rule_text']

    return None

def clean_and_parse_json(response_text):
    """
    Strips markdown code blocks and finds the JSON object.
    """
    try:
        # 1. Remove Markdown code fences (e.g., ```json ... ```)
        text = re.sub(r"```json", "", response_text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)
        
        # 2. Find the first outer curly brace pair
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            json_str = match.group()
            return json.loads(json_str)
    except Exception as e:
        print(f"JSON PARSING ERROR: {e} | Text: {response_text}")
    return {}

# --- HELPER: INTENT CLASSIFIER ---
def classify_intent_and_extract(user_text, current_category, potential_fields=None, is_confirming_category=False):
    """
    Decides if the user is:
    1. Switching Category (e.g., "Actually, I need farm insurance")
    2. Answering a Question (e.g., "I am 30 years old")
    """
    
    valid_broad_cats = ", ".join(get_broad_category_options())

    if is_confirming_category:
        prompt = f"""
        User Input: "{user_text}"
        System asked: "Are you looking for {current_category} insurance?"
        
        Task:
        1. Did the user agree (Yes/Correct/Right)? -> Set "confirmed": true
        2. If user corrects it (e.g., "No, I want Car Insurance") -> Set "new_category": "Vehicle".
        
        Output JSON:
        {{
            "confirmed": true/false,
            "new_category": "BroadCategoryName" or null,
            "extracted_data": {{}}
        }}
        """
        response = llm.invoke(prompt)
        return clean_and_parse_json(response.content)

    extraction_instruction = ""
    if potential_fields:
        extraction_instruction = f"""
        ### 🕵️ DATA EXTRACTION TASK
        We are looking for specific values to fill these EXACT KEYS: {potential_fields}
        
        INSTRUCTIONS:
        1. Analyze the user's input.
        2. If you find a value that fits one of our keys, extract it using THAT EXACT KEY NAME.
        3. IGNORE values for keys we are NOT looking for.
        
        MAPPING EXAMPLES:
        - Target Keys: ['age_of_eldest_member', 'occupation']
        - User Input: "I am 24 years old teacher"
        - Output: {{ "age_of_eldest_member": "24", "occupation": "Teacher" }}
        
        - Target Keys: ['sum_insured_preference']
        - User Input: "I want 5 lakhs cover"
        - Output: {{ "sum_insured_preference": "5 Lakhs" }}
        """
    
    prompt = f"""
    Analyze Input: "{user_text}"
    Context: Category={current_category}, WaitingFor={potential_fields}

    {extraction_instruction}
    
    Task:
    1. Identify if the user wants to SWITCH insurance types (e.g., "Actually show me car insurance").
    2. CLASSIFY any switch into: [{valid_broad_cats}].
    3. EXTRACT relevant profile data, mapping it strictly to the Target Keys provided above.
    
    Valid Categories:
    {valid_broad_cats}

    Output JSON format only:
    {{
        "switch_detected": true/false,
        "new_category": "ExactCategoryString" (e.g., "Health & Accident", "Vehicle") or null,
        "extracted_data": {{ "KEY": "VALUE" }}
    }}
    """
    
    response = llm.invoke(prompt)
    return clean_and_parse_json(response.content)

# --- 1. ROUTER NODE (The Brain) ---
def router_node(state: AgentState):
    messages = state["messages"]
    last_user_msg = messages[-1][1] if messages else ""
    current_cat = state.get("current_category")
    is_confirmed = state.get("category_confirmed", False)
    collected = state.get("collected_data") or {}
    last_asked = state.get("last_asked_field")
    plan_status = state.get("recommended_plan")
    
    # Initialize if empty
    if "collected_data" not in state:
        state["collected_data"] = {}

    print(f"🧠 ROUTER: Analyzing '{last_user_msg}' | Cat: {current_cat} (Confirmed: {is_confirmed}) | Plan: {plan_status}")

    # --- SCENARIO A: We are waiting for Category Confirmation ---
    if current_cat and not is_confirmed and last_asked == "category_confirmation":
        analysis = classify_intent_and_extract(last_user_msg, current_cat, is_confirming_category=True)
        
        if analysis.get("confirmed"):
            print("✅ Category Confirmed!")
            return {
                "category_confirmed": True,
                "last_asked_field": None,
                "next_step": "router"
            }
        elif analysis.get("new_category"):
            print(f"🔄 Correction: {current_cat} -> {analysis['new_category']}")
            return {
                "current_category": analysis["new_category"],
                "category_confirmed": False,
                "last_asked_field": None,
                "next_step": "collector"
            }
        else:
            return {"category_confirmed": True, "next_step": "router"}

    potential_fields_to_extract = get_required_fields(current_cat) if current_cat else []    
    # A. Analyze Intent
    analysis = classify_intent_and_extract(last_user_msg, current_cat, potential_fields_to_extract)
    
    # B. Handle Category Switch
    if analysis.get("new_category") and analysis["new_category"] != current_cat:
        new_cat = analysis["new_category"]
        return {
                "current_category": analysis["new_category"],
                "category_confirmed": False,
                "collected_data": analysis.get("extracted_data", {}),
                "recommended_plan": None,
                "policy_context": None,
                "next_step": "collector",
                "last_asked_field": None
            }
            

    # C. Update Data (Merge extracted info)
    if analysis.get("extracted_data"):
        new_data = analysis["extracted_data"]
        clean_data = {k.lower(): v for k, v in new_data.items() if v}
        collected.update(clean_data)

        print(f"🔥 UPDATED PROFILE: {collected}")
    
    if not current_cat:
        return {"next_step": "collector", "collected_data": collected}
    
    if current_cat and not is_confirmed:
        return {
            "next_step": "collector",
            "current_category": current_cat,
            "category_confirmed": False
        }
    
    if plan_status == "Done":
        return {
            "next_step": "sales", 
            "collected_data": collected
        }

    required = get_required_fields(current_cat)
    missing = [f for f in required if f not in collected or collected[f] in [None, ""]]
    
    if missing:
        return {
            "next_step": "collector", 
            "collected_data": collected, 
            "missing_fields": missing,
            "current_category": current_cat
        }
    else:
        return {
            "next_step": "analyst", 
            "collected_data": collected,
            "current_category": current_cat,
        }

def collector_node(state: AgentState):
    current_cat = state.get("current_category")
    is_confirmed = state.get("category_confirmed", False)
    missing = state.get("missing_fields", [])

    if current_cat and not is_confirmed:
        return {
            "messages": [("ai", f"It sounds like you are looking for **{current_cat}** Insurance. Is that correct?")],
            "last_asked_field": "category_confirmation"
        }

    if not current_cat:
        return {
            "messages": [("ai", "I can help with Health, Vehicle, Pet, and Property insurance. Which one are you interested in?")],
            "last_asked_field": "category"
        }

    if missing:
        fields_list_str = ", ".join(missing)
        
        question_prompt = f"""
        You are a helpful insurance assistant. 
        The user wants {current_cat} insurance.
        We need to know: [{fields_list_str}].
        
        Task:
        Generate a polite message asking for these details. 
        
        IMPORTANT FORMATTING RULES:
        1. Start with a polite opening sentence.
        2. Present the questions as a NUMBERED LIST.
        3. Keep questions short and clear.

        Example Output:
        "To verify your eligibility, could you please provide:
        1. Your Age?
        2. Your Occupation?"

        Output ONLY the question.
        """
        response = llm.invoke(question_prompt)
        question = response.content.strip().replace('"', '')
        
        return {
            "messages": [("ai", question)],
            "last_asked_field": "bulk_questions" 
        }
    
    return {}
    
def analyst_node(state: AgentState):
    collected = state.get("collected_data")
    broad_category = state.get("current_category")
    vectorstore = state.get("vectorstore")

    print(f"🕵️ ANALYST: Searching for {broad_category} policies matching {collected}")

    if not vectorstore:
        return {"messages": [("ai", "Error: No policy database loaded.")], "recommended_plan": None}
    
    specific_subtypes = get_specific_categories_for_broad(broad_category)

    query = f"{broad_category} insurance policy features coverage"
    for key, val in collected.items():
        query += f" {val}"
    
    try:
        docs = vectorstore.similarity_search(query, k=10, filter={"category": {"$in": specific_subtypes}} if specific_subtypes else None)
        retrieved_docs = [d.page_content for d in docs]
    except:
        print("⚠️ Advanced filtering failed, using broad search")
        docs = vectorstore.similarity_search(query, k=10)

    unique_policies = {}
    logic_context = ""

    for doc in docs:
        source = doc.metadata.get('source', 'Unknown')
        doc_cat = doc.metadata.get('category', 'General')
        if specific_subtypes and doc_cat not in specific_subtypes:
            continue
        if source not in unique_policies:
            unique_policies[source] = doc.page_content

            rule_text = get_logic_for_file(source)
            if rule_text:
                logic_context += f"\n👉 PRICING RULE FOR '{source}':\n{rule_text}\n"
            else:
                logic_context += f"\n❌ NO RULE FOUND FOR '{source}'. Check filename matching.\n"
    
    if len(unique_policies) < 3:
        print("⚠️ Few matches found. Expanding search for alternatives...")
        query_broad = f"{broad_category} insurance policy features"
        docs_broad = vectorstore.similarity_search(query_broad, k=5)
        for doc in docs_broad:
            source = doc.metadata.get('source', 'Unknown')
            if source not in unique_policies:
                unique_policies[source] = doc.page_content
    
    num_found = len(unique_policies)
    context_text = ""
    i = 1
    for source, content in list(unique_policies.items())[:3]:
        context_text += f"\n--- POLICY OPTION {i}: {source} ---\n{content[:1500]}...\n"
        i += 1
    
    if num_found == 0:
        return {
            "messages": [("ai", f"I searched the database but couldn't find any {broad_category} policies. Please try a different category.")],
            "recommended_plan": "Done"
        }
    
    elif num_found == 1:
        prompt = f"""
        You are a smart Insurance Underwriter.
        User Category Need: {broad_category}
        
        User Profile: {json.dumps(collected)}
        
        I searched the database and found ONLY ONE relevant policy:
        {context_text}

        STRICT PRICING LOGIC (USE THIS EXACTLY):
        {logic_context}
        
        YOUR TASK:
        1. State clearly: "I found one policy that matches your criteria."
        2. Recommend this policy and explain its benefits.
        3. Do NOT invent other policies to make up numbers.
        4. Mention if this policy meets the user's specific budget/needs stated in the profile.
        5. CALCULATE the premium using the "PRICING RULE" above.
        6. DO NOT use generic formulas. Use the specific numbers in the rule (e.g. "Rs 11,350").
        7. If the user's age/sum insured matches a range in the rule, use that price.
        8. If values are missing, ASSUME defaults (e.g. Age: 30, Sum Insured: 5 Lakhs) and STATE THEM.

        ### 💰 Premium Calculation
        * **User Profile Used:** Age: [X], SI: [Y]
        * **Base Rate:** ₹[Insert Number] (Annual/Monthly - STATE WHICH)
        * **Duration:** [e.g. 1 Year / 2 Years]
        * **Tax:** +18% GST
        * **Total Estimated Premium:** ₹[Final Amount] FOR [Duration]
        """
    
    else:
        prompt = f"""
        You are a smart Insurance Underwriter.

        User Profile: {json.dumps(collected)}
        User Category Need: {broad_category}
        
        I have found {len(unique_policies)} distinct policy documents:
        {context_text}

        PRICING RULES (STRICT):
        {logic_context}
        
        YOUR TASK:
        1. Recommend up to 3 DISTINCT policies.
        2. CALCULATE PREMIUMS using the "PRICING RULES" above.
        
        ### 🧠 INTELLIGENT VARIABLE MAPPING (CRITICAL)
        If the User Profile is missing exact fields, use these logical mappings:
        - **Risk Class (Accident):** - Doctors, Office, Architects -> Use "Class 1" Rate
        - Sales, Field, Site Work -> Use "Class 2" Rate
        - Manual Labor, Drivers, Mechanics -> Use "Class 3" Rate
        - **Engine CC (Vehicle):**
        - If 'Car' & unknown CC -> Assume < 1000cc (Small Car)
        - If 'Bike' & unknown CC -> Assume 75-150cc (Standard Bike)
        - **Sum Insured:**
        - If user said "Cheap" -> Use lowest SI in table.
        - If user said "Best" -> Use highest SI in table.
        - If unknown -> Default to 5 Lakhs (Health) or 15 Lakhs (PA).
        - **Travel Duration:** - If unknown -> Assume "14 Days" (Standard Trip).

        ### 💰 Premium Calculation Output Format
        For each recommended policy, you MUST show the math:
        * **Policy:** [Name]
        * **Inputs Used:** Age: [X], SI: [Y], Class: [Z] (State if Assumed)
        * **Base Formula:** [Show the rule you used]
        * **Math:** [Value] x [Rate] = [Result]
        * **Tax:** +18% GST
        * **Final Estimate:** ₹[Total] [Per Year/Per Trip]

        Recommendation:
        """
    
    response = llm.invoke(prompt)
    recommendation = response.content
    
    return {
        "recommended_plan": "Done", 
        "policy_context": context_text,
        "logic_context": logic_context,
        "messages": [("ai", recommendation)]
    }

def sales_node(state: AgentState):
    """
    Handles Q&A AFTER a policy has been recommended.
    """
    last_user_msg = state["messages"][-1][1]
    context = state.get("policy_context", "No specific policy context available.")
    
    logic_context = state.get("logic_context", "")
    collected = state.get("collected_data", {})
    
    if "other" in last_user_msg.lower() or "different" in last_user_msg.lower():
        return {
            "messages": [("ai", "Sure, let me look for other options based on your profile...")],
            "recommended_plan": None,
            "next_step": "analyst"
        }

    prompt = f"""
    You are an insurance expert. Use ONLY the data below.
    
    Policy Data (Qualitative): 
    {context}

    USER PROFILE: {json.dumps(collected)}
    User Question: "{last_user_msg}"

    AVAILABLE PRICING RULES:
    {logic_context}
    
    Task: 
    1. Answer the user's question.
    2. If the user asks for a price (e.g., "2 year premium"), find the rule in the text above.
    3. LOOKUP the specific rate for their Age/Vehicle.
    4. APPLY the duration math (e.g. Rule says: "2 Years = 2 * Base - 5%").
    5. OUTPUT A REAL NUMBER. Do not show variables like "Base Rate * 2". Show "5000 * 2 = 10000".
    6. If the logic text above is empty, apologize and say you cannot calculate.
    7. CRITICAL: You MUST state if the Final Amount is "Per Year", "Per Month", or "For X Years".

    OUTPUT FORMAT:
    [Answer to question]

    ### 🧮 Premium Calculation
    **Assumptions:** [List assumptions]
    **Formula:** [Show the formula found in logic]
    **Math:** [Step 1] -> [Step 2]
    **Total Estimated Premium:** [Final Result]

    Example Output:
    "Based on the rules for [Policy Name]:
    1. Base Annual Premium: ₹5,000 (Per Year)
    2. Duration Selected: 2 Years
    3. Calculation: ₹5,000 x 2 Years = ₹10,000
    4. Discount (5%): -₹500
    5. GST (18%): +₹1,710
    
    **Total Payable:** ₹11,210 (For 2 Years)"
    """
    response = llm.invoke(prompt)
    
    return {"messages": [("ai", response.content)]}