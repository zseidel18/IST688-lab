import os
import requests
import streamlit as st
from langchain.agents import create_agent

def get_weather_data(location: str = "Syracuse, NY") -> dict:
    """Return current weather and today's forecast for one location,
    including temperatures in Fahrenheit, wind, and rain or snow chances.
    Accepts city names, ZIP codes, airport codes, and landmarks.
    Defaults to Syracuse, NY when no argument is provided.
    """
    url = f'https://wttr.in/{location}?format=j1'
    response = requests.get(url, timeout=10)

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

agent = create_agent(
    model="openai:gpt-5-mini",
    tools=[get_weather_data],
    system_prompt=(
        "You are a practical weather assistant. Use the weather tool "
        "when weather information is needed. If no location is supplied, "
        "use Syracuse, NY. Using the returned weather information, give "
        "clear and concise recommendations for today. Include:\n"
        "1. Clothing to wear\n"
        "2. Useful items to bring\n"
        "3. Appropriate outdoor activities\n"
        "4. Any safety or changing-weather warnings\n\n"
        "Do not invent weather values that were not returned by the "
        "weather tool."
    ),
)

st.title("What to Wear Bot")

location = st.text_input(
    "City, state, or country",
    placeholder="Example: Syracuse, NY",
)

if st.button("Get advice"):
    location = location.strip() or "Syracuse, NY"

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"What should I wear in {location}?",
                }
            ]
        }
    )

    with st.chat_message("assistant"):
        st.write(result["messages"][-1].content)