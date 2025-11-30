import json
import os
import time
import requests

from datetime import datetime, date
from dotenv import load_dotenv
from langchain_core.tools import tool
from pgvector.django import CosineDistance
from typing import Optional, List, Dict, Any

from .documents import EMBEDDER
from .map import GraphMap
from .mocks import FlightOffer, HotelOffer, mock_find_flights, mock_find_hotels
from .models import Chunk

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class GoogleAPIError(Exception):
    """Raised when Google API requests fail"""
    pass


# ============================================================================
# Helper Functions for Google APIs
# ============================================================================


def _geocode_city(city_name: str) -> Dict[str, Any]:
    """
    Geocode a city name to get its coordinates using Google Places API.

    Args:
        city_name: Name of the city to geocode

    Returns:
        Dictionary with city name, latitude, and longitude

    Raises:
        GoogleAPIError: If geocoding fails
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.location,places.formattedAddress",
    }

    data = {"textQuery": city_name, "languageCode": "en"}

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        if not result.get("places"):
            raise GoogleAPIError(f"City '{city_name}' not found")

        place = result["places"][0]
        location = place["location"]

        return {
            "name": place["displayName"]["text"],
            "lat": location["latitude"],
            "lng": location["longitude"],
        }
    except requests.exceptions.RequestException as e:
        raise GoogleAPIError(f"Failed to geocode city '{city_name}': {str(e)}")


# ============================================================================
# Helper Functions for Dates
# ============================================================================


def _parse_datestr(s: str) -> date:
    format = "%Y-%m-%d"
    now = datetime.now()
    d = datetime.strptime(s, format)
    if d < now:
        if d.month < now.month or (d.month == now.month and d.day < now.day):
            d = d.replace(year=now.year + 1)
        else:
            d = d.replace(year=now.year)
    return d


# ============================================================================
# Tool 1: City Finder
# ============================================================================


@tool
def find_cities_between(
    origin: str, destination: str
) -> list[str]:
    """
    Find all cities between two points (origin and destination cities).

    Args:
        origin: Starting city name
        destination: Ending city name

    Returns:
        A list of cities between the origin and destination

    Raises:
        GoogleAPIError: If API requests fail
    """
    graphmap = GraphMap()
    return graphmap.find_cheapest_path(origin, destination)


# ============================================================================
# Tool 2: Points of Interest Finder
# ============================================================================


@tool
def find_points_of_interest(
    city: str,
    categories: Optional[List[str]] = None,
    min_rating: float = 4.0,
    max_results: int = 20,
) -> Dict[str, Any]:
    """
    Find notable locations and attractions in a specified city.

    Args:
        city: City name
        categories: Optional list of categories to filter by
                   (e.g., ["tourist_attraction", "museum", "restaurant"])
        min_rating: Minimum rating threshold (default: 4.0)
        max_results: Maximum number of results to return (default: 20)

    Returns:
        Dictionary containing:
        - city: City name
        - location: City coordinates (lat, lng)
        - points_of_interest: List of POIs with details

    Raises:
        GoogleAPIError: If API requests fail
    """
    print(f"Finding points of interest in {city}...")

    # Default categories if none provided
    if categories is None:
        categories = [
            "tourist_attraction",
            "museum",
            "park",
            "restaurant",
            "shopping_mall",
            "art_gallery",
        ]

    # Step 1: Geocode the city
    city_location = _geocode_city(city)

    print(f"Searching in {city_location['name']}...")

    # Step 2: Search for places in each category
    all_pois = []

    for category in categories:
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount,"
            "places.priceLevel,places.types,places.editorialSummary,"
            "places.currentOpeningHours,places.photos",
        }

        data = {
            "textQuery": f"{category} in {city}",
            "languageCode": "en",
            "maxResultCount": 10,
            "locationBias": {
                "circle": {
                    "center": {
                        "latitude": city_location["lat"],
                        "longitude": city_location["lng"],
                    },
                    "radius": 15000,  # 15km radius
                }
            },
        }

        try:
            response = requests.post(
                url, json=data, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()

            for place in result.get("places", []):
                # Filter by minimum rating
                rating = place.get("rating", 0)
                if rating < min_rating:
                    continue

                # Extract photo references (up to 3)
                photos = []
                for photo in place.get("photos", [])[:3]:
                    photo_name = photo.get("name", "")
                    if photo_name:
                        photos.append(
                            f"https://places.googleapis.com/v1/{photo_name}/media?key={GOOGLE_API_KEY}&maxHeightPx=400&maxWidthPx=400"
                        )

                # Extract opening hours
                opening_hours = None
                if "currentOpeningHours" in place:
                    hours = place["currentOpeningHours"]
                    opening_hours = {
                        "open_now": hours.get("openNow", False),
                        "weekday_text": hours.get("weekdayDescriptions", []),
                    }

                poi = {
                    "name": place["displayName"]["text"],
                    "place_id": place["id"],
                    "category": category,
                    "address": place.get("formattedAddress", "N/A"),
                    "location": {
                        "lat": place["location"]["latitude"],
                        "lng": place["location"]["longitude"],
                    },
                    "rating": rating,
                    "user_ratings_total": place.get("userRatingCount", 0),
                    "price_level": place.get("priceLevel", "PRICE_LEVEL_UNSPECIFIED"),
                    "opening_hours": opening_hours,
                    "photos": photos,
                    "description": place.get("editorialSummary", {}).get("text", ""),
                }

                all_pois.append(poi)

            # Small delay to respect rate limits
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to search for {category}: {str(e)}")
            continue

    # Step 3: Sort by rating and review count, then limit results
    all_pois.sort(key=lambda x: (
        x["rating"], x["user_ratings_total"]), reverse=True)
    all_pois = all_pois[:max_results]

    print(f"Found {len(all_pois)} points of interest")

    return {
        "city": city_location["name"],
        "location": {"lat": city_location["lat"], "lng": city_location["lng"]},
        "points_of_interest": all_pois,
    }


# ============================================================================
# Tool 3: Hotel Offers Finder
# ============================================================================


@tool
def find_hotels(
    city: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    max_price: float = 10000.0,
) -> str:
    """
    Search for available hotel offers for specific hotels and dates.

    Args:
        city: Name of the city to find hotels in
        check_in: Check-in date in YYYY-MM-DD format
        check_out: Check-out date in YYYY-MM-DD format
        adults: Number of adults (default: 2)
        max_price: Maximum total price in specified currency (optional)

    Returns:
        A list of hotel offers in JSON format
    """

    check_in_date = _parse_datestr(check_in)
    check_out_date = _parse_datestr(check_out)

    offers = mock_find_hotels(
        city, check_in_date, check_out_date, adults, max_price)
    offers = list(map(HotelOffer.as_dict, offers))
    return json.dumps(offers)


# ============================================================================
# Tool 4: Flight Finder
# ============================================================================


@tool
def find_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    travel_class: str = "ECONOMY",
    non_stop: bool = False,
    max_price: Optional[float] = None,
) -> str:
    """
    Search for flights between cities for specific dates.

    Args:
        origin: Origin airport/city code (IATA)
        destination: Destination airport/city code (IATA)
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date for round trip (optional)
        adults: Number of adult passengers (default: 1)
        travel_class: Cabin class - ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST (default: "ECONOMY")
        non_stop: Direct flights only (default: False)
        max_price: Maximum price in specified currency (optional)

    Returns:
        A list of flight offers in JSON format
    """

    departure_date_date = _parse_datestr(departure_date)
    return_date_date = None
    if return_date is not None:
        return_date_date = _parse_datestr(return_date)

    offers = mock_find_flights(origin, destination, departure_date_date,
                               return_date_date, adults, travel_class, non_stop, max_price)
    offers = list(map(FlightOffer.as_dict, offers))
    return json.dumps(offers)


# ============================================================================
# Tool 5: RAG tools
# ============================================================================


@tool
def city_information(query: str) -> str:
    """
    Retrieve relevant information for cities based on the given query.

    Args:
        query: Generic query to retrieve answers for.

    Returns:
        String containing relevant content.
    """
    embedding = EMBEDDER.encode(query)
    chunks: list[Chunk] = Chunk.objects.order_by(CosineDistance(  # type:ignore
        "embedding", embedding))[:5]

    chunk_strs = []
    for chunk in chunks:
        chunk_strs.append(str(chunk.content))
    return "- " + "\n\n- ".join(chunk_strs)


@tool
def calculator(expr: str) -> str:
    """
    Perform a math operation.

    Args:
        expr: Python math expression.

    Returns:
        String representation of the answer.
    """
    return str(eval(expr))


@tool
def currency_converter(frm: str, to: str, amount: float) -> float:
    """
    Convert from one currency to another.

    Args:
        frm: Currency to convert from (e.g. 'USD', 'JPY')
        to: Currency to convert to (e.g. 'USD', 'JPY')
        amount: Amount of currency to convert

    Returns:
        Amount of converted currency.
    """
    frm = frm.lower()
    to = to.lower()
    if frm == "usd" and to == "jpy":
        return amount * 155
    elif frm == "jpy" and to == "usd":
        return round(amount / 155, 2)
    else:
        return amount
