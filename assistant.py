import openai
import os
import streamlit as st
import time
import logging as log
import re
import json
import PyPDF2
import pandas as pd

QE_ASSISTANT_ID = os.getenv("QE_ASSISTANT_ID")

client = openai

# API KEY
openai.api_key = os.getenv("QE_AI_OPENAI_API_KEY")


# https://www.youtube.com/watch?v=2lGrFbpHpz4&t=1385s

# New function for OpenAI interaction
def ask_openai(user_message, file_ids=None, thread_id=None, chat=None):
    if not thread_id:
        thread = client.beta.threads.create()
        thread_id = thread.id

    attachments = [
        {
            "file_id": file_id,
            "tools": [
                {
                    "type": "file_search"
                }
            ]
        }
        for file_id in file_ids
    ] if file_ids else []

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message,
        attachments=attachments
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=os.getenv("QE_ASSISTANT_ID")
    )

    if run.status == 'completed':
        messages = client.beta.threads.messages.list(
            thread_id=thread_id
        )
        log.info(f"OpenAI usage: {run.usage}")
        total_tokens = run.usage.total_tokens
        log.info(f"OpenAI asst response: {messages.data[0]}")
        assistant_response = messages.data[0].content[0].text.value

        # remove text like "【12:0†source】" from content value
        assistant_response = re.sub(r"【\d+:\d+†source】", "", assistant_response)

        return assistant_response, thread_id, None, total_tokens
    else:
        raise Exception(f"Failed to get response {run.status} from OpenAI: {run}")


def extract_text_from_file(uploaded_file):
    file_type = uploaded_file.type
    file_text = ""

    # Extract text based on file type
    if file_type == "application/pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        for page in reader.pages:
            file_text += page.extract_text()

    # elif file_type == "text/csv":
    #     df = pd.read_csv(uploaded_file)
    #     file_text = df.to_string()

    elif file_type == "application/json":
        file_text = json.dumps(json.load(uploaded_file), indent=2)

    elif file_type == "text/plain":
        file_text = uploaded_file.read().decode('utf-8')

    return file_text


# Function to reset Kiwi
def reset_kiwi():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# def find_or_create_vector_store(file_ids):
#     vector_store = client.beta.vector_stores.create(name="Quality Engineer", file_ids=file_ids,
#                                                     expires_after={"anchor": "last_active_at", "days": 1})
#     return vector_store
#
#
# def upload_file_to_openai(location):
#     # Send File to OpenAI
#     file = client.files.create(file=open(location, "rb"), purpose='assistants')
#
#     # Delete the temporary file
#     os.remove(location)
#
#     return file.id
#
#
# def update_assistant(vector_store):
#     assistant = client.beta.assistants.update(
#         assistant_id=QE_ASSISTANT_ID,
#         tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
#     )
#
#     log.info("Assistant_id: {} has been updated with vector store: {}".format(assistant.id, vector_store.id))
#
#     return assistant.id
#
#
# def startAssistantThread(prompt, vector_id):
#     # Initiate Messages
#     messages = [{"role": "user", "content": prompt}]
#
#     # Create the Thread
#     tool_resources = {"file_search": {"vector_store_ids": [vector_id]}}
#     thread = client.beta.threads.create(messages=messages, tool_resources=tool_resources)
#
#     return thread.id
#
#
# def runAssistant(thread_id, assistant_id):
#     run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id,
#                                           instructions="Your name is Kiwi because it sounds like 'QE'. You are an accomplished quality engineer who can "
#                                                        "create well-detailed test cases based on  provided given specs when provided by the user. "
#                                                        "You can also provide feedback if a user shares their own test cases. ",
#                                           tools=[{"type": "file_search"}])
#     return run
#
#
# def checkRunStatus(thread_id, run_id):
#     run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
#     return run.status
#
#
# def retrieveThread(thread_id):
#     thread_messages = client.beta.threads.messages.list((thread_id))
#     list_messages = thread_messages.data
#     thread_messages = []
#     for message in list_messages:
#         obj = {}
#         obj['content'] = message.content[0].text.value
#         obj['role'] = message.role
#         thread_messages.append(obj)
#     return thread_messages[::-1]
