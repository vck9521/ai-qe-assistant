from dotenv import load_dotenv
import os
import openai
import streamlit as st
from streamlit_extras.colored_header import colored_header
from PIL import Image
import st_functions
from assistant import *
import time
import re
import logging
from streamlit_extras.bottom_container import bottom

# Load environment variables
load_dotenv()
load_dotenv(dotenv_path=".env_secret", override=True)

# Fetch the assistant id
assistant_id = os.getenv("QE_ASSISTANT_ID")
client = openai
# API KEY
openai.api_key = os.getenv("QE_AI_OPENAI_API_KEY")

# Initialize session state
if 'start_chat' not in st.session_state:
    st.session_state.start_chat = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = None
if 'uploaded_file_names' not in st.session_state:
    st.session_state.uploaded_file_names = []
if 'file_texts' not in st.session_state:
    st.session_state.file_texts = []
if 'openai_files' not in st.session_state:
    st.session_state.openai_files = []
if 'show_confirm' not in st.session_state:
    st.session_state.show_confirm = False  # Check if the restart confirmation dialog should be shown

# Customizing the UI
st.set_page_config(page_title="Kiwi.ai", page_icon=":kiwifruit:")

# Load CSS
st_functions.load_css("ui_enhancements/style.css")

# Load the image (Logo)
logo = Image.open("images/Gemini_Generated_Image_6c6kcu6c6kcu6c6k.png")

# CUSTOMIZING THE SIDEBAR
# Add the logo to the sidebar
st.sidebar.image(logo, width=100)

# CUSTOMIZING THE MAIN PAGE
with bottom():
    st.caption("Kiwi can make mistakes. Contact vkim@equilar.com for any questions or inquiries.")

st.title("Kiwi, Your Personal QE Assistant")
colored_header(label="Hi, I'm Kiwi the QE! :kiwifruit:", description="Ask me anything related to testing!",
               color_name="violet-70")

# File Uploader Section
uploaded_files = st.file_uploader("Upload Files", type=["docx", "html", "json", "pdf", "txt"],
                                  accept_multiple_files=True, key="uploader")
st.write("Please read https://platform.openai.com/docs/assistants/tools/file-search for supported file types.")

# Process Newly Uploaded Files
if uploaded_files:
    new_files = [file for file in uploaded_files if file.name not in st.session_state.uploaded_file_names]
    if new_files:
        st.session_state.uploaded_file_names.extend([file.name for file in new_files])
        with st.spinner('Kiwi is processing your file(s) . . .'):
            for new_file in new_files:
                try:
                    # Save the uploaded file temporarily
                    temp_file_path = f"temp_{new_file.name}"
                    with open(temp_file_path, "wb") as f:
                        f.write(new_file.getbuffer())

                    # Upload to OpenAI
                    status_text = st.empty()
                    status_text.text(f"Converting file {new_file.name} for OpenAI...")
                    with open(temp_file_path, "rb") as file_to_upload:
                        openai_file = client.files.create(
                            file=file_to_upload,
                            purpose='assistants'
                        )
                    logging.info(f"Uploaded file: {openai_file}")
                    st.session_state.openai_files.append(openai_file.id)

                    # Process file content
                    file_text = extract_text_from_file(new_file)
                    st.session_state.file_texts.append(file_text)

                    # Clean up the temporary file
                    os.remove(temp_file_path)

                    st.success(f"Kiwi successfully processed your uploaded file: {new_file.name}!", icon="✅")
                except Exception as e:
                    st.error(f"Kiwi was unable to process your uploaded file: {new_file.name}. Error: {str(e)}",
                             icon="🚨")

# Start Chat Button
if st.sidebar.button("Start Chat"):
    st.session_state.start_chat = True
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

# Creating Restart Button
st.sidebar.markdown("**If you want to restart/reset Kiwi, click the button below:**")

if st.sidebar.button("🔄 Restart/Reset Kiwi 🔄 "):
    st.session_state.show_confirm = True  # Show confirmation dialog
# Confirmation dialog
if st.session_state.show_confirm:
    st.sidebar.markdown("## Are you sure you want to restart/reset Kiwi? This will delete your current chat log.")
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Yes"):
            reset_kiwi()

    with col2:
        if st.button("No"):
            st.session_state.show_confirm = False  # Close the dialog
            st.rerun()

# When User Starts Chat
if st.session_state.start_chat:
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4o"

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "tokens" in message:
                st.caption(f"Tokens used: {message['tokens']}")

    # Chat input
    prompt = st.chat_input("Please type here.")

    # Suggestive prompts section
    suggestions_container = st.container()
    with suggestions_container:
        st.write("Try asking:")
        suggestions = [
            "Can you create test cases for me?",
            "Can you review my test cases?",
            "Best practices for being a successful QE",
            "What is regression testing?"
        ]

        # Create suggestion buttons in equal columns
        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                if st.button(suggestion, key=f"suggestion_{i}"):
                    # When a suggestion is clicked, use it as the prompt
                    prompt = suggestion

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Use the ask_openai function
        with st.spinner('Kiwi is responding . . .'):
            assistant_response, thread_id, _, total_tokens = ask_openai(
                prompt,
                file_ids=st.session_state.openai_files,
                thread_id=st.session_state.thread_id
            )
            st.session_state.thread_id = thread_id
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_response,
                "tokens": total_tokens})

        st.rerun()

else:
    st.write("Click 'Start Chat' to begin.")

if st.button("Exit Chat"):
    reset_kiwi()
