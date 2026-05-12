import streamlit as st
from dotenv import load_dotenv
import os
import requests

load_dotenv()

from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain.agents import create_agent
from tavily import TavilyClient

# =========================
# 🌦️ Weather Tool
# =========================
@tool
def get_weather(city: str) -> str:
    """Get current weather of a city"""

    api_key = os.getenv("OPENWEATHER_API_KEY")

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

    response = requests.get(url)

    data = response.json()

    if str(data.get("cod")) != "200":
        return f"Weather data not found for {city}"

    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    return f"""
🌦️ Weather in {city}

Condition: {desc}
Temperature: {temp}°C
Feels Like: {feels_like}°C
Humidity: {humidity}%
Wind Speed: {wind} m/s
"""


# =========================
# 📰 News Tool
# =========================
@tool
def get_news(city: str) -> str:
    """Get latest news about a city"""

    tavily_client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )

    response = tavily_client.search(
        query=f"latest breaking news in {city}",
        search_depth="basic",
        max_results=3
    )

    results = response.get("results", [])

    if not results:
        return f"No latest news found for {city}"

    news_list = []

    for r in results:

        title = r.get("title", "No title")

        url = r.get("url", "")

        snippet = r.get("content", "")

        news_list.append(
            f"""
📰 {title}

🔗 {url}

{snippet[:180]}...
"""
        )

    return "\n\n".join(news_list)


# =========================
# 🧠 Agent
# =========================
@st.cache_resource
def load_agent():

    llm = ChatGroq(
        model="llama-3.3-70b-versatile"
    )

    agent = create_agent(
        model=llm,
        tools=[get_weather, get_news],

        system_prompt="""
You are a helpful city assistant.

Rules:
- Use tools whenever needed
- Never show function calls
- Never show JSON/XML
- Give concise answers
- Use weather tool only for weather queries
- Use news tool only for news queries
- Use both tools only if user asks for both
"""
    )

    return agent


# =========================
# 🎨 Streamlit UI
# =========================
st.set_page_config(
    page_title="City AI Agent",
    page_icon="🏙️",
    layout="wide"
)

st.title("🏙️ City AI Agent")

st.caption(
    "Get weather and latest news for any city."
)

# =========================
# Sidebar
# =========================
with st.sidebar:

    st.header("🛠️ Available Tools")

    st.success("🌦️ Weather Tool")

    st.success("📰 News Tool")

    st.divider()

    st.header("💡 Examples")

    st.info("Weather in Hyderabad")

    st.info("Latest news in Mumbai")

    st.info("Weather and news for Delhi")

    st.divider()

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []

        st.rerun()


# =========================
# Session State
# =========================
if "messages" not in st.session_state:

    st.session_state.messages = []


# =========================
# Display Messages
# =========================
for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.write(message["content"])


# =========================
# Input Section
# =========================
city = st.text_input(
    "Enter City Name"
)

query_type = st.selectbox(
    "Select Request Type",
    ["Weather", "News", "Both"]
)


# =========================
# Generate Query
# =========================
final_query = ""

if city:

    if query_type == "Weather":

        final_query = f"What is the weather in {city}?"

    elif query_type == "News":

        final_query = f"What is the latest news in {city}?"

    else:

        final_query = (
            f"Give weather and latest news for {city}"
        )


# =========================
# Ask Agent
# =========================
if st.button("Ask Agent"):

    if not city:

        st.error("Please enter a city name.")

    else:

        st.session_state.messages.append({
            "role": "user",
            "content": final_query
        })

        with st.chat_message("user"):

            st.write(final_query)

        with st.chat_message("assistant"):

            with st.spinner("🤖 Thinking..."):

                try:

                    agent = load_agent()

                    response = agent.invoke(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": final_query
                                }
                            ]
                        },
                        config={
                            "recursion_limit": 5
                        }
                    )

                    output = response["messages"][-1].content

                    st.write(output)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": output
                    })

                except Exception as e:

                    st.error(
                        f"Error: {str(e)}"
                    )