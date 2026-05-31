"""
============================================================
J.A.R.V.I.S. — Web & Information Skills
Layer 5: Information & Web (FR-14 to FR-17)
============================================================
Handles: web search, news, weather, Wikipedia, quick facts,
         currency conversion, time/date
"""

import webbrowser
import urllib.parse
import logging
import requests
from datetime import datetime

from core.brain import Intent, Response
from config import Config

log = logging.getLogger("jarvis.skills.web")

REQUEST_TIMEOUT = 8   # seconds


# ══════════════════════════════════════════════════════════
# FR-14: Web Search
# ══════════════════════════════════════════════════════════
def handle_web_search(intent: Intent) -> Response:
    query = intent.params.get("query", "").strip()
    if not query:
        return Response(text="What would you like me to search for, Sir?", success=False)

    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    return Response(text=f"Searching Google for {query}, Sir.")


# ══════════════════════════════════════════════════════════
# FR-15: News Summaries
# ══════════════════════════════════════════════════════════
CATEGORY_MAP = {
    "technology": "technology",
    "tech": "technology",
    "sports": "sports",
    "sport": "sports",
    "india": "general",     # NewsAPI doesn't have India-specific; use top-headlines with country=in
    "business": "business",
    "finance": "business",
    "general": "general",
}


def handle_news(intent: Intent) -> Response:
    category = intent.params.get("category", "general")
    api_key = Config.news_api_key

    if not api_key:
        return Response(
            text="News API key not configured, Sir. Please add it to your .env file.",
            success=False
        )

    try:
        mapped_cat = CATEGORY_MAP.get(category, "general")
        params = {
            "apiKey": api_key,
            "pageSize": 5,
            "language": "en",
        }

        if category == "india":
            params["country"] = "in"
            url = "https://newsapi.org/v2/top-headlines"
        else:
            params["category"] = mapped_cat
            params["country"] = "us"
            url = "https://newsapi.org/v2/top-headlines"

        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()

        articles = data.get("articles", [])
        if not articles:
            return Response(text="No news articles found right now, Sir.")

        headlines = [a["title"] for a in articles[:5] if a.get("title")]
        summary = f"Here are the top {len(headlines)} {category} headlines, Sir: "
        summary += ". ".join(f"Number {i+1}: {h}" for i, h in enumerate(headlines))

        return Response(text=summary, data={"headlines": headlines})

    except requests.exceptions.ConnectionError:
        return Response(
            text="No internet connection, Sir. I cannot fetch the news right now.",
            success=False
        )
    except Exception as e:
        log.error("News fetch error: %s", e)
        return Response(text=f"News service error, Sir: {e}", success=False)


# ══════════════════════════════════════════════════════════
# FR-16: Weather
# ══════════════════════════════════════════════════════════
def handle_weather(intent: Intent) -> Response:
    api_key = Config.weather_api_key
    city = Config.weather_city
    units = Config.weather_units

    # Fallback: no-key weather via wttr.in
    if not api_key:
        try:
            location = city or ""
            url = f"https://wttr.in/{urllib.parse.quote(location)}?format=3"
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                weather_text = resp.text.strip()
                return Response(text=f"Weather update: {weather_text}", data={"raw": weather_text})
        except requests.exceptions.ConnectionError:
            return Response(text="No internet connection for weather, Sir.", success=False)
        except Exception as e:
            log.error("wttr.in error: %s", e)

        return Response(
            text="Weather API key not configured, Sir. Add it to your .env file for accurate forecasts.",
            success=False
        )

    try:
        params = {
            "appid": api_key,
            "units": units,
            "q": city,
        }
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        data = resp.json()

        if resp.status_code != 200:
            return Response(text=f"Weather service error: {data.get('message', 'Unknown error')}", success=False)

        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        desc = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]
        city_name = data["name"]
        unit_symbol = "°C" if units == "metric" else "°F"

        return Response(
            text=(
                f"Current weather in {city_name}: {desc}, "
                f"{temp:.0f}{unit_symbol}, feels like {feels:.0f}{unit_symbol}, "
                f"humidity {humidity}%, Sir."
            ),
            data=data
        )

    except requests.exceptions.ConnectionError:
        return Response(text="No internet connection, Sir.", success=False)
    except Exception as e:
        log.error("Weather error: %s", e)
        return Response(text=f"Weather service unavailable, Sir: {e}", success=False)


# ══════════════════════════════════════════════════════════
# FR-17: Quick Facts — Wikipedia
# ══════════════════════════════════════════════════════════
def handle_what_is(intent: Intent) -> Response:
    query = intent.params.get("query", "").strip()
    if not query:
        return Response(text="What would you like to know about, Sir?", success=False)

    try:
        import wikipedia
        wikipedia.set_lang("en")
        try:
            summary = wikipedia.summary(query, sentences=2, auto_suggest=True)
            return Response(
                text=summary,
                data={"source": "wikipedia", "query": query}
            )
        except wikipedia.exceptions.DisambiguationError as e:
            # Use first option
            try:
                summary = wikipedia.summary(e.options[0], sentences=2)
                return Response(text=summary)
            except Exception:
                return Response(text=f"There are multiple results for {query}, Sir. Could you be more specific?")
        except wikipedia.exceptions.PageError:
            # Will fall through to AI query
            pass

    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        log.warning("Wikipedia error: %s", e)

    # Fallback: route to AI
    from core.brain import Intent as I
    return Response(
        text=f"Let me check with my AI systems about {query}...",
        data={"fallback_to_ai": True, "prompt": f"What is {query}? Give a brief 2-3 sentence answer."}
    )


# ══════════════════════════════════════════════════════════
# FR-17: Currency Conversion
# ══════════════════════════════════════════════════════════
def handle_currency_convert(intent: Intent) -> Response:
    amount = intent.params.get("amount", 1.0)
    from_c = intent.params.get("from_currency", "USD")
    to_c = intent.params.get("to_currency", "INR")
    api_key = Config.exchange_api_key

    try:
        if api_key:
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_c}/{to_c}/{amount}"
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            if data.get("result") == "success":
                converted = data["conversion_result"]
                rate = data["conversion_rate"]
                return Response(
                    text=f"{amount:.2f} {from_c} is {converted:.2f} {to_c}, Sir. Rate: 1 {from_c} = {rate:.4f} {to_c}.",
                    data={"rate": rate, "result": converted}
                )
        else:
            # Fallback: open Google currency conversion
            query = f"{amount} {from_c} to {to_c}"
            encoded = urllib.parse.quote(query)
            webbrowser.open(f"https://www.google.com/search?q={encoded}")
            return Response(text=f"Opening Google for the {from_c} to {to_c} conversion, Sir.")

    except requests.exceptions.ConnectionError:
        return Response(text="No internet connection for currency conversion, Sir.", success=False)
    except Exception as e:
        log.error("Currency conversion error: %s", e)
        return Response(text=f"Currency conversion failed, Sir: {e}", success=False)

    return Response(text="Currency conversion service unavailable, Sir.", success=False)


# ══════════════════════════════════════════════════════════
# FR-14: Open Website
# ══════════════════════════════════════════════════════════
def handle_open_website(intent: Intent) -> Response:
    website = intent.params.get("website", "").lower().strip()
    if not website:
        return Response(text="Which website should I open, Sir?", success=False)

    # Common domains mapping
    domains = {
        "youtube": "https://youtube.com",
        "google": "https://google.com",
        "facebook": "https://facebook.com",
        "twitter": "https://twitter.com",
        "reddit": "https://reddit.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com"
    }

    url = domains.get(website)
    if not url:
        url = f"https://{website}.com"

    try:
        webbrowser.open(url)
        return Response(text=f"Opening {website.title()}, Sir.")
    except Exception as e:
        log.error("Failed to open website %s: %s", website, e)
        return Response(text=f"I was unable to open {website.title()}, Sir.", success=False)


def register(brain):
    """Register all web/info skill handlers."""
    brain.register_skill("web_search", handle_web_search)
    brain.register_skill("news", handle_news)
    brain.register_skill("weather", handle_weather)
    brain.register_skill("what_is", handle_what_is)
    brain.register_skill("currency_convert", handle_currency_convert)
    brain.register_skill("open_website", handle_open_website)
