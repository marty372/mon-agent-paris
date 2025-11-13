import os
import requests
import pandas as pd
import time
import schedule
from datetime import datetime, timedelta
from telegram import Bot

# Variables d'environnement correctement utilisées
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

# Vérification des variables sensibles
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not API_KEY:
    raise ValueError("Un des tokens/ID/clé API requis est absent des variables d'environnement.")

bot = Bot(token=TELEGRAM_TOKEN)

def get_matches():
    all_matches = []
    headers = {"x-apisports-key": API_KEY}
    for league_name, league_id in LEAGUES.items():
        url = "https://v3.football.api-sports.io/fixtures"
        params = {"league": league_id, "season": 2024, "next": 15}
        try:
            r = requests.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            for f in data["response"]:
                dt_str = f["fixture"]["date"]
                dt_obj = datetime.strptime(dt_str[:16], "%Y-%m-%dT%H:%M")
                if dt_obj <= datetime.now() + timedelta(days=3):
                    all_matches.append({
                        "Date": dt_str[:10],
                        "Heure": dt_str[11:16],
                        "Ligue": league_name,
                        "Dom": f["teams"]["home"]["name"],
                        "Ext": f["teams"]["away"]["name"]
                    })
        except Exception as e:
            print(f"Erreur lors du téléchargement pour {league_name} : {e}")
    return pd.DataFrame(all_matches)

def send_alerts():
    print(f"Analyse à {datetime.now().strftime('%H:%M')}")
    df = get_matches()
    if df.empty:
        print("Aucun match trouvé")
        return
    alerts = []
    for _, m in df.iterrows():
        if "PSG" in m["Dom"] or "City" in m["Dom"]:
            alerts.append(f"⚽ {m['Ligue']} | {m['Dom']} vs {m['Ext']} | {m['Date']} {m['Heure']}")
    if alerts:
        msg = "🎯 MATCHS À SUIVRE:\n" + "\n".join(alerts[:5])
        try:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
            print(f"✅ {len(alerts)} alertes envoyées")
        except Exception as e:
            print(f"Erreur Telegram : {e}")
    else:
        print("ℹ️ Aucune alerte")

schedule.every().hour.do(send_alerts)

if __name__ == "__main__":
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Agent 24/7 activé !")
    except Exception as e:
        print(f"Erreur lancement Telegram : {e}")
    while True:
        schedule.run_pending()
        time.sleep(60)
