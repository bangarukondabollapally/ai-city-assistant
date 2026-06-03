import os
from textwrap import dedent

import requests
import streamlit as st
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from tavily import TavilyClient

os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
os.environ["OPENWEATHER_API_KEY"] = st.secrets["OPENWEATHER_API_KEY"]
os.environ["TAVILY_API_KEY"] = st.secrets["TAVILY_API_KEY"]


@tool
def get_weather(city: str) -> str:
    """Get current weather of a city"""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={os.getenv('OPENWEATHER_API_KEY')}&units=metric"
    data = requests.get(url, timeout=10).json()

    if str(data.get("cod")) != "200":
        return f"Weather data not found for {city}: {data.get('message', 'Unknown error')}"

    return dedent(f"""
    🌦️ Weather in {city}
    Condition: {data["weather"][0]["description"]}
    Temperature: {data["main"]["temp"]}°C
    Feels Like: {data["main"]["feels_like"]}°C
    Humidity: {data["main"]["humidity"]}%
    Wind Speed: {data["wind"]["speed"]} m/s
    """).strip()


@tool
def get_news(city: str) -> str:
    """Get latest news about a city"""
    results = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")).search(
        query=f"latest breaking news in {city}",
        search_depth="basic",
        max_results=3,
    ).get("results", [])

    if not results:
        return f"No latest news found for {city}"

    return "\n\n".join([
        f"📰 {r.get('title', 'No title')}\n🔗 {r.get('url', '')}\n{r.get('content', '')[:180]}..."
        for r in results
    ])


@st.cache_resource
def load_agent() -> AgentExecutor:
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    prompt = ChatPromptTemplate.from_messages([
        ("system", dedent("""
        You are a helpful city assistant.
        - Use tools whenever needed
        - Never show function calls or JSON/XML
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
    return AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True, max_iterations=5)


st.set_page_config(page_title="City AI Agent", page_icon="🏙️", layout="wide")
st.title("🏙️ City AI Agent")
st.caption("Get weather and latest news for any city.")

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

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if prompt := st.chat_input("Ask about any city..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🤖 Thinking..."):
            try:
                response = load_agent().invoke({"input": prompt, "chat_history": []})
                output = response["output"]
                st.write(output)
                st.session_state.messages.append({"role": "assistant", "content": output})
            except Exception as e:
                st.error(f"Error: {str(e)}")