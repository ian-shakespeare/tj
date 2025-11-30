# Multi-Agent Vacation Planning System - Tool Implementation Plan

## Overview
This document outlines the implementation plan for four essential tools that will power our multi-agent travel planning system. These tools will provide real-time data from external APIs to help plan comprehensive vacation itineraries.

## Architecture Context
- **Framework**: LangChain with Ollama (qwen3:8b model)
- **Database**: PostgreSQL with pgvector for semantic search
- **Existing Agents**:
  - Pathfinder: Builds city-to-city itineraries
  - Explorer: Finds points of interest
  - Booker: Searches hotels and flights
  - Budgeteer: Estimates costs
  - Receptionist: Orchestrates all agents

## Tool Specifications

### 1. City Finder Tool
**Purpose**: Find all cities between two points (origin and destination cities)

**API**: Google Routes API + Places API
- **Routes API Endpoint**: `https://routes.googleapis.com/directions/v2:computeRoutes`
- **Places API Endpoint**: `https://places.googleapis.com/v1/places:searchNearby`

**Implementation Details**:
- **Input Parameters**:
  - `origin_city: str` - Starting city name
  - `destination_city: str` - Ending city name
  - `max_detour_minutes: int = 120` - Maximum acceptable detour (optional)

- **Process Flow**:
  1. Geocode both origin and destination cities using Places API Text Search
  2. Use Routes API to compute the optimal route between cities
  3. Extract waypoints or intermediate cities along the route
  4. For the route polyline, sample points every N kilometers (e.g., every 50km)
  5. Use Places API Nearby Search to find cities/localities near those points
  6. Filter results to include only administrative areas (type: "locality" or "administrative_area_level_3")
  7. Return list of cities with coordinates, distance from origin, and estimated travel time

- **Output Format**:
  ```python
  {
    "origin": {"name": str, "lat": float, "lng": float},
    "destination": {"name": str, "lat": float, "lng": float},
    "intermediate_cities": [
      {
        "name": str,
        "lat": float,
        "lng": float,
        "distance_from_origin_km": float,
        "estimated_travel_time_minutes": int
      }
    ],
    "total_distance_km": float,
    "total_duration_minutes": int
  }
  ```

- **API Authentication**: Requires Google Cloud API key with Routes API and Places API enabled

- **Rate Limits**: 
  - Routes API: Check Google Cloud quotas (typically generous for development)
  - Places API: Up to 1000 requests/day (free tier)

- **Error Handling**:
  - Handle invalid city names with graceful fallback
  - Validate API responses
  - Implement retry logic for transient failures

### 2. Points of Interest Finder Tool
**Purpose**: Find notable locations and attractions in a specified city

**API**: Google Places API (New)
- **Endpoint**: `https://places.googleapis.com/v1/places:searchText`
- **Details Endpoint**: `https://places.googleapis.com/v1/places/{place_id}`

**Implementation Details**:
- **Input Parameters**:
  - `city: str` - City name
  - `categories: list[str] = None` - Optional filter (e.g., ["tourist_attraction", "museum", "restaurant"])
  - `min_rating: float = 4.0` - Minimum rating threshold
  - `max_results: int = 20` - Maximum number of results
  
- **Process Flow**:
  1. Geocode the city using Places API Text Search
  2. Define search radius (e.g., 5km for small cities, 15km for large cities)
  3. Query Places API for each category:
     - tourist_attraction
     - museum
     - park
     - restaurant (highly rated)
     - shopping_mall
     - night_club (if applicable)
  4. For each result, fetch detailed information including:
     - Name, address, location
     - Rating and number of reviews
     - Price level
     - Opening hours
     - Photos (up to 3 reference URLs)
  5. Sort by rating and review count
  6. Return top N results per category

- **Output Format**:
  ```python
  {
    "city": str,
    "location": {"lat": float, "lng": float},
    "points_of_interest": [
      {
        "name": str,
        "place_id": str,
        "category": str,
        "address": str,
        "location": {"lat": float, "lng": float},
        "rating": float,
        "user_ratings_total": int,
        "price_level": int,  # 0-4 scale
        "opening_hours": {
          "open_now": bool,
          "weekday_text": list[str]
        },
        "photos": list[str],  # Photo reference URLs
        "description": str  # Editorial summary if available
      }
    ]
  }
  ```

- **API Authentication**: Same Google Cloud API key as City Finder

- **Rate Limits**: 
  - Text Search: Consider cost per request
  - Details requests: May require additional quota

- **Error Handling**:
  - Handle missing data fields gracefully
  - Validate city exists
  - Filter out permanently closed places

### 3. Hotel Finder Tool
**Purpose**: Search for available hotels in a city for specific dates

**API**: Amadeus Hotel Search API
- **Endpoints**:
  - Hotel List: `https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city`
  - Hotel Search: `https://test.api.amadeus.com/v3/shopping/hotel-offers`

**Implementation Details**:
- **Input Parameters**:
  - `city_code: str` - IATA city code (e.g., "NYC", "LON")
  - `check_in: str` - Check-in date (YYYY-MM-DD format)
  - `check_out: str` - Check-out date (YYYY-MM-DD format)
  - `adults: int = 2` - Number of adults
  - `max_price: float = None` - Maximum price per night (optional)
  - `currency: str = "USD"` - Currency code
  - `max_results: int = 10` - Maximum number of results
  
- **Process Flow**:
  1. If city name is provided instead of code, convert to IATA code using Amadeus location API
  2. Query Hotel List endpoint to get hotels in the city
  3. Use Hotel Search endpoint with:
     - Hotel IDs from step 2
     - Check-in/check-out dates
     - Number of guests
  4. Parse availability and pricing information
  5. Sort by price or rating
  6. Return top N results

- **Output Format**:
  ```python
  {
    "city": str,
    "city_code": str,
    "check_in": str,
    "check_out": str,
    "hotels": [
      {
        "hotel_id": str,
        "name": str,
        "rating": float,
        "location": {
          "latitude": float,
          "longitude": float,
          "address": str
        },
        "offers": [
          {
            "id": str,
            "room_type": str,
            "guests": int,
            "price": {
              "total": float,
              "currency": str,
              "per_night": float
            },
            "cancellation_policy": str,
            "amenities": list[str],
            "bed_type": str
          }
        ]
      }
    ]
  }
  ```

- **API Authentication**: 
  - Requires Amadeus API key and secret
  - OAuth 2.0 token-based authentication
  - Token expires after ~30 minutes, implement refresh logic

- **Rate Limits**: 
  - Test environment: Limited requests per second
  - Production: Check Amadeus pricing tier

- **Error Handling**:
  - Handle no availability scenarios
  - Validate date formats and ranges
  - Handle invalid city codes
  - Cache authentication tokens

### 4. Flight Finder Tool
**Purpose**: Search for flights between cities for specific dates

**API**: Amadeus Flight Offers Search API
- **Endpoint**: `https://test.api.amadeus.com/v2/shopping/flight-offers`

**Implementation Details**:
- **Input Parameters**:
  - `origin: str` - Origin airport/city code (IATA)
  - `destination: str` - Destination airport/city code (IATA)
  - `departure_date: str` - Departure date (YYYY-MM-DD)
  - `return_date: str = None` - Return date for round trip (optional)
  - `adults: int = 1` - Number of adult passengers
  - `travel_class: str = "ECONOMY"` - Cabin class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
  - `non_stop: bool = False` - Direct flights only
  - `max_results: int = 10` - Maximum number of results
  - `max_price: float = None` - Maximum price (optional)
  - `currency: str = "USD"` - Currency code
  
- **Process Flow**:
  1. Convert city names to IATA airport codes if needed
  2. Validate date formats and ensure departure is before return
  3. Query Flight Offers Search endpoint with parameters
  4. Parse response for:
     - Flight segments (outbound/return)
     - Airline information
     - Duration and layovers
     - Pricing
  5. Sort by price, duration, or relevance
  6. Return top N results

- **Output Format**:
  ```python
  {
    "origin": str,
    "destination": str,
    "departure_date": str,
    "return_date": str,
    "flights": [
      {
        "id": str,
        "type": str,  # "one-way" or "round-trip"
        "price": {
          "total": float,
          "currency": str,
          "per_person": float
        },
        "outbound": {
          "segments": [
            {
              "departure": {
                "airport": str,
                "terminal": str,
                "time": str  # ISO 8601
              },
              "arrival": {
                "airport": str,
                "terminal": str,
                "time": str
              },
              "carrier": str,
              "flight_number": str,
              "aircraft": str,
              "duration": str,  # ISO 8601 duration
              "cabin_class": str
            }
          ],
          "total_duration": str
        },
        "return": {  # Same structure as outbound, null if one-way
          "segments": [...],
          "total_duration": str
        },
        "number_of_stops": int,
        "booking_class": str,
        "seats_available": int
      }
    ]
  }
  ```

- **API Authentication**: Same as Hotel Finder (Amadeus OAuth 2.0)

- **Rate Limits**: 
  - Test environment: Limited requests
  - Monitor quota usage

- **Error Handling**:
  - Handle no flights found
  - Validate airport codes
  - Handle date validation errors
  - Parse and display API error messages clearly

## Implementation Structure

### Recommended File Organization
```
lib/
├── __init__.py
├── pgvector.py (existing)
├── tools/
│   ├── __init__.py
│   ├── city_finder.py
│   ├── poi_finder.py
│   ├── hotel_finder.py
│   ├── flight_finder.py
│   └── api_clients/
│       ├── __init__.py
│       ├── google_api.py
│       └── amadeus_api.py
```

### Shared Components

#### Google API Client (`lib/tools/api_clients/google_api.py`)
- Centralized authentication and request handling
- Shared methods:
  - `geocode_city(city_name: str) -> dict`
  - `search_places(query: str, location: dict, radius: int) -> list`
  - `get_place_details(place_id: str) -> dict`
  - `compute_route(origin: dict, destination: dict) -> dict`

#### Amadeus API Client (`lib/tools/api_clients/amadeus_api.py`)
- OAuth token management with auto-refresh
- Shared methods:
  - `get_access_token() -> str`
  - `refresh_token() -> str`
  - `search_hotels(params: dict) -> dict`
  - `search_flights(params: dict) -> dict`
  - `get_airport_code(city_name: str) -> str`

### Environment Variables
Add to `.env` file:
```bash
# Google Cloud Platform
GOOGLE_API_KEY=your_google_api_key

# Amadeus API (Test Environment)
AMADEUS_API_KEY=your_amadeus_api_key
AMADEUS_API_SECRET=your_amadeus_api_secret
AMADEUS_API_BASE_URL=https://test.api.amadeus.com

# PostgreSQL (existing)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=japan-travel-agent
```

### Dependencies to Add
Update `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies ...
    "requests>=2.32.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.10.0",  # For data validation
    "httpx>=0.28.0",  # For async API calls (future enhancement)
]
```

## Integration with Existing Agents

### Pathfinder Agent
- Add `city_finder` tool to discover intermediate cities
- Usage: Find cities between start and end points to build itinerary

### Explorer Agent  
- Add `poi_finder` tool to discover attractions
- Usage: For each city in itinerary, find top-rated points of interest

### Booker Agent
- Add `hotel_finder` tool for accommodation search
- Add `flight_finder` tool for transportation between cities
- Usage: Book hotels for each city stay and flights for inter-city travel

## Testing Strategy

### Unit Tests
1. Test each API client independently with mocked responses
2. Test input validation for all tools
3. Test error handling scenarios

### Integration Tests
1. Test actual API calls with test credentials
2. Verify response parsing and data transformation
3. Test rate limiting and retry logic

### End-to-End Tests
1. Test full agent workflow with all tools
2. Sample query: "Plan a 7-day trip from Tokyo to Osaka between June 1-7, 2025"
3. Verify all agents can access and use tools correctly

## Development Phases

### Phase 1: API Client Setup (2-3 days)
- [ ] Set up Google Cloud project and enable APIs
- [ ] Set up Amadeus test account
- [ ] Implement base API client classes
- [ ] Test authentication and basic requests

### Phase 2: Core Tool Implementation (3-4 days)
- [ ] Implement City Finder tool
- [ ] Implement POI Finder tool
- [ ] Implement Hotel Finder tool
- [ ] Implement Flight Finder tool
- [ ] Write unit tests for each tool

### Phase 3: LangChain Integration (2 days)
- [ ] Wrap tools as LangChain @tool decorators
- [ ] Add tools to appropriate agents
- [ ] Update agent system prompts if needed
- [ ] Test tool calling from agents

### Phase 4: Testing & Refinement (2-3 days)
- [ ] Integration testing with real APIs
- [ ] End-to-end agent workflow testing
- [ ] Handle edge cases and errors
- [ ] Optimize API usage to reduce costs
- [ ] Add caching where appropriate

### Phase 5: Documentation (1 day)
- [ ] Document API setup instructions
- [ ] Create usage examples
- [ ] Document rate limits and costs
- [ ] Create troubleshooting guide

## Cost Considerations

### Google APIs
- **Places API**: $17 per 1000 Text Search requests
- **Routes API**: $5 per 1000 route requests
- **Free tier**: $200 monthly credit

### Amadeus APIs
- **Test environment**: Free but limited
- **Production**: Pay-per-use pricing
- Estimated cost: ~$0.50-2.00 per complete trip query

### Recommendations
1. Implement caching for repeated queries (especially city geocoding)
2. Use test environments during development
3. Set up budget alerts in Google Cloud Console
4. Consider implementing request batching where possible

## Future Enhancements
1. Add caching layer (Redis) for frequently searched cities/hotels
2. Implement async API calls for better performance
3. Add support for alternative APIs (Skyscanner, Booking.com)
4. Create visualization of routes on maps
5. Add real-time price tracking and alerts
6. Implement user preferences and personalization
7. Add support for multi-city trips (not just point-to-point)
8. Integrate weather data for destination planning

## Security Considerations
1. Never commit API keys to version control
2. Use environment variables for all credentials
3. Implement API key rotation policy
4. Add request logging for debugging (but sanitize sensitive data)
5. Validate and sanitize all user inputs
6. Implement rate limiting on user-facing endpoints
7. Use HTTPS for all API communications

## Notes
- All date formats should be ISO 8601 (YYYY-MM-DD)
- All prices should include currency code
- All coordinates should be in decimal degrees
- Consider time zones when handling flight times
- Handle multi-airport cities (e.g., NYC has JFK, LGA, EWR)
