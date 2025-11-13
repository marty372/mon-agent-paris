import os
import requests
import pandas as pd
import time
import schedule
from datetime import datetime, timedelta
from telegram import Bot

# Variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("API_KEY")

LEAGUES = {
    "Ligue 1": 61,
    "Premier League": 39,
    "LaLiga": 140,
    "Serie A": 135,
    "Bundesliga": 78
}

# Paramètres de paris
COTE_MIN = 1.5  # Cote minimale intéressante
COTE_MAX = 3.0  # Cote maximale (trop risqué au-delà)
VICTORIES_MIN = 3  # Minimum de victoires sur 5 derniers matchs

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not API_KEY:
    raise ValueError("Variables d'environnement manquantes")

bot = Bot(token=TELEGRAM_TOKEN)

def get_team_stats(team_id, league_id):
    """Récupère les stats d'une équipe"""
    url = "https://v3.football.api-sports.io/teams/statistics"
    params = {"team": team_id, "league": league_id, "season": 2024}
    headers = {"x-apisports-key": API_KEY}
    
    try:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()["response"]
        
        # Extraire les stats importantes
        form = data["form"][-5:]  # 5 derniers matchs
        wins = form.count('W')
        goals_for = data["goals"]["for"]["total"]["total"]
        goals_against = data["goals"]["against"]["total"]["total"]
        
        return {
            "wins_last_5": wins,
            "form": form,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "clean_sheets": data["clean_sheet"]["total"]
        }
    except Exception as e:
        print(f"Erreur stats: {e}")
        return None

def get_matches_with_odds():
    """Récupère matchs + cotes + stats"""
    all_bets = []
    headers = {"x-apisports-key": API_KEY}
    
    for league_name, league_id in LEAGUES.items():
        # Récupérer les matchs avec cotes
        url = "https://v3.football.api-sports.io/odds"
        params = {
            "league": league_id,
            "season": 2024,
            "bet": 1,  # Match Winner (1X2)
            "bookmaker": 8  # Bet365
        }
        
        try:
            r = requests.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            
            for fixture in data["response"]:
                fixture_data = fixture["fixture"]
                dt = datetime.strptime(fixture_data["date"][:16], "%Y-%m-%dT%H:%M")
                
                # Seulement matchs dans les 3 prochains jours
                if dt > datetime.now() + timedelta(days=3):
                    continue
                
                # Extraire les cotes
                if not fixture.get("bookmakers"):
                    continue
                    
                odds = fixture["bookmakers"][0]["bets"][0]["values"]
                home_odd = float([o["odd"] for o in odds if o["value"] == "Home"][0])
                away_odd = float([o["odd"] for o in odds if o["value"] == "Away"][0])
                
                # Récupérer les stats des équipes
                home_team = fixture["teams"]["home"]
                away_team = fixture["teams"]["away"]
                
                home_stats = get_team_stats(home_team["id"], league_id)
                away_stats = get_team_stats(away_team["id"], league_id)
                
                if not home_stats or not away_stats:
                    continue
                
                # ANALYSE : Détecter les value bets
                bet_home = analyze_bet(
                    home_stats, away_stats, home_odd, "Domicile",
                    home_team["name"], away_team["name"]
                )
                
                bet_away = analyze_bet(
                    away_stats, home_stats, away_odd, "Extérieur",
                    away_team["name"], home_team["name"]
                )
                
                if bet_home:
                    all_bets.append({
                        "date": fixture_data["date"][:10],
                        "heure": fixture_data["date"][11:16],
                        "ligue": league_name,
                        "match": f"{home_team['name']} vs {away_team['name']}",
                        "pari": f"Victoire {home_team['name']}",
                        "cote": home_odd,
                        "raison": bet_home,
                        "confiance": calculate_confidence(home_stats, home_odd)
                    })
                
                if bet_away:
                    all_bets.append({
                        "date": fixture_data["date"][:10],
                        "heure": fixture_data["date"][11:16],
                        "ligue": league_name,
                        "match": f"{home_team['name']} vs {away_team['name']}",
                        "pari": f"Victoire {away_team['name']}",
                        "cote": away_odd,
                        "raison": bet_away,
                        "confiance": calculate_confidence(away_stats, away_odd)
                    })
                    
        except Exception as e:
            print(f"Erreur {league_name}: {e}")
    
    return sorted(all_bets, key=lambda x: x["confiance"], reverse=True)

def analyze_bet(team_stats, opponent_stats, odd, location, team_name, opponent_name):
    """Analyse si un pari est intéressant"""
    
    # Vérifier cote dans la range acceptable
    if odd < COTE_MIN or odd > COTE_MAX:
        return None
    
    reasons = []
    
    # Critère 1 : Forme récente excellente
    if team_stats["wins_last_5"] >= VICTORIES_MIN:
        reasons.append(f"✅ Forme: {team_stats['wins_last_5']}/5 victoires")
    
    # Critère 2 : Différence de forme significative
    if team_stats["wins_last_5"] - opponent_stats["wins_last_5"] >= 2:
        reasons.append(f"🔥 Meilleure forme que l'adversaire")
    
    # Critère 3 : Attaque forte
    if team_stats["goals_for"] > opponent_stats["goals_for"] * 1.2:
        reasons.append(f"⚽ Attaque supérieure ({team_stats['goals_for']} buts)")
    
    # Critère 4 : Défense solide
    if team_stats["goals_against"] < opponent_stats["goals_against"] * 0.8:
        reasons.append(f"🛡️ Défense solide")
    
    # Au moins 2 critères remplis pour recommander
    if len(reasons) >= 2:
        return " | ".join(reasons)
    
    return None

def calculate_confidence(stats, odd):
    """Calcule un score de confiance (0-100)"""
    score = 0
    
    # Forme récente (max 40 points)
    score += stats["wins_last_5"] * 8
    
    # Cote (max 30 points) - cote basse = plus sûr
    if odd < 2.0:
        score += 30
    elif odd < 2.5:
        score += 20
    else:
        score += 10
    
    # Bilan offensif/défensif (max 30 points)
    if stats["goals_for"] > 30:
        score += 15
    if stats["goals_against"] < 20:
        score += 15
    
    return min(score, 100)

def send_alerts():
    """Envoie les meilleurs paris"""
    print(f"🔍 Analyse à {datetime.now().strftime('%H:%M')}")
    
    best_bets = get_matches_with_odds()
    
    if not best_bets:
        print("ℹ️ Aucun pari intéressant trouvé")
        return
    
    # Top 5 paris avec meilleure confiance
    top_bets = best_bets[:5]
    
    msg = "🎯 TOP PARIS DU JOUR\n\n"
    
    for i, bet in enumerate(top_bets, 1):
        msg += f"{i}. {bet['match']}\n"
        msg += f"   📅 {bet['date']} à {bet['heure']}\n"
        msg += f"   🎭 {bet['ligue']}\n"
        msg += f"   🎯 Pari: {bet['pari']}\n"
        msg += f"   💰 Cote: {bet['cote']}\n"
        msg += f"   📈 Confiance: {bet['confiance']}%\n"
        msg += f"   {bet['raison']}\n\n"
    
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        print(f"✅ {len(top_bets)} paris envoyés")
    except Exception as e:
        print(f"❌ Erreur Telegram: {e}")

schedule.every(6).hours.do(send_alerts)  # Toutes les 6h

if __name__ == "__main__":
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Agent Paris Intelligence activé !")
        send_alerts()  # Analyse immédiate au démarrage
    except Exception as e:
        print(f"Erreur démarrage: {e}")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
