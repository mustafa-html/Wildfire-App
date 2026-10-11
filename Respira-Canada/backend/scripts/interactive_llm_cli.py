"""Chat with the assistant from the terminal.

    cd backend && python -m scripts.interactive_llm_cli --lat 51.05 --lon -114.07 --name "Calgary, AB"
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import services  # noqa: E402
from app.api.llm import DEFAULT_LOCATION, build_chat_response, build_context_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, default=DEFAULT_LOCATION["latitude"])
    parser.add_argument("--lon", type=float, default=DEFAULT_LOCATION["longitude"])
    parser.add_argument("--name", default=DEFAULT_LOCATION["name"])
    args = parser.parse_args()
    location = {"latitude": args.lat, "longitude": args.lon, "name": args.name}
    session = f"cli-{datetime.now().timestamp():.0f}"

    print("\nRespira wildfire assistant. Type ':data' for the live data, 'exit' to quit.\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit", ":q"}:
            break
        if text == ":data":
            print("\n" + build_context_text(services.location_context(args.lat, args.lon, args.name)))
            continue
        print(f"\nRespira: {build_chat_response(text, session, location).response}\n")


if __name__ == "__main__":
    main()
