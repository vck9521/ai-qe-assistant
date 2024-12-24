import openai
import os
import streamlit as st
import time
import logging as log
import re
import json
import PyPDF2
import openpyxl
import pandas as pd
import io
import clipboard


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


# Function to remove Markdown formatting (like italics, bold, etc.)
def clean_markdown(text):
    # Remove italics (single * or _)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # Remove bold (double ** or __)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    return text


def extract_test_cases(text: str) -> list:
    # Clean up any Markdown formatting (e.g., italics, bold)
    text = clean_markdown(text)

    test_case_patterns = [
        r'(Test\s*Case\s*\d+\s*[:-].*?)(?=Test\s*Case|$)',
        r'(Scenario\s*\d+\s*[:-].*?)(?=Scenario|$)',
        r'(\d+\.\s*Test\s*Case.*?)(?=\d+\.\s*Test|$)'
    ]

    test_cases = []
    for pattern in test_case_patterns:
        matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            case_text = match.group(1).strip()

            # Extract components
            title_match = re.search(r"(?:Test Case \d+:|Scenario \d+:)\s*(.*?)(?=\n|$)", case_text)

            objective_match = re.search(
                r"Objective:\s*(.*?)(?=\n\s*(?:Preconditions?:|\s*Steps?:|\s*Expected Result?:)|$)", case_text,
                re.DOTALL)
            preconditions_match = re.search(r"Preconditions?:\s*(.*?)(?=\n\s*(?:Steps?:|\s*Expected Result?:)|$)",
                                            case_text, re.DOTALL)

            # Adjusted regex to capture the full Steps section, including multi-line content (like payloads)
            steps_match = re.search(r"Steps?:\s*(.*?)(?=\n\s*(?:Expected Result?:|$))", case_text, re.DOTALL)
            expected_match = re.search(r"Expected Result:\s*(.*?)(?=\n\s*(?:Test Case|Scenario|$|\Z)|\n[-]{2,}|\n{2,})",
                                       case_text, re.DOTALL)

            # Process steps as a list, adjusting for step numbers already present
            steps = []
            if steps_match:
                step_matches = re.finditer(r"(\d+\.\s*.*?)(?=\n\s*\d+\.|\n\n|$)", steps_match.group(1), re.DOTALL)
                for step in step_matches:
                    # Strip the step number if it's already included
                    step_text = step.group(1).strip()
                    # Remove the leading number (e.g., "1. " or "2. ")
                    step_text = re.sub(r"^\d+\.\s*", "", step_text)
                    steps.append(step_text)

            # Append extracted components
            test_cases.append({
                "title": title_match.group(1).strip() if title_match else "No Title Found",
                "objective": objective_match.group(1).strip() if objective_match else "No Objective Found",
                "preconditions": preconditions_match.group(1).strip() if preconditions_match else "No Preconditions Found",
                "steps": steps if steps else "No Steps Found",
                "expected_results": expected_match.group(1).strip() if expected_match else "No Expected Results Found"
            })

    return test_cases


def download_test_cases(messages):
    # Initialize or reset the download_format state variable
    if "download_format" not in st.session_state:
        st.session_state.download_format = False  # False when no format is selected

    for message in reversed(messages):
        if message["role"] == "assistant":
            structured_data = extract_test_cases(message["content"])

            # If no test cases were found, display an error and return
            if not structured_data:
                st.sidebar.error("No test cases found in most recent Kiwi response.")
                return False

            format_type = st.sidebar.selectbox("Select format", ("CSV", "XLSX", "TXT"), help="Only the most recent Kiwi response is analyzed when finding test cases.")
            st.sidebar.markdown(f"Found **{len(structured_data)} test cases** generated from most recent Kiwi response")

            # Ensure all required columns exist in the structured data
            columns = ['title', 'objective', 'preconditions', 'steps', 'expected_results']
            for col in columns:
                if col not in structured_data[0]:
                    structured_data[0][col] = "No {} data found.".format(col)

            if format_type in ["CSV", "XLSX"]:
                df = pd.DataFrame(structured_data)

                # Ensure steps are in the correct format (a list of strings)
                df['steps'] = df['steps'].apply(
                    lambda steps: '\n'.join([f"{i + 1}) {step}" for i, step in enumerate(steps)]))

                if format_type == "CSV":
                    data = df.to_csv(index=False).encode('utf-8')
                    mime = "text/csv"
                else:
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False, engine='openpyxl')
                    data = buffer.getvalue()
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                text_content = ""
                for case in structured_data:
                    text_content += f"Title: {case['title']}\n"
                    text_content += f"Objective: {case['objective']}\n"
                    text_content += f"Preconditions: {case['preconditions']}\n"
                    text_content += "Steps:\n"
                    for i, step in enumerate(case['steps'], 1):
                        text_content += f"  {i}. {step}\n"
                    text_content += f"Expected Results: {case['expected_results']}\n\n"
                    text_content += "=" * 50 + "\n\n"
                data = text_content.encode('utf-8')
                mime = "text/plain"

            col1, col2 = st.sidebar.columns(2)
            with col1:
                st.download_button(
                    label=f"Download as {format_type}",
                    data=data,
                    file_name=f"test_cases.{format_type.lower()}",
                    mime=mime,
                    key="download_button"
                )
            with col2:
                if st.button("Close"):
                    st.session_state.download_format = False
                    st.rerun()

            return True

    # If no test cases are found, show an error message
    st.sidebar.error("No test cases found in most recent Kiwi response.")
    return False
