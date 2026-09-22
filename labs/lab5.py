import json

import requests
import streamlit as st
from openai import OpenAI


# Create the OpenAI client using the API key stored in Streamlit secrets.
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

MODEL = st.secrets.get("OPENAI_MODEL", "gpt-5-mini")

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


# Define the tool that OpenAI is allowed to request.
tools = [
    {
        "type": "function",

        "function": {
            "name": "get_current_weather",

            "description": (
                "Get current weather and today's forecast for a "
                "location. Use Syracuse, NY if no location is provided."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "location": {
                        "type": "string",

                        "description": (
                            "The city and state or city and country, "
                            "for example Syracuse, NY or Lima, Peru."
                        ),
                    }
                },

                "required": ["location"],
            },
        },
    }
]


def create_weather_advice(location):
    """
    Ask OpenAI to request the weather tool and then use the
    returned weather information to create recommendations.
    """

    # Use Syracuse when the user does not provide a location.
    location = location.strip()

    if location == "":
        location = "Syracuse, NY"

    messages = [
        {
            "role": "system",

            "content": (
                "You are a practical weather assistant. Use the "
                "weather tool when weather information is needed. "
                "If no location is supplied, use Syracuse, NY."
            ),
        },

        {
            "role": "user",

            "content": (
                f"What should I wear today in {location}, and what "
                "outdoor activities would be appropriate for the "
                "weather?"
            ),
        },
    ]

    # First OpenAI call:
    # The model receives the available tool and decides whether
    first_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    assistant_message = first_response.choices[0].message

    # Add the model's tool request to the message history.
    messages.append(assistant_message)

    # If the model did not request a tool, return its answer.
    if not assistant_message.tool_calls:
        return assistant_message.content, None

    weather_data = None

    # Run each function requested by the model.
    for tool_call in assistant_message.tool_calls:

        tool_function = tool_call.function.name

        if tool_function == "get_current_weather":

            # The function arguments come back from OpenAI as JSON.
            function_arguments = json.loads(
                tool_call.function.arguments
            )

            tool_location = function_arguments.get("location")

            # Use Syracuse if OpenAI does not include a location.
            if not tool_location:
                tool_location = "Syracuse, NY"

            # The application runs the actual Python function.
            weather_data = get_current_weather(tool_location)

            # Add the weather results to the messages.
            # tool_call_id connects the results to the correct request.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(weather_data),
                }
            )

    if weather_data is None:
        raise Exception(
            "The model requested an unsupported function."
        )

    # Give the model specific instructions for creating the final
    # answer from the weather returned by the function.
    messages.append(
        {
            "role": "system",

            "content": (
                "Using the returned weather information, give clear "
                "and concise recommendations for today. Include:\n"
                "1. Clothing to wear\n"
                "2. Useful items to bring\n"
                "3. Appropriate outdoor activities\n"
                "4. Any safety or changing-weather warnings\n\n"
                "Do not invent weather values that were not returned "
                "by the weather tool."
            ),
        }
    )

    # Second OpenAI call:
    # The model can now see the weather returned by the function
    # and use it to create the final recommendations.
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    final_answer = final_response.choices[0].message.content

    return final_answer, weather_data


# ------------------------------------------------------------------
# Streamlit interface
# ------------------------------------------------------------------

st.title("What to Wear Bot")

st.write(
    "Enter a city to receive clothing and outdoor-activity "
    "suggestions based on today's weather. If the box is left "
    "blank, the app will use Syracuse, NY."
)

location_input = st.text_input(
    "City, state, or country",
    placeholder="Example: Syracuse, NY",
)

if st.button("Get recommendations", type="primary"):

    with st.spinner(
        "Checking the weather and preparing recommendations..."
    ):

        try:
            advice, weather = create_weather_advice(
                location_input
            )

            st.subheader("Today's recommendations")

            st.markdown(advice)

            if weather is not None:

                current = weather["current"]

                st.caption(
                    f"Weather matched to "
                    f"{weather['matched_location']} | "
                    f"{current['temperature_F']:.0f}°F | "
                    f"Feels like "
                    f"{current['feels_like_F']:.0f}°F | "
                    f"{current['description']}"
                )

                with st.expander(
                    "View weather data used by the bot"
                ):
                    st.json(weather)

        except Exception as error:
            st.error(
                f"Unable to create recommendations: {error}"
            )