"""Test all scrapers against live sites — leaderboard only, max 3 entries."""

import asyncio
import time
import sys

from phoenix.scrapers.registry import discover_scrapers, list_scrapers, get_scraper


async def test_one(name: str) -> dict:
    start = time.time()
    try:
        scraper = get_scraper(name)
        try:
            entries = await asyncio.wait_for(
                scraper.scrape_leaderboard(max_entries=3),
                timeout=45.0,
            )
            elapsed = round(time.time() - start, 1)
            if entries:
                usernames = [e.username for e in entries]
                return {"status": "ok", "count": len(entries), "sample": usernames, "time": elapsed}
            else:
                return {"status": "empty", "count": 0, "time": elapsed}
        except asyncio.TimeoutError:
            return {"status": "timeout", "time": round(time.time() - start, 1)}
        except Exception as e:
            return {"status": "error", "error": str(e)[:120], "time": round(time.time() - start, 1)}
        finally:
            await scraper.close()
    except Exception as e:
        return {"status": "init_error", "error": str(e)[:120]}


async def main():
    discover_scrapers()
    platforms = list_scrapers()

    # If args provided, only test those
    if len(sys.argv) > 1:
        platforms = [p for p in sys.argv[1:] if p in platforms]

    print(f"\nTesting {len(platforms)} scrapers against live sites...\n")
    print(f"{'Platform':<20} {'Status':<10} {'Count':<6} {'Time':<8} {'Details'}")
    print("-" * 90)

    results = {"ok": 0, "empty": 0, "error": 0, "timeout": 0}

    for name in platforms:
        r = await test_one(name)
        status = r["status"]
        results[status] = results.get(status, 0) + 1

        details = ""
        if status == "ok":
            details = f"users: {r['sample']}"
        elif status in ("error", "init_error"):
            details = r.get("error", "")

        time_str = f"{r.get('time', '?')}s"
        count_str = str(r.get("count", "-"))
        icon = {"ok": "+", "empty": "~", "error": "X", "timeout": "T", "init_error": "!"}
        print(f"[{icon.get(status, '?')}] {name:<18} {status:<10} {count_str:<6} {time_str:<8} {details}")

    print("-" * 90)
    print(f"\nSummary: {results.get('ok', 0)} ok, {results.get('empty', 0)} empty, "
          f"{results.get('error', 0)} errors, {results.get('timeout', 0)} timeouts")


if __name__ == "__main__":
    asyncio.run(main())
