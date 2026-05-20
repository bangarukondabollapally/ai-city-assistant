import os
from textwrap import dedent

import requests
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from rich.console import Console
from rich.prompt import Prompt
from tavily import TavilyClient

load_dotenv()

console = Console()

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
        return f"Error: {data.get('message', 'Could not fetch weather')}"
    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    return f"Weather in {city}: {desc}, {temp}°C, Humidity: {humidity}%"

# =========================
# 📰 News Tool (Tavily)
# =========================
@tool
def get_news(city: str) -> str:
    """Get latest news about a city"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "News service is not configured (missing API key)."

    tavily_client = TavilyClient(api_key=api_key)
    response = tavily_client.search(
        query=f"latest news in {city}",
        search_depth="basic",
        max_results=3,
    )
    results = response.get("results", [])
    if not results:
        return f"No news found for {city}"
    news_list = []
    for r in results:
        title = r.get("title", "No title")
        url = r.get("url", "")
        snippet = r.get("content", "")
        news_list.append(
            f"- {title}\n  🔗 {url}\n  📝 {snippet[:150]}..."
        )
    return f"Latest news in {city}:\n\n" + "\n\n".join(news_list)

# =========================
# 🧠 Agent
# =========================
def create_city_agent() -> AgentExecutor:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        console.print("[bold red]Error: GROQ_API_KEY not found in environment variables.[/bold red]")
        raise ValueError("GROQ_API_KEY not set")
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    prompt = ChatPromptTemplate.from_messages([
        ("system", dedent("""
        You are a helpful city assistant.

        Use tools whenever needed.

        Do NOT show:
        - function calls
        - tool syntax
        - JSON
        - XML tags

        Only return clean natural language responses to the user.
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
# 💬 CLI Loop
# =========================
def main():
    agent = create_city_agent()
    console.print("[bold green]🏙️ City Agent | type 'exit' to quit[/bold green]\n")

    while True:
        user_input = Prompt.ask("You")
        if user_input.lower() == "exit":
            break

        try:
            response = agent.invoke({"input": user_input, "chat_history": []})
            console.print(f"\n[bold cyan]Bot:[/bold cyan] {response['output']}\n")
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")


if __name__ == "__main__":
    main()