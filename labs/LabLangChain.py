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
    url = f"https://wttr.in/{location}?format=j1"
    response = requests.get(url, timeout=10)

    if response.status_code != 200:
        raise Exception(f"wttr.in error: status {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        raise Exception(f"Could not find a location named {location}")

    try:
        current = data["current_condition"][0]
        today = data["weather"][0]
        nearest = data["nearest_area"][0]

        matched_city = nearest["areaName"][0]["value"]
        matched_region = nearest["region"][0]["value"]
        matched_country = nearest["country"][0]["value"]

        hourly_forecast = []

        for hour in today["hourly"]:
            raw_time = int(hour["time"])
            hour_24 = raw_time // 100
            time_label = f"{hour_24:02d}:00"

            hourly_forecast.append(
                {
                    "time": time_label,
                    "temperature_F": float(hour["tempF"]),
                    "feels_like_F": float(hour["FeelsLikeF"]),
                    "description": hour["weatherDesc"][0]["value"],
                    "chance_of_rain_percent": int(hour["chanceofrain"]),
                    "chance_of_snow_percent": int(hour["chanceofsnow"]),
                    "wind_mph": float(hour["windspeedMiles"]),
                }
            )

        return {
            "location": location,
            "temperature": float(current["temp_F"]),
            "description": current["weatherDesc"][0]["value"],
            "matched_location": (
                f"{matched_city}, {matched_region}, {matched_country}"
            ),
            "current": {
                "temperature_F": float(current["temp_F"]),
                "feels_like_F": float(current["FeelsLikeF"]),
                "description": current["weatherDesc"][0]["value"],
                "humidity_percent": int(current["humidity"]),
                "wind_mph": float(current["windspeedMiles"]),
                "wind_direction": current["winddir16Point"],
                "precipitation_inches": float(current["precipInches"]),
                "visibility_miles": float(current["visibilityMiles"]),
                "uv_index": int(current["uvIndex"]),
            },
            "today": {
                "minimum_temperature_F": float(today["mintempF"]),
                "maximum_temperature_F": float(today["maxtempF"]),
                "sunrise": today["astronomy"][0]["sunrise"],
                "sunset": today["astronomy"][0]["sunset"],
                "hourly_forecast": hourly_forecast,
            },
        }

    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise Exception(
            "wttr.in returned weather data in an unexpected format."
        ) from error


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

    with st.expander("Behind the scenes"):
        for message in result["messages"]:
            st.write(f"**{message.type}**")
            st.write(message.content)

            if message.type == "ai" and message.tool_calls:
                st.write(message.tool_calls)


# 12a. There are five messages:
# 1. human: My question about Syracuse and the Eiffel Tower.
# 2. ai: The model requests weather for both locations.
# 3. tool: The weather results for Syracuse.
# 4. tool: The weather results for the Eiffel Tower.
# 5. ai: The final clothing and activity recommendations.

# 12b. Its message.content is empty because the model is requesting tools
# instead of writing an answer.
# The requests are in message.tool_calls: one for Syracuse
# and one for the Eiffel Tower.

# 12c. In Lab 5:
# The initial messages list created the user message.
# The first API call created the AI tool requests, which were
# added using messages.append(assistant_message).
# The for tool_call loop ran the weather function for each location.
# messages.append with role="tool" added each weather result.
# The second API call created the final AI answer.
