"""
Travel Planning Tools for Multi-Agent System

This module provides four essential tools for vacation planning:
1. City Finder - Find cities between origin and destination
2. Points of Interest Finder - Discover attractions in a city
3. Hotel Finder - Search for available hotels
4. Flight Finder - Search for flights between cities

All tools integrate with external APIs (Google Maps Platform and Amadeus).
"""

import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain_core.tools import tool
from pgvector.django import CosineDistance
import requests
from amadeus import Client, ResponseError
from dotenv import load_dotenv

from .documents import EMBEDDER
from .models import Chunk

# Load environment variables
load_dotenv()

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")

# Initialize Amadeus client
amadeus = Client(client_id=AMADEUS_API_KEY, client_secret=AMADEUS_API_SECRET)


class GoogleAPIError(Exception):
    """Raised when Google API requests fail"""

    pass


class AmadeusAPIError(Exception):
    """Raised when Amadeus API requests fail"""

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


def _compute_route(
    origin: Dict[str, float], destination: Dict[str, float]
) -> Dict[str, Any]:
    """
    Compute route between two points using Google Routes API.

    Args:
        origin: Dictionary with 'lat' and 'lng' keys
        destination: Dictionary with 'lat' and 'lng' keys

    Returns:
        Dictionary with route information including polyline and duration

    Raises:
        GoogleAPIError: If route computation fails
    """
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline",
    }

    data = {
        "origin": {
            "location": {
                "latLng": {"latitude": origin["lat"], "longitude": origin["lng"]}
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination["lat"],
                    "longitude": destination["lng"],
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()

        if not result.get("routes"):
            raise GoogleAPIError("No route found between the specified points")

        route = result["routes"][0]

        # Parse duration (format: "12345s")
        duration_str = route["duration"]
        duration_seconds = int(duration_str.rstrip("s"))
        duration_minutes = duration_seconds // 60

        return {
            "distance_meters": route["distanceMeters"],
            "duration_minutes": duration_minutes,
            "polyline": route["polyline"]["encodedPolyline"],
        }
    except requests.exceptions.RequestException as e:
        raise GoogleAPIError(f"Failed to compute route: {str(e)}")


def _decode_polyline(encoded: str) -> List[Dict[str, float]]:
    """
    Decode a Google Maps encoded polyline string into coordinates.

    Args:
        encoded: Encoded polyline string

    Returns:
        List of dictionaries with 'lat' and 'lng' keys
    """
    points = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append({"lat": lat / 1e5, "lng": lng / 1e5})

    return points


def _search_nearby_places(
    location: Dict[str, float], radius: int = 50000
) -> List[Dict[str, Any]]:
    """
    Search for localities (cities) near a given location.

    Args:
        location: Dictionary with 'lat' and 'lng' keys
        radius: Search radius in meters (default: 50km)

    Returns:
        List of places found
    """
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.location,places.types",
    }

    data = {
        "includedTypes": ["locality", "administrative_area_level_3"],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": location["lat"], "longitude": location["lng"]},
                "radius": radius,
            }
        },
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        places = []
        for place in result.get("places", []):
            places.append(
                {
                    "name": place["displayName"]["text"],
                    "lat": place["location"]["latitude"],
                    "lng": place["location"]["longitude"],
                    "types": place.get("types", []),
                }
            )

        return places
    except requests.exceptions.RequestException:
        return []


def _calculate_distance(point1: Dict[str, float], point2: Dict[str, float]) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Args:
        point1: Dictionary with 'lat' and 'lng' keys
        point2: Dictionary with 'lat' and 'lng' keys

    Returns:
        Distance in kilometers
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # Earth's radius in kilometers

    lat1 = radians(point1["lat"])
    lon1 = radians(point1["lng"])
    lat2 = radians(point2["lat"])
    lon2 = radians(point2["lng"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# ============================================================================
# Helper Functions for Amadeus API
# ============================================================================


def _pad_datestr(s: str) -> str:
    format = "%Y-%m-%d"
    now = datetime.now()
    d = datetime.strptime(s, format)
    if d < now:
        if d.month < now.month or (d.month == now.month and d.day < now.day):
            d = d.replace(year=now.year + 1)
        else:
            d = d.replace(year=now.year)
    return d.strftime(format)


# ============================================================================
# Tool 1: City Finder
# ============================================================================


@tool
def find_cities_between(
    origin_city: str, destination_city: str, max_detour_minutes: int = 120
) -> Dict[str, Any]:
    """
    Find all cities between two points (origin and destination cities).

    This tool uses Google Routes API to compute the optimal route, then
    searches for cities along that route.

    Args:
        origin_city: Starting city name
        destination_city: Ending city name
        max_detour_minutes: Maximum acceptable detour in minutes (default: 120)

    Returns:
        Dictionary containing:
        - origin: Origin city info (name, lat, lng)
        - destination: Destination city info (name, lat, lng)
        - intermediate_cities: List of cities along the route
        - total_distance_km: Total distance in kilometers
        - total_duration_minutes: Total duration in minutes

    Raises:
        GoogleAPIError: If API requests fail
    """

    # Step 1: Geocode both cities
    origin = _geocode_city(origin_city)
    destination = _geocode_city(destination_city)

    # Step 2: Compute route
    route = _compute_route(origin, destination)
    total_distance_km = route["distance_meters"] / 1000
    total_duration_minutes = route["duration_minutes"]

    # Step 3: Decode polyline and sample points
    polyline_points = _decode_polyline(route["polyline"])

    # Sample points every ~50km along the route
    sample_interval = max(
        1, len(polyline_points) // max(1, int(total_distance_km / 50))
    )
    sampled_points = polyline_points[::sample_interval]

    # Step 4: Find cities near sampled points
    cities_found = {}

    for point in sampled_points:
        nearby_places = _search_nearby_places(
            point, radius=30000)  # 30km radius

        for place in nearby_places:
            city_name = place["name"]

            # Skip if we've already found this city
            if city_name in cities_found:
                continue

            # Skip origin and destination cities
            if city_name == origin["name"] or city_name == destination["name"]:
                continue

            # Calculate distance from origin
            distance_from_origin = _calculate_distance(origin, place)

            # Estimate travel time (proportional to distance)
            estimated_time = int(
                (distance_from_origin / total_distance_km) * total_duration_minutes
            )

            cities_found[city_name] = {
                "name": city_name,
                "lat": place["lat"],
                "lng": place["lng"],
                "distance_from_origin_km": round(distance_from_origin, 2),
                "estimated_travel_time_minutes": estimated_time,
            }

    # Step 5: Sort cities by distance from origin
    intermediate_cities = sorted(
        cities_found.values(), key=lambda x: x["distance_from_origin_km"]
    )

    return {
        "origin": origin,
        "destination": destination,
        "intermediate_cities": intermediate_cities,
        "total_distance_km": round(total_distance_km, 2),
        "total_duration_minutes": total_duration_minutes,
    }


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
# Tool 3: Hotel List
# ============================================================================


def list_hotels(city_code: str, max_results: int = 50) -> Dict[str, Any]:
    """
    List available hotels in a city using Amadeus Hotels by City endpoint.

    This tool should be used first to get hotel IDs, which can then be used
    with find_hotels to get specific offers with dates and pricing.

    Args:
        city_code: IATA city code (e.g., "TYO" for Tokyo, "NYC" for New York)
        max_results: Maximum number of hotels to return (default: 50)

    Returns:
        Dictionary containing:
        - city_code: IATA city code
        - hotels: List of hotels with basic information

    Raises:
        AmadeusAPIError: If API requests fail
    """
    print(f"Listing hotels in {city_code}...")

    try:
        # Get list of hotels in the city
        response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code
        )

        hotels_data = response.data

        if not hotels_data:
            print("No hotels found in this city")
            return {"city_code": city_code, "hotels": []}

        hotels = []

        for hotel_data in hotels_data[:max_results]:
            hotel = {
                "hotel_id": hotel_data["hotelId"],
                "name": hotel_data["name"],
                "iata_code": hotel_data.get("iataCode", city_code),
                "location": {
                    "latitude": float(hotel_data.get("geoCode", {}).get("latitude", 0)),
                    "longitude": float(
                        hotel_data.get("geoCode", {}).get("longitude", 0)
                    ),
                },
                "address": {
                    "country_code": hotel_data.get("address", {}).get(
                        "countryCode", "N/A"
                    )
                },
            }

            hotels.append(hotel)

        print(f"Found {len(hotels)} hotels")

        return {"city_code": city_code, "hotels": hotels}

    except ResponseError as e:
        raise AmadeusAPIError(f"Amadeus API error: {e.response.body}")
    except Exception as e:
        raise AmadeusAPIError(f"Failed to list hotels: {str(e)}")


# ============================================================================
# Tool 4: Hotel Offers Finder
# ============================================================================


def find_hotels(
    hotel_ids: List[str],
    check_in: str,
    check_out: str,
    adults: int = 2,
    max_price: Optional[float] = None,
    currency: str = "USD",
    max_results: int = 10,
) -> Dict[str, Any]:
    """
    Search for available hotel offers for specific hotels and dates.

    Note: Use list_hotels() first to get hotel IDs for a city.

    Args:
        hotel_ids: List of Amadeus hotel IDs (get from list_hotels)
        check_in: Check-in date in YYYY-MM-DD format
        check_out: Check-out date in YYYY-MM-DD format
        adults: Number of adults (default: 2)
        max_price: Maximum total price in specified currency (optional)
        currency: Currency code (default: "USD")
        max_results: Maximum number of results (default: 10)

    Returns:
        Dictionary containing:
        - check_in: Check-in date
        - check_out: Check-out date
        - hotels: List of hotels with offers

    Raises:
        AmadeusAPIError: If API requests fail
    """

    check_in = _pad_datestr(check_in)
    check_out = _pad_datestr(check_out)

    print(f"Searching for hotel offers from {check_in} to {check_out}...")

    if not hotel_ids:
        raise AmadeusAPIError(
            "hotel_ids cannot be empty. Use list_hotels() first to get hotel IDs."
        )

    try:
        # Search for hotel offers using hotel IDs
        # Convert list to comma-separated string
        hotel_ids_str = ",".join(hotel_ids[:max_results])

        response = amadeus.shopping.hotel_offers_search.get(
            hotelIds=hotel_ids_str,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=adults,
            currency=currency,
            bestRateOnly=True,
        )

        hotels_data = response.data

        if not hotels_data:
            print("No hotel offers found for the specified criteria")
            return {"check_in": check_in, "check_out": check_out, "hotels": []}

        hotels = []

        for offer_data in hotels_data:
            hotel_data = offer_data["hotel"]

            # Filter by max price if specified
            offers = []
            for offer in offer_data.get("offers", []):
                price_total = float(offer["price"]["total"])

                if max_price and price_total > max_price:
                    continue

                # Calculate per-night price
                checkin_date = datetime.strptime(check_in, "%Y-%m-%d")
                checkout_date = datetime.strptime(check_out, "%Y-%m-%d")
                num_nights = (checkout_date - checkin_date).days
                per_night = price_total / num_nights if num_nights > 0 else price_total

                offer_info = {
                    "id": offer["id"],
                    "room_type": offer.get("room", {})
                    .get("typeEstimated", {})
                    .get("category", "N/A"),
                    "guests": adults,
                    "price": {
                        "total": price_total,
                        "currency": offer["price"]["currency"],
                        "per_night": round(per_night, 2),
                    },
                    "cancellation_policy": "Check with hotel",
                    "amenities": offer.get("room", {})
                    .get("description", {})
                    .get("text", "")
                    .split(","),
                    "bed_type": offer.get("room", {})
                    .get("typeEstimated", {})
                    .get("bedType", "N/A"),
                }

                offers.append(offer_info)

            if not offers:
                continue

            # Get hotel location
            location = {
                "latitude": float(hotel_data.get("latitude", 0)),
                "longitude": float(hotel_data.get("longitude", 0)),
                "address": hotel_data.get("address", {}).get("lines", ["N/A"])[0]
                if hotel_data.get("address", {}).get("lines")
                else "N/A",
            }

            hotel = {
                "hotel_id": hotel_data["hotelId"],
                "name": hotel_data["name"],
                "rating": hotel_data.get("rating", "N/A"),
                "location": location,
                "offers": offers,
            }

            hotels.append(hotel)

        print(f"Found {len(hotels)} hotels with available offers")

        return {"check_in": check_in, "check_out": check_out, "hotels": hotels}

    except ResponseError as e:
        raise AmadeusAPIError(f"Amadeus API error: {e.response.body}")
    except Exception as e:
        raise AmadeusAPIError(f"Failed to search hotels: {str(e)}")


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
    max_results: int = 10,
    max_price: Optional[float] = None,
    currency: str = "USD",
) -> Dict[str, Any]:
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
        max_results: Maximum number of results (default: 10)
        max_price: Maximum price in specified currency (optional)
        currency: Currency code (default: "USD")

    Returns:
        Dictionary containing:
        - origin: Origin airport code
        - destination: Destination airport code
        - departure_date: Departure date
        - return_date: Return date (if applicable)
        - flights: List of flight offers

    Raises:
        AmadeusAPIError: If API requests fail
    """

    departure_date = _pad_datestr(departure_date)
    if return_date:
        return_date = _pad_datestr(return_date)

    print(
        f"Searching for flights from {origin} to {destination} on {departure_date}..."
    )

    try:
        # Build search parameters
        search_params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "travelClass": travel_class,
            "currencyCode": currency,
            "max": max_results,
        }

        if return_date:
            search_params["returnDate"] = return_date

        if non_stop:
            search_params["nonStop"] = "true"

        if max_price:
            search_params["maxPrice"] = str(int(max_price))

        # Search for flight offers
        response = amadeus.shopping.flight_offers_search.get(**search_params)

        flights_data = response.data

        if not flights_data:
            print("No flights found for the specified criteria")
            return {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "flights": [],
            }

        flights = []

        for flight_data in flights_data:
            # Parse price
            price = flight_data["price"]
            total_price = float(price["total"])
            per_person = total_price / adults

            # Parse itineraries (outbound and return)
            itineraries = flight_data["itineraries"]

            def parse_itinerary(itinerary):
                segments = []
                for segment in itinerary["segments"]:
                    seg_info = {
                        "departure": {
                            "airport": segment["departure"]["iataCode"],
                            "terminal": segment["departure"].get("terminal", "N/A"),
                            "time": segment["departure"]["at"],
                        },
                        "arrival": {
                            "airport": segment["arrival"]["iataCode"],
                            "terminal": segment["arrival"].get("terminal", "N/A"),
                            "time": segment["arrival"]["at"],
                        },
                        "carrier": segment["carrierCode"],
                        "flight_number": segment["number"],
                        "aircraft": segment.get("aircraft", {}).get("code", "N/A"),
                        "duration": segment["duration"],
                        "cabin_class": segment.get("cabin", travel_class),
                    }
                    segments.append(seg_info)

                return {"segments": segments, "total_duration": itinerary["duration"]}

            outbound = parse_itinerary(itineraries[0])
            return_flight = None

            if len(itineraries) > 1:
                return_flight = parse_itinerary(itineraries[1])

            # Count stops
            num_stops = len(outbound["segments"]) - 1
            if return_flight:
                num_stops += len(return_flight["segments"]) - 1

            # Get seats available
            seats_available = flight_data.get("numberOfBookableSeats", 0)

            flight = {
                "id": flight_data["id"],
                "type": "round-trip" if return_flight else "one-way",
                "price": {
                    "total": total_price,
                    "currency": price["currency"],
                    "per_person": round(per_person, 2),
                },
                "outbound": outbound,
                "return": return_flight,
                "number_of_stops": num_stops,
                "booking_class": travel_class,
                "seats_available": seats_available,
            }

            flights.append(flight)

        print(f"Found {len(flights)} flight options")

        return {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "flights": flights,
        }

    except ResponseError as e:
        raise AmadeusAPIError(f"Amadeus API error: {e.response.body}")
    except Exception as e:
        raise AmadeusAPIError(f"Failed to search flights: {str(e)}")


# ============================================================================
# Tool 5: RAG tools
# ============================================================================


@tool(response_format="content_and_artifact")
def city_information(query: str) -> str:
    """
    Retrieve relevant information for cities based on the given query.

    Args:
        query: Generic query to retrieve answers for.

    Returns:
        String containing relevant content.
    """
    embedding = EMBEDDER.encode(query)
    chunks = Chunk.objects.order_by(CosineDistance(  # type:ignore
        "embedding", embedding))[:5]
    return "- " + "\n\n- ".join(map(Chunk.content.__str__, chunks))#type:ignore


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
