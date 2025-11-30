### TJ - Multi-Agent Japan Vacation Planning System

#### Overview

This document outlines the implementation plan for the tools and architecture powering our multi-agent travel planning system. These tools, drawing on external APIs, are intended to help plan comprehensive vacation itineraries.

#### Architecture Context

The system architecture utilizes a Multi-Agent System (MAS) approach, employing specialized agents for different stages of trip planning.

*   **Framework** : LangChain with Ollama (`gpt-oss:20b` model).
*   **Web Application Stack**: The web application stack uses **Django** with its built-in **authentication/authorization** features.
*   **Database** : PostgreSQL with pgvector for semantic search.
*   **Agents**:
    *   **Pathfinder**: Builds city-to-city itineraries.
    *   **Explorer**: Finds points of interest.
    *   **Booker**: Searches hotels and flights.
    *   **Budgeteer**: Estimates costs.
    *   **Receptionist**: Orchestrates all agents.

***

### Project Checkpoint Summary

This section details the critical architectural decisions, operational insights, and issues encountered during the recent development sprint.

#### 1. Technologies and Model Selection

The core reasoning engine uses **GPT OSS models** instead of the originally planned Qwen3 models. This decision was driven by the observation that the **Qwen3:8b model exhibited a tendency to perform reasoning even when that capability was intended to be disabled**. For the web interface, the system uses **Django, leveraging its built-in authentication and authorization mechanisms**.

#### 2. Interesting Insights (Multi-Agent Delegation)

The project leverages a multi-agent architecture where task distribution and collaboration are key. Performance comparisons revealed a direct relationship between model size and delegation strategy:

*   I found that **larger models generally performed worse than smaller/medium sized ones**.
*   Larger models tended to prioritize solving the entire problem internally without consulting sub agents.
*   Conversely, **smaller models more eagerly delegated work to specialists** (the defined sub-agents), aligning with the MAS principle of distributing tasks among agents to solve complex, multi-step challenges.

#### 3. Issues Encountered (API Integration)

The primary development issues centered on integrating the real-time travel APIs, specifically the **Hotel Finder Tool** and the **Flight Finder Tool**.

*   I ran into many issues with the hotels and flight API because **the format is very particular**.
*   The LLM agents were **mostly unsuccessful in calling the flight/hotel tools** due to the specific format requirements. Agents rely on defined tool schemas and procedural memory to execute actions.
*   After stabilizing the tool calls, I **hit the API rate limit** (which is a known limitation of the Amadeus test environment specified in the original plan's Phase 4: Testing & Refinement).
*   To proceed and enable a demo, I decided to **mock the hotel and flight functionality**. While this is not ideal for a production system, it allows for a demonstration and leaves the option open for future users who wish to pay for an API extension.

***

### Tool Specifications

This section details the initial design specifications for the four primary tools, noting that the Hotel Finder and Flight Finder are currently operating in a mocked state.

#### 1. City Finder Tool

*   **Purpose** : Find all cities between two points (origin and destination cities).
*   **API** : Google Routes API + Places API.
*   **Process Flow** : Geocode cities, compute optimal route, extract waypoints, sample points along the route, use Places API Nearby Search, and filter results.
*   **Rate Limits** : Places API allows up to 1000 requests/day (free tier).

#### 2. Points of Interest Finder Tool

*   **Purpose** : Find notable locations and attractions in a specified city.
*   **API** : Google Places API (New).
*   **Process Flow** : Geocode the city, define a search radius, query Places API for categories (e.g., tourist_attraction, museum), fetch details, and return top results.
*   **Input Parameters** : city, categories (optional filter), min_rating (default 4.0), max_results (default 20).

#### 3. Hotel Finder Tool (Currently Mocked)

*   **Purpose** : Search for available hotels in a city for specific dates.
*   **API (Planned)** : Amadeus Hotel Search API.
*   **Endpoints (Planned)** : Hotel List (`/v1/reference-data/locations/hotels/by-city`) and Hotel Search (`/v3/shopping/hotel-offers`).
*   **Implementation Note**: The implementation of this tool caused issues due to the API's **particular format** and subsequent rate limiting; functionality is currently **mocked**.

#### 4. Flight Finder Tool (Currently Mocked)

*   **Purpose** : Search for flights between cities for specific dates.
*   **API (Planned)** : Amadeus Flight Offers Search API.
*   **Endpoint (Planned)** : `/v2/shopping/flight-offers`.
*   **Implementation Note**: The implementation of this tool caused issues due to the API's **particular format** and subsequent rate limiting; functionality is currently **mocked**.

### Implementation Structure

#### Shared Components
*   **Google API Client**: Centralized authentication and request handling; includes methods for `geocode_city`, `search_places`, `get_place_details`, and `compute_route`.
*   **Amadeus API Client**: Designed for OAuth token management with auto-refresh; includes methods for `get_access_token`, `search_hotels`, `search_flights`, and `get_airport_code`.

#### Integration with Existing Agents
*   **Pathfinder Agent**: Uses `city_finder` tool to discover intermediate cities.
*   **Explorer Agent**: Uses `poi_finder` tool to discover attractions.
*   **Booker Agent**: Was planned to use `hotel_finder` and `flight_finder` for accommodation and transportation between cities.

### Testing Strategy

Testing includes three levels: Unit Tests, Integration Tests, and End-to-End Tests.

*   **Unit Tests**: Test API clients with mocked responses, input validation, and error handling scenarios.
*   **Integration Tests**: Planned to test actual API calls with test credentials and verify response parsing; also included checking rate limiting and retry logic. (Note: Current integration testing for Amadeus APIs is limited due to the mocking of Hotel and Flight Finders).
*   **End-to-End Tests**: Test full agent workflow, verifying agents access and use tools correctly, using sample queries like "Plan a 7-day trip from Tokyo to Osaka between June 1-7, 2025".

### Development Phases (Original Plan)

*   **Phase 1: API Client Setup (2-3 days)**: Set up accounts, implement base client classes, and test authentication.
*   **Phase 2: Core Tool Implementation (3-4 days)**: Implement the four core tools (City, POI, Hotel, Flight Finder) and write unit tests.
*   **Phase 3: LangChain Integration (2 days)**: Wrap tools, add them to agents, and update system prompts.
*   **Phase 4: Testing & Refinement (2-3 days)**: Integration testing with real APIs, E2E testing, error handling, and optimization. (Note: This phase encountered the API rate limiting issue, leading to the mocking of travel functionality).
*   **Phase 5: Documentation (1 day)**: Document API setup, usage examples, rate limits, costs, and troubleshooting.

### Cost Considerations

Development costs primarily stem from API usage.

*   **Google APIs**: Places API costs ~$17 per 1000 Text Search requests, and Routes API costs ~$5 per 1000 route requests, offset by a $200 monthly credit.
*   **Amadeus APIs**: The test environment is free but limited. Production uses pay-per-use pricing, estimated at ~$0.50–2.00 per complete trip query.
*   **Recommendations**: Implement caching, use test environments, set up budget alerts, and consider request batching.

### Future Enhancements

Potential future work includes:
1.  Adding a caching layer (Redis) for frequently searched cities/hotels.
2.  Implementing async API calls for improved performance.
3.  Adding support for alternative APIs (e.g., Skyscanner, Booking.com).
4.  Creating route visualization on maps.
5.  Adding real-time price tracking and alerts.
6.  Implementing user preferences and personalization.
7.  Adding support for multi-city trips (beyond point-to-point travel).
8.  Integrating weather data for destination planning.

### Security Considerations

Security requires rigorous adherence to best practices, especially concerning tool usage which represents arbitrary code execution paths.

*   Credentials **MUST NOT** be committed to version control; environment variables **MUST** be used.
*   Implement API key rotation and request logging (sanitizing sensitive data).
*   User input **MUST** be validated and sanitized.
*   Rate limiting **MUST** be implemented on user-facing endpoints.
*   All API communications **SHOULD** use HTTPS.
*   Hosts **MUST** obtain explicit user consent before invoking any tool, as tools represent arbitrary code execution.

### Notes

*   All date formats should be ISO 8601 (YYYY-MM-DD).
*   All prices should include currency code.
*   Consider time zones and handle multi-airport cities (e.g., NYC).

***

**Analogy for LLM Delegation Insight:**

The observed difference between larger and smaller models is similar to hiring a company CEO versus a team manager. The **larger model (CEO)** tends to believe it can handle all major tasks internally, relying on its vast general knowledge to synthesize a full solution without detailed consultation. The **smaller model (Team Manager)**, knowing its own scope and limitations, is more inclined to follow the established workflow—eagerly delegating specific, complex tasks (like booking flights or finding obscure hotels) to its predefined **specialists (sub-agents/tools)**, thereby ensuring the distributed workload achieves the collective goal effectively.
