import streamlit as st
import os
from utils import load_policies_from_folder # Import the new function
from workflow import create_graph

# --- PAGE CONFIG ---
st.set_page_config(page_title="Modular Policy Bot", layout="wide")
st.title("🤖 Modular Multi-Agent Bot")

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I can help you with Health, Vehicle, Pet, and Property insurance. How can I assist you today?"}
    ]
# if "user_profile" not in st.session_state:
#     st.session_state.user_profile = {}
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
# if "uploader_key" not in st.session_state:
#     st.session_state.uploader_key = 0
if "recommended_plan" not in st.session_state:
    st.session_state.recommended_plan = None  # <--- ADD THIS
if "policy_context" not in st.session_state:
    st.session_state.policy_context = None
if "collected_data" not in st.session_state:
    st.session_state.collected_data = {}
if "current_category" not in st.session_state:
    st.session_state.current_category = None
if "last_asked_field" not in st.session_state:
    st.session_state.last_asked_field = None
if "category_confirmed" not in st.session_state:
    st.session_state.category_confirmed = False  # [NEW] Default to False

# --- SIDEBAR ---
with st.sidebar:
    st.header("Policy Database")
    # Check if folder exists
    policy_folder = "policies"
    if not os.path.exists(policy_folder):
        os.makedirs(policy_folder)
        st.warning(f"Created '{policy_folder}' folder. Please add PDFs there.")

    # Status Indicator
    if st.button("Load/Refresh Policies"):
        with st.spinner("Indexing policies..."):
            vs, msg = load_policies_from_folder(policy_folder)
            if vs:
                st.session_state.vectorstore = vs
                st.success(msg)
            else:
                st.error(msg)

    
    # Clear / Reset Button
    if st.button("Reset Conversation"):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("Debug State")
    st.write(f"Category: {st.session_state.current_category}")
    st.write(f"Waiting For: {st.session_state.last_asked_field}")
    st.json(st.session_state.collected_data)

# --- AUTO-LOAD ON STARTUP ---
# If DB is empty, try loading automatically once
# if st.session_state.vectorstore is None:
#     vs, msg = load_policies_from_folder(policy_folder)
#     if vs:
#         st.session_state.vectorstore = vs
#         print("Auto-loaded policies on startup.")
        
# --- CHAT LOOP ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Type your message...")

if user_input:

    # 2. Add User Message to History
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # --- REMOVED THE MANUAL SIMULATION BLOCK HERE ---

    # 3. Prepare Inputs for Graph
    graph_messages = []
    for m in st.session_state.messages:
        role = "human" if m["role"] == "user" else "ai"
        graph_messages.append((role, m["content"]))
    
    inputs = {
        "messages": graph_messages,
        "collected_data": st.session_state.collected_data, # Pass persistent data
        "current_category": st.session_state.current_category,
        "category_confirmed": st.session_state.category_confirmed,
        "last_asked_field": st.session_state.last_asked_field,
        "vectorstore": st.session_state.vectorstore,
        "recommended_plan": st.session_state.recommended_plan,
        "policy_context": st.session_state.policy_context
    }
    
    # 4. Run Graph (The ONLY logic source now)
    with st.spinner("Agent is thinking..."):
        try:
            app = create_graph()
            result = app.invoke(inputs)
            
            st.session_state.recommended_plan = result.get("recommended_plan")
            st.session_state.last_asked_field = result.get("last_asked_field")
            st.session_state.collected_data = result.get("collected_data", {})
            st.session_state.current_category = result.get("current_category")
            st.session_state.category_confirmed = result.get("category_confirmed", False)
            st.session_state.policy_context = result.get("policy_context")
            
            last_msg = result["messages"][-1]

            # Handle LangGraph message format
            if isinstance(last_msg, tuple):
                role, content = last_msg
            else:
                role = last_msg.type if hasattr(last_msg, 'type') else "unknown"
                content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

            # [FIX 2] Fallback Logic if AI is silent
            if role == "ai":
                st.session_state.messages.append({"role": "assistant", "content": content})
                with st.chat_message("assistant"):
                    st.markdown(content)
            else:
                # If role is 'human', it means the graph returned the user's message back (no new AI output)
                fallback_msg = "I'm sorry, I didn't quite understand that. Could you please specify which type of insurance (Health, Vehicle, Pet, etc.) you are interested in?"
                st.session_state.messages.append({"role": "assistant", "content": fallback_msg})
                with st.chat_message("assistant"):
                    st.markdown(fallback_msg)
            # st.rerun()
        except Exception as e:
            st.error(f"An error occurred: {e}")