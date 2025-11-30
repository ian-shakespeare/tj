import os

from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from sendgrid import Mail, SendGridAPIClient

from .models import Plan
from .tools import calculator, city_information, currency_converter, find_cities_between, find_flights, find_hotels, find_points_of_interest

load_dotenv()

model = ChatOllama(model="gpt-oss:20b", num_ctx=32_000, reasoning=False)
sg_client = SendGridAPIClient(os.getenv("SENDGRID_KEY"))

pathfinder = create_agent(
    model=model,
    system_prompt="\
            You are a planner at a Japan-focused travel agency. \
            You are responsible for building basic vacation itineraries. \
            Your itineraries should only include Japanese cities and the dates they are to be visited. \
            It's important you do NOT include points of interest or finer-grain locations as that information will be gathered by one of your coworkers. \
            You should use available tools to identify what cities MAY be included in an itinerary, and your own judgement for which of those possible cities SHOULD be included. \
            ALWAYS respect the given date ranges.",
    tools=[find_cities_between]
)

explorer = create_agent(
    model=model,
    system_prompt="\
            You are a planner at a Japan-focused travel agency. \
            You are responsible for finding activities or points of interest for a given itinerary (an itinerary will contain only a list of cities and the dates to visit them). \
            You have access to general information for cities, as well as places via Google's Places API. \
            It's important to find a VARIETY of activities and places (Restaurants, attractions, parks, museums etc.). \
            You should ALWAYS use the Google Places API when searching for activities. \
            Otherwise, rely on the general information database. \
            Prefer activities with better ratings. \
            When applicable, include price information for recommended activities.",
    tools=[city_information, find_points_of_interest]
)

booker = create_agent(
    model=model,
    system_prompt="\
            You are a planner at a travel agency. \
            You are responsible for finding hotels and flights (when necessary) for a given itinerary (an itinerary will contain only a list of cities and the dates to visit them). \
            You have access to a hotel and flight search tool. \
            The tools use mock data, so don't be alarmed if the data is nonsensical, use it regardless. \
            NEVER guess what hotels or flights are available, ALWAYS use available tools for such information. \
            Only search for flights when there are no other efficient means of transportation (i.e. high speed rail). \
            Be sure to include price in your response as it will be used by a coworker to price a vacation.",
    tools=[find_flights, find_hotels]
)

# TODO: Update this agent's system prompt
budgeteer = create_agent(
    model=model,
    system_prompt="\
            You are a planner at a travel agency. \
            You are responsible for estimating the total cost of given itinerary. \
            You have access to general price information to estimate food and souvenir costs. \
            ALWAYS use the prices given to you as the basis for your estimate. \
            ALWAYS include relevant currencies in your response. \
            ALWAYS include the total cost in your response as it will be used by a coworker to generate a complete travel plan.",
    tools=[calculator, currency_converter]
)


@tool
def call_pathfinder(query: str) -> str:
    """
    Pathfinder coworker specialized in building a basic city-to-city itinerary.

    Args:
        query: Query to submit to the coworker. Be sure to include the start and endpoints, as well as dates, for the desired vacation.

    Returns:
        str: Coworker response
    """

    result = pathfinder.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content


@tool
def call_explorer(query: str) -> str:
    """
    Explorer coworker specialized in finding points-of-interest and activies along a basic city-to-city itinerary.
    In general, this coworker should be queried with the output from the Pathfinder coworker.

    Args:
        query: Query to submit to the coworker.

    Returns:
        str: Coworker response
    """

    result = explorer.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content


@tool
def call_booker(query: str) -> str:
    """
    Booking coworker specialized in finding hotels and flights (when necessary)

    Args:
        query: Query to submit to the coworker.

    Returns:
        str: Coworker response
    """

    result = booker.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content


@tool
def call_budgeteer(query: str) -> str:
    """
    Budgeteer coworker specialized in estimating the total cost of a vacation.
    In general, this coworker should be queried with the prices gathered from the Explorer and Booker coworkers.

    Args:
        query: Query to submit to the coworker.

    Returns:
        str: Coworker response
    """

    result = budgeteer.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content


receptionist = create_agent(
    model=model,
    system_prompt="\
            You are customer representative at a travel agency focused on Japanese vacations. \
            You are responsible for taking customer requests and creating fun vacation plans. \
            You have several expert coworkers to help you. \
            ALWAYS rely on your coworkers for accurate information. \
            Once you have collected information from your coworkers, you should build a final vacation plan that includes dates, locations, and an estimated total cost. \
            Do NOT include questions in your response. \
            It will be served to a user asyncronously and they will not be able to make further queries.",
    tools=[call_pathfinder, call_explorer, call_booker, call_budgeteer]
)


def send_email(to: str, plan_id: int):
    message = Mail(
        from_email=os.getenv("SENDGRID_FROM_EMAIL"),
        to_emails=to,
        subject="New Travel Japan Plan Is Ready!",
        html_content=f"You can view your new plan <a href='{str(os.getenv("BASE_URL")) + "/plans/" + str(plan_id)}'>in the web app</a>."
    )
    response = sg_client.send(message)
    print(response)


def create_plan(prompt: str, user: User):
    print("### Starting Plan Creation ###")
    try:
        result = receptionist.invoke(
            {"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        title_raw = model.invoke([
            HumanMessage(
                content=f"Create a short (less than 64 character) title for the following travel itinerary: f{content}")
        ]).content
        title = BeautifulSoup(str(title_raw), "html.parser").get_text()

        plan = Plan(title=title, content=content, user=user)
        plan.save()

        send_email(str(user.email), plan.id)
        print("### Finished Creating Plan ###")
    except Exception as e:
        print(f"### Failed To Create Plan: '{str(e)}' ###")
