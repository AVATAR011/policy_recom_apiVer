import os
import glob
import re
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters.character import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

CATEGORY_REGEX = r"(?:Category|Type|Class)\s*[:\-]\s*([a-zA-Z\s]+)"

def extract_category_from_text(text):
    """
    Scans the text to find the 'Category: X' field.
    """
    match = re.search(CATEGORY_REGEX, text, re.IGNORECASE)
    if match:
        # Found it! Clean up the result (e.g., "Health " -> "Health")
        return match.group(1).strip()
    return "General" # Fallback if field not found

def load_policies_from_folder(folder_path="policies"):
    """
    Scans the specified folder for .pdf and .txt files, loads them, 
    and creates a Persistent VectorStore.
    """
    # 1. Get all file paths
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    all_files = pdf_files + txt_files
    
    if not all_files:
        return None, f"No PDF or TXT files found in '{folder_path}' folder."

    all_chunks = []
    
    # 2. Load each file
    print(f"Loading {len(all_files)} files from {folder_path}...")
    for file_path in all_files:
        try:
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path)
                
            data = loader.load()

            if not data: continue

            first_page_text = data[0].page_content
            detected_category = extract_category_from_text(first_page_text)
            
            file_name = os.path.basename(file_path)
            print(f"   📄 File: {file_name} -> Detected Category: [{detected_category}]")

            for doc in data:
                doc.metadata["source"] = file_name
                # This enables the strict filtering in your Agent
                doc.metadata["category"] = detected_category
                
            # Split text
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = text_splitter.split_documents(data)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    # 3. Create Vector Store (THE FIX: Added persist_directory)
    if all_chunks:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # This directory is where the database will be saved on your computer
        persist_dir = "./chroma_db"
        
        vectorstore = Chroma.from_documents(
            documents=all_chunks, 
            embedding=embeddings, 
            persist_directory=persist_dir  # <--- THIS FIXES THE ERROR
        )
        return vectorstore, f"Successfully loaded {len(all_files)} documents."
    
    return None, "Failed to process documents."

def save_learned_case(profile, chosen_policy_name, reason, folder="policies"):
    """
    Appends a successful recommendation to a text file.
    """
    file_path = os.path.join(folder, "learned_data.txt")
    
    entry = f"""
    [LEARNED CASE STUDY]
    Scenario: User is {profile.get('age')} years old, works as {profile.get('occupation')}, budget {profile.get('budget')}.
    Concern: {profile.get('concerns')}
    Successful Recommendation: {chosen_policy_name}
    Why it worked: {reason}
    ---------------------------------------------------
    """
    
    with open(file_path, "a") as f:
        f.write(entry)
        
    print(f"✅ Learned new case: {chosen_policy_name}")