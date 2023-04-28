import os
import sys
import pathlib
import streamlit as st
from streamlit_chat import message
import openai
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import PythonCodeTextSplitter
from langchain.llms import OpenAI
from langchain.chains import VectorDBQA
from langchain.document_loaders import TextLoader
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import RetrievalQA
from typing import List
from langchain.schema import Document

# Hide traceback
st.set_option('client.showErrorDetails', False)

# Setting page title and header
st.set_page_config(page_title="CODE CHAT", page_icon=":robot_face:")
st.markdown("<h1 style='text-align: center; color: red;'>CODE CHAT</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>Perform queries on your GIT REPO</h1>", unsafe_allow_html=True)

# Initialise session state variables
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

# Ask user to enter OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key", type='password')

# Create a button for the user to submit their API key
if st.button('Submit'):
    # Set the OpenAI API key as an environment variable
    os.environ["OPENAI_API_KEY"] = openai_api_key
    # Set the OpenAI API key directly
    openai.api_key = openai_api_key
    
    # Check if the API key is valid by making a simple API call
    try:
        models = openai.Model.list()
        st.success("API key is valid!")
    except Exception as e:
        st.error("Error testing API key: {}".format(e))

# Get code from a repository and split the file into content and metadata

def get_repo_docs(repo_path):
    repo = pathlib.Path(repo_path)
    print ("Iterating through git files")
    # Iterate over only .ipynb files in the repo (including subdirectories) 
    for codefile in repo.glob("**/*.ipynb"):
            print(codefile)
            with open(codefile, "r") as file:
                rel_path = codefile.relative_to(repo)
                yield Document(page_content=file.read(), metadata={"source": str(rel_path)})

# Use the Python code text splitter from Langchain to create chunks
def get_source_chunks (repo_path): 
    source_chunks = []
    print ("Creating source chunks")
    # Create a PythonCodeTextSplitter object for splitting the code
    splitter = PythonCodeTextSplitter(chunk_size=1024, chunk_overlap=30)
    for source in get_repo_docs(repo_path):
        for chunk in splitter.split_text(source.page_content):
            source_chunks.append(Document(page_content=chunk, metadata=source.metadata))
    return source_chunks

# Define function to generate response from user input
# This will also create the embeddings and store them in ChromaDB if it does not exist already
def generate_response(input_text):
    # Define the path of the repository and Chroma DB 
    REPO_PATH = '<Enter absolute path of your local git repo>'
    CHROMA_DB_PATH = f'./chroma/{os.path.basename(REPO_PATH)}'

    vector_db = None

    # Check if Chroma DB exists
    if not os.path.exists(CHROMA_DB_PATH):
        # Create a new Chroma DB
        print(f'Creating Chroma DB at {CHROMA_DB_PATH}...')
        source_chunks = get_source_chunks(REPO_PATH)
        ## Creating embeddings using the OpenAIEmbeddings, will incur costs
        vector_db = Chroma.from_documents(source_chunks, OpenAIEmbeddings(), persist_directory=CHROMA_DB_PATH) 
        vector_db.persist()
    else:
        # Load an existing Chroma DB
        print(f'Loading Chroma DB from {CHROMA_DB_PATH}...')
        vector_db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=OpenAIEmbeddings())

    # Load a QA chain
    qa_chain = load_qa_chain(OpenAI(temperature=1), chain_type="stuff")
    qa = RetrievalQA(combine_documents_chain=qa_chain, retriever=vector_db.as_retriever())
    query_response = qa.run(input_text)
    return query_response

# From here is the code for creating the chat bot using streamlit and streamlit_chat
# container for chat history
response_container = st.container()

# container for text box
input_container = st.container()

with input_container:
    # Create a form for user input
    with st.form(key='my_form', clear_on_submit=True):
        user_input = st.text_area("You:", key='input', height=100)
        submit_button = st.form_submit_button(label='Send')

    if submit_button and user_input:
        # If user submits input, generate response and store input and response in session state variables
        try:
            query_response = generate_response(user_input)
            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(query_response)
        except Exception as e:
            st.error("An error occurred: {}".format(e))


if st.session_state['generated']:
    # Display chat history in a container
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
            # message(st.session_state["generated"][i], key=str(i))
            #st.text(st.session_state["past"][i])
            st.code(st.session_state["generated"][i],language="python", line_numbers=False)