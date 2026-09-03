import streamlit as st
from openai import OpenAI
from PyPDF2 import PdfReader


def read_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


# Show title and description.
st.title("Lab 2 - Document Summarizer")
st.write(
    "Provide a document to summarize using your selected summary type "
    "from the options in the sidebar."
)

# Get OpenAI API key from Streamlit secrets.
openai_api_key = st.secrets["OPENAI_API_KEY"]

# Initialize the OpenAI client.
client = OpenAI(api_key=openai_api_key)

# Let the user select the type of summary.
summary_type = st.sidebar.selectbox(
    "Choose a summary type",
    [
        "Summarize the document in 100 words",
        "Summarize the document in 2 connecting paragraphs",
        "Summarize the document in 5 bullet points"
    ]
)

# Let the user select between models.
use_advanced_model = st.sidebar.checkbox("Use advanced model")

if use_advanced_model:
    model_to_use = "gpt-5-mini"
else:
    model_to_use = "gpt-5-nano"

# Let the user upload a file.
uploaded_file = st.file_uploader(
    "Upload a document (.pdf)", type=("pdf")
)

if uploaded_file:

    # Process the uploaded PDF.
    document = read_pdf(uploaded_file)

    # Define a system message.
    system_message = "You are a helpful assistant that summarizes documents."

    # Prepare the messages to the LLM.
    messages = [
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": f"Here's a document: {document} \n\n---\n\n {summary_type}"
        }
    ]

    # Generate an answer using the OpenAI API.
    stream = client.chat.completions.create(
        model=model_to_use,
        messages=messages,
        stream=True,
    )

    # Stream the response to the app using `st.write_stream`.
    st.write_stream(stream)