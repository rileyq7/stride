#!/usr/bin/env python
"""
Test the review summarizer with real reviews.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.review_summarizer import summarize_reviews, result_to_consensus_dict


def main():
    print("=" * 70)
    print("REVIEW SUMMARIZER TEST")
    print("=" * 70)

    # Sample reviews for testing
    test_reviews = [
        {
            "source": "believe_in_the_run",
            "reviewer_name": "Chad",
            "rating": 4.5,
            "body": """The Brooks Ghost 16 continues to be one of the most reliable daily trainers.
            The DNA Loft v3 foam provides excellent cushioning without feeling mushy.
            Runs true to size for me - I wore my normal 10.5. The fit is accommodating with a
            medium-width toe box that should work for most foot shapes. Great for easy runs and
            long runs alike. The only downside is the weight at 10.1oz which is slightly heavier
            than some competitors."""
        },
        {
            "source": "believe_in_the_run",
            "reviewer_name": "Thomas",
            "rating": 4.0,
            "body": """I have wide feet and found the Ghost 16 to fit well in the forefoot.
            The toe box has enough room without being sloppy. I'd recommend going half size up
            if you have particularly wide feet. The cushioning is plush and works great for
            recovery runs. Not ideal for tempo work - too soft and heavy for that."""
        },
        {
            "source": "user_review",
            "reviewer_name": "RunnerJohn",
            "rating": 5.0,
            "body": """Best daily trainer I've owned. True to size, comfortable from the first run.
            The cushioning is perfect for my 50mpw training. Durable too - I'm at 300 miles and
            they still feel fresh. Only complaint is they run a bit warm in summer."""
        },
        {
            "source": "user_review",
            "reviewer_name": "MarathonMary",
            "rating": 4.0,
            "body": """Solid shoe for easy days. I have narrow feet and wish it came in a narrow width
            option - the standard width feels a bit loose in the midfoot. Went with my normal size
            and the length is perfect. Great cushioning for long runs."""
        },
    ]

    print("\nSummarizing 4 reviews for Brooks Ghost 16...")
    print("(This will call the LLM - may take 10-15 seconds)")

    result = summarize_reviews("Brooks Ghost 16", test_reviews)

    if result:
        print("\n--- SUMMARY RESULT ---")
        print(f"Sizing: {result.sizing_verdict} (confidence: {result.sizing_confidence:.0%})")
        if result.sizing_notes:
            print(f"  Notes: {result.sizing_notes}")

        print(f"\nWidth:")
        print(f"  Forefoot: {result.width_forefoot}")
        print(f"  Midfoot: {result.width_midfoot}")
        print(f"  Heel: {result.width_heel}")

        print(f"\nPros:")
        for pro in result.pros:
            print(f"  ✓ {pro}")

        print(f"\nCons:")
        for con in result.cons:
            print(f"  ✗ {con}")

        print(f"\nBest for:")
        for bf in result.best_for:
            print(f"  → {bf}")

        print(f"\nAvoid if:")
        for av in result.avoid_if:
            print(f"  → {av}")

        if result.notable_quotes:
            print(f"\nNotable quotes:")
            for q in result.notable_quotes:
                print(f"  \"{q.get('quote', '')}\" - {q.get('reviewer', '')}")

        print(f"\nOverall sentiment: {result.overall_sentiment:.0%}")

        # Show as consensus dict
        print("\n--- AS CONSENSUS JSON ---")
        import json
        consensus = result_to_consensus_dict(result)
        print(json.dumps(consensus, indent=2))

    else:
        print("ERROR: Summarization failed")


if __name__ == '__main__':
    main()
