import re
import sys

from enrich_activities import build_session, is_cookie_valid, update_cookie_in_supabase


def normalize_cookie(raw: str) -> str:
    # 🟢 Accepts a bare cookie value, a "_strava4_session=...;" pair, or a whole
    # Cookie: header line copied from DevTools -- extracts just the session value either way.
    raw = raw.strip()
    m = re.search(r"_strava4_session=([^;\s]+)", raw)
    value = m.group(1) if m else raw
    return f"_strava4_session={value};"


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else input("Paste the fresh _strava4_session cookie value: ")
    cookie = normalize_cookie(raw)

    session = build_session(cookie)
    if not is_cookie_valid(session):
        print("This cookie doesn't look valid (dashboard check failed) -- not saving it.")
        print("Grab a fresh value from a logged-in browser tab (DevTools > Application > Cookies > strava.com).")
        sys.exit(1)

    update_cookie_in_supabase(cookie)
    print("Cookie verified against /dashboard and saved to Supabase.")


if __name__ == "__main__":
    main()
