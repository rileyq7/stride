#!/usr/bin/env python
"""
Test LLM overlay for shoe matching recommendations.

This script:
1. Simulates a quiz session with specific answers
2. Runs the current heuristic matching
3. Sends the top candidates to Granite for re-ranking/validation
4. Compares results

Run: python backend/scripts/test_llm_matching_overlay.py
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import requests
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.models.catalog import ShoeProduct, ShoeModel, Gender, Terrain
from app.services.matching import MatchingService, UserProfile, FootProfile, UserPreferences


# Set LLM provider - options: "replicate", "ollama", "none"
# For Replicate, set REPLICATE_API_TOKEN in your .env
os.environ["LLM_PROVIDER"] = "replicate"
os.environ["REPLICATE_MODEL"] = "ibm-granite/granite-4.0-h-small"


async def call_llm_provider(prompt: str, max_tokens: int = 1500) -> str:
    """Call the configured LLM provider."""
    from app.services.llm_provider import get_llm_provider
    provider = get_llm_provider()
    return await provider.generate(prompt, max_tokens)


def build_llm_rerank_prompt(user_profile: dict, candidates: list[dict]) -> str:
    """Build prompt for LLM to re-rank shoe candidates."""

    # Format user profile
    profile_text = f"""
USER PROFILE:
- Pronation: {user_profile.get('pronation', 'neutral')}
- Foot width: {user_profile.get('width', 'standard')}
- Arch type: {user_profile.get('arch', 'neutral')}
- Foot issues: {', '.join(user_profile.get('issues', [])) or 'None'}
- Budget: {user_profile.get('budget', 'any')}
- Terrain: {user_profile.get('terrain', 'road')}
- Distance: {user_profile.get('distance', 'mixed')}
- Priorities: {', '.join(user_profile.get('priorities', [])) or 'None specified'}
- Experience: {user_profile.get('experience', 'recreational')}
"""

    # Format candidates
    candidates_text = ""
    for i, shoe in enumerate(candidates, 1):
        candidates_text += f"""
SHOE {i}: {shoe['brand']} {shoe['name']}
- Price: ${shoe.get('price', 'Unknown')}
- Weight: {shoe.get('weight_oz', 'Unknown')}oz
- Drop: {shoe.get('drop_mm', 'Unknown')}mm
- Support type: {shoe.get('support_type', 'Unknown')}
- Current heuristic score: {shoe.get('score', 0):.0%}
"""

    prompt = f"""You are a running shoe expert. Given a user's profile and a list of candidate shoes from our database,
re-rank the shoes from best to worst match. Consider:

1. CRITICAL - Budget: Never recommend shoes over the user's budget as top picks
2. Pronation needs: Overpronators need stability shoes, not neutral/racing shoes
3. Foot issues: Match specific needs (wide feet need wide options, plantar fasciitis needs cushion)
4. Use case: Match terrain and distance preferences

{profile_text}

CANDIDATE SHOES (pre-filtered from our database):
{candidates_text}

TASK: Return a JSON object with your re-ranked recommendations. Format:
{{
    "rankings": [
        {{
            "rank": 1,
            "shoe_index": <original index 1-10>,
            "shoe_name": "Brand Model",
            "score": 0.95,
            "reasoning": "Brief explanation why this is the best match"
        }},
        ...
    ],
    "disqualified": [
        {{
            "shoe_index": <index>,
            "shoe_name": "Brand Model",
            "reason": "Why this shoe should NOT be recommended (e.g., over budget, wrong support type)"
        }}
    ],
    "notes": "Any general observations about the match quality"
}}

Return ONLY the JSON, no other text.
"""
    return prompt


async def get_candidates_for_profile(
    gender: str = "mens",
    terrain: str = "road",
    budget: str = "under_100",
    pronation: str = "overpronation",
    priorities: list = None,
    limit: int = 10
) -> tuple[list[dict], UserProfile]:
    """Get candidate shoes using the heuristic matching."""

    priorities = priorities or ["stability"]

    # Build user profile
    foot = FootProfile(
        width="standard",
        arch="neutral" if pronation == "neutral" else "flat",
        pronation=pronation,
        issues=["overpronation"] if pronation == "overpronation" else []
    )

    preferences = UserPreferences(
        priorities=priorities,
        budget=budget,
        experience="recreational",
        gender=gender,
        distances=["5k", "10k", "half_marathon"],
        terrain=terrain,
    )

    user_profile = UserProfile(
        category="running",
        foot=foot,
        preferences=preferences,
    )

    async with async_session_maker() as db:
        # Query products
        query = select(ShoeProduct).where(
            ShoeProduct.is_active == True,
        ).join(ShoeModel).options(
            selectinload(ShoeProduct.model).selectinload(ShoeModel.brand),
            selectinload(ShoeProduct.offers),
        )

        # Gender filter
        gender_map = {"mens": Gender.MENS, "womens": Gender.WOMENS}
        if gender in gender_map:
            query = query.where(
                (ShoeModel.gender == gender_map[gender]) | (ShoeModel.gender == Gender.UNISEX)
            )

        # Terrain filter
        terrain_map = {"road": Terrain.ROAD, "trail": Terrain.TRAIL, "track": Terrain.TRACK}
        if terrain in terrain_map:
            query = query.where(ShoeModel.terrain == terrain_map[terrain])

        result = await db.execute(query)
        products = result.scalars().all()

        # Score with heuristic matching
        matching_service = MatchingService(db)
        scored = []
        for product in products:
            score, component_scores = matching_service.calculate_match_score(product, user_profile)

            # Get price
            prices = [float(o.price) for o in (product.offers or []) if o.price and o.in_stock]
            price = min(prices) if prices else (float(product.msrp_usd) if product.msrp_usd else None)

            model = product.model
            scored.append({
                "id": str(product.id),
                "brand": model.brand.name if model and model.brand else "Unknown",
                "name": product.name,
                "price": price,
                "weight_oz": float(product.weight_oz) if product.weight_oz else None,
                "drop_mm": float(product.drop_mm) if product.drop_mm else None,
                "support_type": model.support_type.value if model and model.support_type else "unknown",
                "score": score,
                "component_scores": component_scores,
            })

        # Sort by score and take top N
        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored[:limit], user_profile


def extract_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response."""
    import re

    # Try to find JSON block
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'(\{[\s\S]*\})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Try parsing the whole thing
    try:
        return json.loads(text)
    except:
        return {}


async def test_scenario(
    name: str,
    gender: str = "mens",
    terrain: str = "road",
    budget: str = "under_100",
    pronation: str = "overpronation",
    priorities: list = None
):
    """Test a specific matching scenario."""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{'='*70}")

    candidates, user_profile = await get_candidates_for_profile(
        gender=gender,
        terrain=terrain,
        budget=budget,
        pronation=pronation,
        priorities=priorities or ["stability"]
    )

    print(f"\nUser Profile:")
    print(f"  Gender: {gender}")
    print(f"  Terrain: {terrain}")
    print(f"  Budget: {budget}")
    print(f"  Pronation: {pronation}")
    print(f"  Priorities: {priorities or ['stability']}")

    print(f"\n--- HEURISTIC MATCHING (Top 10) ---")
    for i, shoe in enumerate(candidates, 1):
        budget_score = shoe['component_scores'].get('budget', 0)
        pronation_score = shoe['component_scores'].get('pronation', 0)
        print(f"{i}. {shoe['brand']} {shoe['name']}")
        print(f"   Price: ${shoe['price']:.0f}" if shoe['price'] else "   Price: Unknown")
        print(f"   Score: {shoe['score']:.0%} (budget={budget_score:.0%}, pronation={pronation_score:.0%})")
        print(f"   Support: {shoe['support_type']}, Weight: {shoe['weight_oz']}oz")

    # Now call LLM
    print(f"\n--- CALLING LLM FOR RE-RANKING ---")

    user_dict = {
        "pronation": user_profile.foot.pronation,
        "width": user_profile.foot.width,
        "arch": user_profile.foot.arch,
        "issues": user_profile.foot.issues,
        "budget": user_profile.preferences.budget,
        "terrain": user_profile.preferences.terrain,
        "priorities": user_profile.preferences.priorities,
        "experience": user_profile.preferences.experience,
    }

    prompt = build_llm_rerank_prompt(user_dict, candidates)

    response = await call_llm_provider(prompt)

    if not response:
        print("No response from Granite")
        return

    print(f"\nRaw LLM response (first 500 chars):")
    print(response[:500])

    parsed = extract_json_from_response(response)

    if parsed:
        print(f"\n--- LLM RE-RANKED RESULTS ---")

        if "rankings" in parsed:
            for item in parsed["rankings"][:5]:
                print(f"{item.get('rank', '?')}. {item.get('shoe_name', 'Unknown')}")
                print(f"   LLM Score: {item.get('score', 0):.0%}")
                print(f"   Reasoning: {item.get('reasoning', 'N/A')}")

        if "disqualified" in parsed and parsed["disqualified"]:
            print(f"\n--- DISQUALIFIED BY LLM ---")
            for item in parsed["disqualified"]:
                print(f"- {item.get('shoe_name', 'Unknown')}: {item.get('reason', 'N/A')}")

        if "notes" in parsed:
            print(f"\nLLM Notes: {parsed['notes']}")
    else:
        print("Could not parse LLM response as JSON")


async def main():
    print("="*70)
    print("LLM MATCHING OVERLAY TEST")
    print("="*70)

    # Test scenario 1: Budget-conscious overpronator
    await test_scenario(
        name="Budget overpronator (under $100, needs stability)",
        budget="under_100",
        pronation="overpronation",
        priorities=["stability", "price"]
    )

    # Test scenario 2: Neutral runner, mid budget
    await test_scenario(
        name="Neutral runner, mid budget ($100-150)",
        budget="100_150",
        pronation="neutral",
        priorities=["cushion", "durability"]
    )

    # Test scenario 3: Speed-focused, any budget
    await test_scenario(
        name="Speed-focused runner, any budget",
        budget="any",
        pronation="neutral",
        priorities=["speed"]
    )


if __name__ == "__main__":
    asyncio.run(main())
