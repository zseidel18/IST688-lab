import streamlit as st
from openai import OpenAI
import sys
from pathlib import Path
from PyPDF2 import PdfReader


# A fix for working with ChromaDB on Streamlit Community Cloud
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import chromadb


#### USING CHROMA DB WITH OPENAI EMBEDDINGS ####

# Create OpenAI client
if 'openai_client' not in st.session_state:
    st.session_state.openai_client = OpenAI(api_key=st.secrets.OPENAI_API_KEY)


# A function that will add documents to collection
# collection = ChromaDB collection, already established
# text = extracted text from PDF files
# Embeddings inserted into the collection from OpenAI
def add_to_collection(collection, text, file_name):

    # Create an embedding
    client = st.session_state.openai_client
    response = client.embeddings.create(
        input=text,
        model='text-embedding-3-small'
    )

    # Get the embedding
    embedding = response.data[0].embedding

    # Add embedding and document to ChromaDB
    collection.add(
        documents=[text],
        ids=file_name,
        embeddings=[embedding]
    )


#### EXTRACT TEXT FROM PDF ####
# This function extracts text from each syllabus
# to pass to add_to_collection
def extract_text_from_pdf(pdf_path):

    reader = PdfReader(pdf_path)

    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


#### POPULATE COLLECTION WITH PDFs ####
# This function uses extract_text_from_pdf
# and add_to_collection to put syllabi in ChromaDB collection
def load_pdfs_to_collection(folder_path, collection):

    loaded = 0

    for pdf_path in Path(folder_path).glob('*.pdf'):

        text = extract_text_from_pdf(pdf_path)

        add_to_collection(
            collection,
            text,
            pdf_path.name
        )

        loaded += 1

    return loaded


#### CREATE CHROMADB ####

# Only create ChromaDB once
if 'Lab4_VectorDB' not in st.session_state:

    # Create ChromaDB client
    chroma_client = chromadb.PersistentClient(path='./ChromaDB_for_Lab')
    collection = chroma_client.get_or_create_collection('Lab4Collection')

    # Check if collection is empty and load PDFs
    if collection.count() == 0:
        loaded = load_pdfs_to_collection('./Lab-04-Data/', collection)

    # Store collection in session state
    st.session_state.Lab4_VectorDB = collection

else:
    collection = st.session_state.Lab4_VectorDB


#### MAIN APP ####

st.title('Lab 4: Chatbot using RAG')


#### QUERYING A COLLECTION -- ONLY USED FOR TESTING ####

topic = st.sidebar.text_input(
    'Topic',
    placeholder='Type your topic (e.g., GenAI)...'
)

if topic:
    client = st.session_state.openai_client
    response = client.embeddings.create(
        input=topic,
        model='text-embedding-3-small'
    )

    # Get the embedding
    query_embedding = response.data[0].embedding

    # Get the text related to this question (this prompt)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3  # The number of closest documents to return
    )

    # Display the results
    st.subheader(f'Results for: {topic}')

    for i in range(len(results['documents'][0])):
        doc = results['documents'][0][i]
        doc_id = results['ids'][0][i]

        st.write(f'**{i+1}. {doc_id}**')

else:
    st.info('Enter a topic in the sidebar to search the collection')