import random

from dataclasses import dataclass
from datetime import date
from typing import Optional


MOCK_AIR_LINES = [
    "Aether",
    "Nova Air",
    "SkyHarbor Airlines",
    "Aurora Jetlines",
    "Horizon Connect",
    "Velvet Wings",
    "Pinnacle Air",
    "Echo Airways",
    "Saffron Airlines",
    "Celestial Air",
]


MOCK_HOTEL_NAMES = [
    "Grand Plaza Hotel",
    "Ocean View Resort",
    "Grand Prince Hotel",
    "APA Station Front",
    "Days Inn",
    "Granva Luxe",
    "Sakura Breeze Hotel",
    "Shinjo Inn & Spa",
    "Mizuki Seaside Resort",
    "Kizuna Grand Lodge",
    "Yuki’s House Guesthouse",
    "Harmony Garden Residence",
    "Zenith Luxury Inn",
    "Kōen Harbor Hotel",
    "Tsukimi Moonview Ryokan",
    "Aoi Horizon Suites",
]


@dataclass
class FlightOffer:
    airline: str
    price_per_person: float
    total: float
    travel_class: str
    non_stop: bool


def mock_find_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None,
    adults: int = 1,
    travel_class: str = "ECONOMY",
    non_stop: bool = False,
    max_price: Optional[float] = None,
) -> list[FlightOffer]:
    """
    Mock implementation of find_flights function.

    Args:
        Same as the original function

    Returns:
        Mocked flight data
    """

    airlines = random.sample(
        MOCK_HOTEL_NAMES, random.randint(1, 5))

    flights = []
    for airline in airlines:
        price_per_person = round(random.randint(20000, 80000) / 100, 2)
        if return_date is not None:
            price_per_person *= 2
        total = price_per_person * adults

        if max_price is not None and total > max_price:
            continue

        flights.append(FlightOffer(airline, price_per_person,
                       total, travel_class, non_stop))

    return flights


@dataclass
class HotelOffer:
    name: str
    price_per_night: float
    total: float
    city_code: str


def mock_list_hotels(city_code: str, check_in: date, check_out: date, adults: int, max_price: float) -> list[HotelOffer]:
    """
    Mock implementation of find_hotels function.

    Args:
        hotel_ids: List of hotel IDs
        check_in: Check-in date
        check_out: Check-out date
        adults: Number of adults
        max_price: Maximum price

    Returns:
        Mocked hotel offers data
    """

    hotel_names = random.sample(
        MOCK_HOTEL_NAMES, random.randint(1, len(MOCK_HOTEL_NAMES) - 1))
    num_nights = abs((check_out - check_in).days)

    hotels = []
    for name in hotel_names:
        price_per_night = round(random.randint(3300, 40000) / 100, 2)
        if adults > 1:
            price_per_night += round(price_per_night * (adults - 1) * 0.2, 2)
        total = round(price_per_night * num_nights * 1.2, 2)
        if total > max_price:
            continue
        hotels.append(HotelOffer(name, price_per_night, total, city_code))

    return hotels
