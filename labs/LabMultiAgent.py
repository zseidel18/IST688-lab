import asyncio, os, time
import requests
import streamlit as st
from agents import Agent, Runner, function_tool

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
MODEL = "gpt-5-mini"


# location can be a city, a zip code, an airport code ('SYR'),
# or a landmark ('Eiffel+Tower')
# note: hard codes units to degrees Fahrenheit
def get_current_weather(location):
    url = f'https://wttr.in/{location}?format=j1'
    response = requests.get(url, timeout=10)

    if response.status_code != 200:
        raise Exception(f'wttr.in error: status {response.status_code}')

    try:
        data = response.json()
    except ValueError:
        # unknown locations come back as plain text, not JSON
        raise Exception(f'Could not find a location named {location}')

    try:
        # j1 has three top-level sections:
        #   current_condition -- one entry, conditions right now
        #   weather           -- three entries, one per day, each with
        #                        min/max, astronomy, and hourly forecasts
        #   nearest_area      -- the location wttr.in actually matched
        current = data['current_condition'][0]

        today = data["weather"][0]
        nearest = data["nearest_area"][0]

        matched_city = nearest["areaName"][0]["value"]
        matched_region = nearest["region"][0]["value"]
        matched_country = nearest["country"][0]["value"]

        # Store the hourly forecast so the bot can consider how the
        # weather will change throughout the day.
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
                    "chance_of_rain_percent": int(
                        hour["chanceofrain"]
                    ),
                    "chance_of_snow_percent": int(
                        hour["chanceofsnow"]
                    ),
                    "wind_mph": float(hour["windspeedMiles"]),
                }
            )

        # The remaining values were added for the clothing and
        # outdoor-activity recommendations.
        return {
            'location': location,
            'temperature': float(current['temp_F']),
            'description': current['weatherDesc'][0]['value'],

            "matched_location": (
                f"{matched_city}, "
                f"{matched_region}, "
                f"{matched_country}"
            ),

            "current": {
                "temperature_F": float(current["temp_F"]),
                "feels_like_F": float(current["FeelsLikeF"]),
                "description": current["weatherDesc"][0]["value"],
                "humidity_percent": int(current["humidity"]),
                "wind_mph": float(current["windspeedMiles"]),
                "wind_direction": current["winddir16Point"],
                "precipitation_inches": float(
                    current["precipInches"]
                ),
                "visibility_miles": float(
                    current["visibilityMiles"]
                ),
                "uv_index": int(current["uvIndex"]),
            },

            "today": {
                "minimum_temperature_F": float(
                    today["mintempF"]
                ),
                "maximum_temperature_F": float(
                    today["maxtempF"]
                ),
                "sunrise": today["astronomy"][0]["sunrise"],
                "sunset": today["astronomy"][0]["sunset"],
                "hourly_forecast": hourly_forecast,
            },
        }

    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise Exception(
            "wttr.in returned weather data in an unexpected format."
        ) from error


# Weather tool
@function_tool
def get_weather(location: str = "Syracuse, NY") -> dict:
    """Return current weather and today's hourly forecast in Fahrenheit.
    Accept a city, ZIP code, airport code, or landmark.
    """
    return get_current_weather(location)


# Specialist agents
weather_agent = Agent(
    name="Weather agent",
    instructions=(
        "Call get_weather for the requested location. Summarize the "
        "current conditions and today's forecast, including temperatures, "
        "feels-like temperature, wind, precipitation chances, and changes "
        "throughout the day. Include the matched location. Report facts "
        "only, with no clothing or activity advice. If the location cannot "
        "be found or the tool fails, explain the problem without inventing data."
    ),
    tools=[get_weather],
    model=MODEL,
)

stylist_agent = Agent(
    name="Stylist agent",
    instructions=(
        "Use the weather information provided to recommend clothing "
        "and useful items to bring today. Consider temperature, feels-like "
        "temperature, wind, precipitation, and changes throughout the day. "
        "Keep your advice practical and concise. Do not invent weather data."
    ),
    model=MODEL,
)

activity_agent = Agent(
    name="Activity agent",
    instructions=(
        "Use the weather information provided to suggest appropriate "
        "outdoor activities and the best times for them today. Include "
        "relevant weather precautions and indoor alternatives if needed. "
        "Keep your advice concise. Do not invent weather data."
    ),
    model=MODEL,
)


# Manager agent
manager_agent = Agent(
    name="Manager",
    instructions=(
        "First call weather_report for the user's location. If no location "
        "is provided, use Syracuse, NY. Check that the matched location "
        "corresponds to the requested location. If the location is invalid, "
        "the match is clearly wrong, or weather information is unavailable, "
        "explain the problem and ask for a valid location. Do not continue "
        "with recommendations in that case. Otherwise, send the weather "
        "report to both clothing_advice and activity_advice. Combine their "
        "responses into one clear, concise answer with a weather summary, "
        "clothing, useful items, outdoor activities, and any weather warnings."
    ),
    tools=[
        weather_agent.as_tool(
            tool_name="weather_report",
            tool_description=(
                "Get a factual summary of current weather and today's "
                "forecast for a location."
            ),
        ),
        stylist_agent.as_tool(
            tool_name="clothing_advice",
            tool_description=(
                "Recommend clothing and useful items based on the "
                "provided weather report."
            ),
        ),
        activity_agent.as_tool(
            tool_name="activity_advice",
            tool_description=(
                "Recommend outdoor activities and suitable times based "
                "on the provided weather report."
            ),
        ),
    ],
    model=MODEL,
)


# Run helper
@st.cache_resource
def get_event_loop():
    return asyncio.new_event_loop()


def run(agent, prompt):
    start = time.perf_counter()
    result = get_event_loop().run_until_complete(Runner.run(agent, prompt))
    return result, time.perf_counter() - start


# Streamlit interface
st.title("What to Wear Crew")

st.write(
    "Enter a city to receive clothing and outdoor-activity "
    "suggestions based on today's weather. If the box is left "
    "blank, the app will use Syracuse, NY."
)

location = st.text_input(
    "City, state, or country",
    placeholder="Example: Syracuse, NY",
)

if st.button("Get advice"):
    location = location.strip() or "Syracuse, NY"

    with st.spinner("Checking the weather and preparing advice..."):
        try:
            result, seconds = run(
                manager_agent,
                f"What should I wear and do today in {location}?",
            )

            with st.chat_message("assistant"):
                st.write(result.final_output)

            usage = result.context_wrapper.usage
            with st.expander("Behind the scenes"):
                st.write(
                    f"Model requests: {usage.requests} · "
                    f"Tokens: {usage.total_tokens:,} · "
                    f"Time: {seconds:.1f}s · "
                    f"Answered by: {result.last_agent.name}"
                )

                for item in result.new_items:
                    if item.type == "tool_call_item":
                        st.write(
                            f"{item.agent.name} called {item.raw_item.name}: "
                            f"{item.raw_item.arguments}"
                        )
                    elif item.type == "tool_call_output_item":
                        st.write(f"result: {str(item.output)[:300]}")
                    elif item.type == "handoff_output_item":
                        st.write(
                            f"handoff: {item.source_agent.name} -> "
                            f"{item.target_agent.name}"
                        )

        except Exception as error:
            st.error(f"Unable to create recommendations: {error}")
