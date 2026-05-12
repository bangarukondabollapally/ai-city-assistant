from dotenv import load_dotenv
import os
import requests
load_dotenv()

from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.messages import HumanMessage
from tavily import TavilyClient
from rich import print

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
        return f"Error: {data.get('message', 'Could not fetch weather')}"
    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    return f"Weather in {city}: {desc}, {temp}°C, Humidity: {humidity}%"

# =========================
# 📰 News Tool (Tavily)
# =========================
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def get_news(city: str) -> str:
    """Get latest news about a city"""
    response = tavily_client.search(
        query=f"latest news in {city}",
        search_depth="basic",
        max_results=3
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
# 🛡️ Human Approval Middleware
# =========================
@wrap_tool_call
def human_approval(request, handler):
    """Ask for human approval before every tool call."""
    tool_name = request.tool_call["name"]
    confirm = input(f"\n⚠️ Agent wants to call '{tool_name}'. Approve? (yes/no): ")
    if confirm.lower() != "yes":
        return ToolMessage(
            content="Tool call denied by user.",
            tool_call_id=request.tool_call["id"]
        )
    return handler(request)

# =========================
# 🧠 Agent + Runnables
# =========================
llm = ChatGroq(model="llama-3.3-70b-versatile")

agent = create_agent(
    llm,
    tools=[get_weather, get_news],
    system_prompt="""You are a helpful city assistant.

Use tools whenever needed.

Do NOT show:
- function calls
- tool syntax
- JSON
- XML tags

Only return clean natural language responses to the user.""",
    middleware=[human_approval]
)

# Runnables chain
format_input = RunnableLambda(
    lambda x: {"messages": [HumanMessage(content=x["query"])]}
)
extract_output = RunnableLambda(
    lambda x: str(x["messages"][-1].content)
)

chain = RunnablePassthrough() | format_input | agent | extract_output

# =========================
# 💬 CLI Loop
# =========================
print("[bold green]🏙️ City Agent | type 'exit' to quit[/bold green]\n")

while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        break
    response = chain.invoke({"query": user_input})
    print(f"\n[bold cyan]Bot:[/bold cyan] {response}\n")