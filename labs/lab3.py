import streamlit as st
from openai import OpenAI

# Show title and description.
st.title("MY Lab3 question answering chatbot")

# Create an OpenAI client.
if 'client' not in st.session_state:
    api_key = st.secrets["OPENAI_API_KEY"]
    st.session_state.client = OpenAI(api_key=api_key)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "system",
            "content":
                "Answer all questions so that a 10 year old can understand. "
                "After answering a user's question, ask 'Do you want more info?'. "
                "If the user says yes, provide more information about the previous "
                "answer and ask 'Do you want more info?' again. "
                "If the user says no, ask 'What can I help you with?'"
        },
        {
            "role": "assistant",
            "content": "What can I help you with?"
        }
    ]

# Display chat messages from history on app rerun
for msg in st.session_state.messages:
    if msg["role"] != "system":
        chat_msg = st.chat_message(msg["role"])
        chat_msg.write(msg["content"])

# React to user input
if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Find user messages
    user_messages = [
        i for i, msg in enumerate(st.session_state.messages)
        if msg["role"] == "user"
    ]

    # Always keep the system prompt
    system_message = st.session_state.messages[0]

    # Keep the last two user messages and the responses to them
    if len(user_messages) >= 2:
        buffer_messages = [
            system_message
        ] + st.session_state.messages[user_messages[-2]:]
    else:
        buffer_messages = [
            system_message
        ] + st.session_state.messages[user_messages[0]:]

    client = st.session_state.client

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=buffer_messages,
        stream=True
    )

    with st.chat_message("assistant"):
        response = st.write_stream(stream)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )