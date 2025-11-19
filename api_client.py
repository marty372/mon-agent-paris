import requests
import logging
from datetime import datetime, timedelta
import config

class FootballAPI:
    def __init__(self):
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-apisports-key": config.API_KEY
        }
        self.logger = logging.getLogger(__name__)

    def _get(self, endpoint, params=None):
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("response", [])
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API Request Error ({endpoint}): {e}")
            return None

    def get_fixtures_with_odds(self, league_id, season=2024, days_ahead=3):
        """Get fixtures with odds for a specific league."""
        # Note: The 'odds' endpoint in API-Football is complex. 
        # Often it's better to get fixtures first, then odds, or use the specific odds endpoint if available for the plan.
        # The original code used /odds directly. We will stick to that but ensure it works.
        
        params = {
            "league": league_id,
            "season": season,
            "bookmaker": 8  # Bet365
        }
        
        # We might need to filter by date manually if the API doesn't support a range in this endpoint
        return self._get("odds", params)

    def get_top_scorers(self, league_id, season=2024):
        """Get top 20 scorers for a league."""
        params = {
            "league": league_id,
            "season": season
        }
        data = self._get("players/topscorers", params)
        return data[:20] if data else []

    def get_standings(self, league_id, season=2024):
        """Get league standings."""
        params = {
            "league": league_id,
            "season": season
        }
        data = self._get("standings", params)
        if data and len(data) > 0:
            # API-Football structure: response[0]['league']['standings'][0] (for first group/table)
            return data[0]['league']['standings'][0]
        return []

    def get_team_stats(self, team_id, league_id, season=2024):
        """Get team statistics."""
        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }
        
        data = self._get("teams/statistics", params)
        if not data:
            return None
            
        # The API returns a list with one object for statistics usually, or just the object
        # Adjusting based on typical API-Football response structure
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return data
