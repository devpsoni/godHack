import streamlit as st
import cohere
import sqlite3
import hashlib
import uuid
from dataclasses import dataclass
from get_api_keys import get_api_key_from_trusted_source
from data_extractor import extract_text_from_pdf, extract_text_from_word_document, extract_text_from_ppt

# Initialize session state
if 'user' not in st.session_state:
    st.session_state.user = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = None

@dataclass
class CONFIG:
    COHERE_API_KEY = get_api_key_from_trusted_source(trusted=True)

# Database setup
conn = sqlite3.connect('user_data.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (username TEXT PRIMARY KEY, password TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS chats
             (id TEXT PRIMARY KEY, username TEXT, title TEXT, messages TEXT)''')
conn.commit()

def cohere_output_generation(question, context):
    co = cohere.Client(CONFIG.COHERE_API_KEY)
    response = co.generate(
        model="command",
        truncate="END",
        prompt=f"Question: {question}\nContext: {context}\nAnswer:",
        max_tokens=1024
    )
    return response.generations[0].text.strip()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def signup(username, password):
    hashed_password = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login(username, password):
    hashed_password = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed_password))
    return c.fetchone() is not None

def save_chat(username, title, messages):
    chat_id = str(uuid.uuid4())
    c.execute("INSERT INTO chats VALUES (?, ?, ?, ?)", (chat_id, username, title, str(messages)))
    conn.commit()
    return chat_id

def get_user_chats(username):
    c.execute("SELECT id, title FROM chats WHERE username=?", (username,))
    return c.fetchall()

def get_chat_messages(chat_id):
    c.execute("SELECT messages FROM chats WHERE id=?", (chat_id,))
    result = c.fetchone()
    return eval(result[0]) if result else []

# Set page config
st.set_page_config(layout="wide", page_title="Barnaby - AI Research Assistant")

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FFFFFF;
    }
    .stSidebar {
        background-color: #1E1E1E;
        padding: 2rem 1rem;
    }
    .stButton > button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #45a049;
    }
    .stTextInput > div > div > input {
        background-color: #3C3C3C;
        color: #FFFFFF;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .chat-message.user {
        background-color: #2B2B2B;
    }
    .chat-message.bot {
        background-color: #3C3C3C;
    }
</style>
""", unsafe_allow_html=True)

# Main content
if not st.session_state.user:
    st.title("Welcome to Barnaby")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_button"):
            if login(login_username, login_password):
                st.session_state.user = login_username
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")
    
    with tab2:
        st.subheader("Sign Up")
        signup_username = st.text_input("Username", key="signup_username")
        signup_password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up", key="signup_button"):
            if signup(signup_username, signup_password):
                st.success("Signup successful. Please log in.")
            else:
                st.error("Username already exists.")

else:
    # Sidebar for logged-in users
    with st.sidebar:
        st.title("Barnaby")
        st.write(f"Welcome, {st.session_state.user}!")
        
        uploaded_file = st.file_uploader("Upload New Document", type=["pdf", "docx", "pptx"])
        
        if st.button("New Chat", key="new_chat_button"):
            st.session_state.messages = []
            st.session_state.current_chat_id = None
        
        st.subheader("Your Chats")
        chats = get_user_chats(st.session_state.user)
        for chat_id, title in chats:
            if st.button(title, key=f"chat_{chat_id}"):
                st.session_state.messages = get_chat_messages(chat_id)
                st.session_state.current_chat_id = chat_id
        
        if st.button("Logout", key="logout_button"):
            st.session_state.user = None
            st.session_state.messages = []
            st.session_state.current_chat_id = None
            st.experimental_rerun()

    # Main chat interface
    if uploaded_file is not None:
        try:
            file_type = uploaded_file.name.split(".")[-1]
            
            if file_type == "pdf":
                context = extract_text_from_pdf(uploaded_file)
            elif file_type == "docx":
                context = extract_text_from_word_document(uploaded_file)
            elif file_type == "pptx":
                context = extract_text_from_ppt(uploaded_file)
            
            st.session_state.messages = [{
                "role": "assistant",
                "content": f"""Hey there! You've uploaded {uploaded_file.name}.

Barnaby can help you analyze this document in several ways:

1. Extract key information
2. Summarize content
3. Answer specific questions
4. Identify main themes or topics

What would you like to know about this document?"""
            }]
            
            chat_title = f"Chat about {uploaded_file.name}"
            st.session_state.current_chat_id = save_chat(st.session_state.user, chat_title, st.session_state.messages)
        except Exception as e:
            st.error(f"An error occurred while processing the file: {str(e)}")

    # Display chat messages
    if st.session_state.messages:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about the document:"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        if 'context' in locals():
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = cohere_output_generation(prompt, context)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Save updated chat
            if st.session_state.current_chat_id:
                c.execute("UPDATE chats SET messages=? WHERE id=?", (str(st.session_state.messages), st.session_state.current_chat_id))
                conn.commit()
        else:
            with st.chat_message("assistant"):
                st.write("Please upload a document before asking questions.")

    st.markdown("---")
    st.caption("For the free version, we only provide you with the ability to upload files less than 1000 pages for business purposes. Contact us at barnaby@example.com")