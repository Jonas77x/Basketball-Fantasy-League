"""Command line: `uv run fantasy` starts the web app, `uv run fantasy update-data` refreshes the data."""

import argparse
import logging
import threading
import webbrowser

from fantasy.config import get_settings


def serve() -> None:
    import uvicorn

    settings = get_settings()
    url = f"http://{'localhost' if settings.host in ('127.0.0.1', '0.0.0.0') else settings.host}:{settings.port}"
    print(f"\n  Fantasy-Assistent läuft: {url}\n  Beenden mit Strg+C\n")
    if settings.open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("fantasy.web.app:app", host=settings.host, port=settings.port, log_level="warning")


def update_data() -> None:
    from fantasy.sources.snapshots import update_all

    print("Lade aktuelle Daten (das dauert etwa eine halbe Minute, die Quellen werden höflich abgefragt) …")
    meta = update_all()
    for name, info in meta.items():
        print(f"  {name}: {info['rows']} Zeilen, Stand {info['fetched_at']}")
    print("Fertig. Starte den Assistenten neu, damit die neuen Daten geladen werden.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="fantasy", description="Persönlicher Fantasy-Basketball-Assistent")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Web-Oberfläche starten (Standard)")
    sub.add_parser("update-data", help="Stats, ADP und Rookies neu laden")
    args = parser.parse_args()
    if args.command == "update-data":
        update_data()
    else:
        serve()


if __name__ == "__main__":
    main()
