import os,requests,pandas as pd,time,schedule
from datetime import datetime,timedelta
from telegram import Bot

TELEGRAM_TOKEN=os.getenv("8555500454:AAHb7e5uIHD0t-ucW_GQgFTeHd8KPxR_ewE")
TELEGRAM_CHAT_ID=os.getenv("7880229779")
API_KEY=os.getenv("API_KEY","182ed8841700cc7279181fba05bb8751")

LEAGUES={"Ligue 1":61,"Premier League":39,"LaLiga":140,"Serie A":135,"Bundesliga":78}
bot=Bot(token=TELEGRAM_TOKEN)

def get_matches():
    all_matches=[]
    headers={"x-apisports-key":API_KEY}
    for league_name,league_id in LEAGUES.items():
        url="https://v3.football.api-sports.io/fixtures"
        params={"league":league_id,"season":2024,"next":15}
        try:
            r=requests.get(url,headers=headers,params=params)
            if r.status_code==200:
                data=r.json()
                for f in data["response"]:
                    d=datetime.strptime(f["fixture"]["date"][:10],"%Y-%m-%d")
                    if d<=datetime.now()+timedelta(days=3):
                        all_matches.append({
                            "Date":f["fixture"]["date"][:10],
                            "Heure":f["fixture"]["date"][11:16],
                            "Ligue":league_name,
                            "Dom":f["teams"]["home"]["name"],
                            "Ext":f["teams"]["away"]["name"]
                        })
        except:pass
    return pd.DataFrame(all_matches)

def send_alerts():
    print(f"Analyse à {datetime.now().strftime('%H:%M')}")
    df=get_matches()
    if df.empty:return
    alerts=[]
    for _,m in df.iterrows():
        if "PSG" in m["Dom"] or "City" in m["Dom"]:
            alerts.append(f"⚽{m['Ligue']}|{m['Dom']}vs{m['Ext']}|{m['Date']}{m['Heure']}")
    if alerts:
        msg="🎯MATCHS À SUIVRE:\n"+"\n".join(alerts[:5])
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,text=msg)
        print(f"✅{len(alerts)}alertes")
    else:print("ℹ️Aucune alerte")

schedule.every().hour.do(send_alerts)

if __name__=="__main__":
    bot.send_message(chat_id=TELEGRAM_CHAT_ID,text="✅Agent 24/7 activé!")
    while True:
        schedule.run_pending()
        time.sleep(60)
