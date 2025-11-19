import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys and Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("API_KEY")

# Validation
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not API_KEY:
    raise ValueError("Missing environment variables: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, or API_KEY")

# Leagues Configuration (Name: ID)
LEAGUES = {
    "Ligue 1": 61,
    "Premier League": 39,
    "LaLiga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Champions League": 2
}

# Betting Parameters
COTE_MIN = 1.5
COTE_MAX = 3.0
VICTORIES_MIN = 3  # Minimum wins in last 5 games

# Bankroll Management
BANKROLL = float(os.getenv("BANKROLL", "100"))  # Default 100€
KELLY_FRACTION = 0.25  # Quarter Kelly (conservative)
