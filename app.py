import os
from textwrap import dedent

import requests
import streamlit as st
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from tavily import TavilyClient

load_dotenv()

# =========================
# 🌦️ Weather Tool
# =========================
@tool
def get_weather(city: str) -> str:
    """Get current weather of a city"""

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "Weather service is not configured (missing API key)."

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url, timeout=10)
    data = response.json()

    if str(data.get("cod")) != "200":
        return f"Weather data not found for {city}: {data.get('message', 'Unknown error')}"

    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    return dedent(f"""
    🌦️ Weather in {city}
    Condition: {desc}
    Temperature: {temp}°C
    Feels Like: {feels_like}°C
    Humidity: {humidity}%
    Wind Speed: {wind} m/s
    """).strip()


# =========================
# 📰 News Tool
# =========================
@tool
def get_news(city: str) -> str:
    """Get latest news about a city"""

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "News service is not configured (missing API key)."

    tavily_client = TavilyClient(api_key=api_key)

    response = tavily_client.search(
        query=f"latest breaking news in {city}",
        search_depth="basic",
        max_results=3,
    )
    results = response.get("results", [])

    if not results:
        return f"No latest news found for {city}"

    news_list = []
    for r in results:
        title = r.get("title", "No title")
        url = r.get("url", "")
        snippet = r.get("content", "")
        news_list.append(f"📰 {title}\n🔗 {url}\n{snippet[:180]}...")

    return "\n\n".join(news_list)


# =========================
# 🧠 Agent
# =========================
@st.cache_resource
def load_agent() -> AgentExecutor:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        st.error("GROQ_API_KEY not found in environment variables.")
        st.stop()
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = ChatPromptTemplate.from_messages([
        ("system", dedent("""
        You are a helpful city assistant.

        Rules:
        - Use tools whenever needed
        - Never show function calls
        - Never show JSON/XML
        - Give concise answers
        - Use weather tool only for weather queries
        - Use news tool only for news queries
        - Use both tools only if user asks for both
        """).strip()),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    tools = [get_weather, get_news]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=5,
    )


# =========================
# 🎨 Streamlit UI
# =========================
st.set_page_config(page_title="City AI Agent", page_icon="🏙️", layout="wide")
st.title("🏙️ City AI Agent")
st.caption("Get weather and latest news for any city.")

# Sidebar
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

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
if prompt := st.chat_input("Ask about any city..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🤖 Thinking..."):
            try:
                agent = load_agent()
                response = agent.invoke({"input": prompt, "chat_history": []})
                output = response["output"]
                st.write(output)
                st.session_state.messages.append({"role": "assistant", "content": output})
            except Exception as e:
                st.error(f"Error: {str(e)}")