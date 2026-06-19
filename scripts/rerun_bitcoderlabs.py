"""Reset BitCoderLabs business state and re-enqueue website/contact/social/scoring workers.

Usage:
    uv run python scripts/rerun_bitcoderlabs.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path so the script can be run with:
#   uv run python scripts/rerun_bitcoderlabs.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from leadforge_database import get_session_ctx
from leadforge_database.models import Business, WebsiteStatus
from leadforge_worker_core.core import enqueue_job


async def main():

    # The BitCoderLabs business IDs
    business_ids = [
        "ce0522b2-19b2-4dd4-bcfd-a50e83b527bf",  # BitCoderLabs Pvt Limited Software Technology Park Peshawar
        "970a3f8d-d467-4a8c-a333-7a80bc3a5f58",  # BitCoderLabs Private Limited
    ]

    print("=" * 60)
    print("Resetting BitCoderLabs business state for re-processing...")
    print("=" * 60)

    async with get_session_ctx() as session:
        for bid in business_ids:
            print(f"\n--- Processing business: {bid} ---")

            # Get business name
            result = await session.execute(select(Business).where(Business.id == bid))
            business = result.scalar_one_or_none()
            if not business:
                print(f"  ❌ Business {bid} not found!")
                continue
            print(f"  Business: {business.name}")

            # Reset website status
            business.website_status = WebsiteStatus.UNKNOWN
            print(f"  ✅ Reset website_status to UNKNOWN")

        await session.commit()
        print(f"\n✅ Database state reset complete!")

    # Enqueue website jobs for each business
    print(f"\n{'=' * 60}")
    print(f"Enqueuing worker jobs...")
    print(f"{'=' * 60}")

    for bid in business_ids:
        # Get business name
        async with get_session_ctx() as session:
            result = await session.execute(select(Business).where(Business.id == bid))
            business = result.scalar_one_or_none()
            name = business.name if business else bid

        print(f"\n  → {name}")
        print(f"    Enqueuing website worker...")
        await enqueue_job("website", "website", {"business_id": bid})
        print(f"    ✅ website job enqueued!")

    print(f"\n{'=' * 60}")
    print(f"✅ All jobs enqueued! Workers should process them shortly.")
    print(f"{'=' * 60}")
    print(f"\nWorker pipeline that will run:")
    print(f"  1. website worker  → analyzes/finds website")
    print(f"  2. contact worker  → extracts contacts (from website + business record)")
    print(f"  3. social worker   → discovers social profiles (from website + name search)")
    print(f"  4. scoring worker  → recalculates lead score")


if __name__ == "__main__":
    asyncio.run(main())
