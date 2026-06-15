import pytest
from multi_rag import route_query

def test_route_query():
    queries = [
        ("My cotton has pink bollworm, what should I spray?", "crop_advisor"),
        ("What is the current market price and MSP of paddy?", "market_analyst"),
        ("How to register for PM-KISAN online?", "schemes_expert"),
        ("Is there any chance of rain tomorrow in Pune?", "weather_analyst"),
        ("Please scan this image of my yellowing leaf", "leaf_scanner"),
        ("Which NPK fertilizer is best for wheat crop?", "crop_advisor"),
        ("What is the demand for chillies in the APMC mandi?", "market_analyst"),
        ("Am I eligible for the PMFBY crop insurance?", "schemes_expert"),
        ("Is a drought expected in the upcoming kharif season?", "weather_analyst"),
        ("Diagnose the brown spots on my tomato plant leaves", "leaf_scanner"),
    ]
    
    for query, expected_agent in queries:
        routed_agents = route_query(query)
        assert expected_agent in routed_agents, f"Failed for query: {query}. Expected {expected_agent} in {routed_agents}"
