import time
import schedule
import logging
from datetime import datetime

import config
from api_client import FootballAPI
from analyzer import BetAnalyzer
from telegram_bot import BettingBot
from bet_tracker import BetTracker
from kelly_criterion import KellyCriterion

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_analysis():
    logger.info("Starting analysis cycle...")
    
    api = FootballAPI()
    analyzer = BetAnalyzer()
    bot = BettingBot()
    tracker = BetTracker()
    kelly = KellyCriterion(config.BANKROLL, config.KELLY_FRACTION)
    
    all_bets = []
    
    for league_name, league_id in config.LEAGUES.items():
        logger.info(f"Checking {league_name}...")
        
        # 0. Get Top Scorers & Standings (Cached for this run)
        top_scorers = api.get_top_scorers(league_id)
        standings = api.get_standings(league_id)
        
        # Helper to find rank
        def get_rank(team_id, standings_list):
            for row in standings_list:
                if row['team']['id'] == team_id:
                    return row['rank']
            return 10 # Default middle rank if not found
        
        # 1. Get Fixtures with Odds
        fixtures = api.get_fixtures_with_odds(league_id)
        
        if not fixtures:
            logger.warning(f"No fixtures found for {league_name}")
            continue
            
        for fixture_obj in fixtures:
            try:
                fixture = fixture_obj["fixture"]
                
                # Date Filter (Next 3 days)
                match_date = datetime.fromisoformat(fixture["date"].replace("Z", "+00:00"))
                if match_date > datetime.now(match_date.tzinfo) + datetime.timedelta(days=3):
                    continue

                # Check Odds availability
                if not fixture_obj.get("bookmakers"):
                    continue
                    
                odds = fixture_obj["bookmakers"][0]["bets"][0]["values"]
                home_odd = next((float(o["odd"]) for o in odds if o["value"] == "Home"), 0)
                away_odd = next((float(o["odd"]) for o in odds if o["value"] == "Away"), 0)
                
                if home_odd == 0 or away_odd == 0:
                    continue

                # Get Team Stats
                home_team = fixture_obj["teams"]["home"]
                away_team = fixture_obj["teams"]["away"]
                
                home_stats = api.get_team_stats(home_team["id"], league_id)
                away_stats = api.get_team_stats(away_team["id"], league_id)
                
                if not home_stats or not away_stats:
                    continue
                
                # --- LEVEL 3: DROPPING ODDS CHECK ---
                # Create a unique match ID (e.g., "2024-05-20_PSG_Lyon")
                match_id = f"{fixture['date'][:10]}_{home_team['name']}_{away_team['name']}".replace(" ", "")
                drop_alerts = tracker.check_dropping_odds(match_id, home_odd, away_odd)
                
                # If significant drop, we can boost confidence or just add it to reasons
                drop_reason = " | ".join(drop_alerts) if drop_alerts else None
                # ------------------------------------
                
                # --- NEW: STANDINGS CHECK ---
                home_rank = get_rank(home_team["id"], standings)
                away_rank = get_rank(away_team["id"], standings)
                rank_reason = analyzer.analyze_standings(home_rank, away_rank)
                # ----------------------------

                # Helper to get odds by ID
                def get_bet_values(bet_id):
                    for b in fixture_obj["bookmakers"][0]["bets"]:
                        if b["id"] == bet_id:
                            return b["values"]
                    return []

                # 1. MATCH WINNER (ID 1)
                # Analyze Home Bet
                reason_home = analyzer.analyze_bet(home_stats, away_stats, home_odd, "home", home_team["name"], away_team["name"])
                if reason_home or (drop_reason and "DOMICILE" in drop_reason) or (rank_reason and "Avantage" in rank_reason and home_rank < away_rank):
                    full_reason = reason_home if reason_home else ""
                    if drop_reason and "DOMICILE" in drop_reason:
                        full_reason = f"{drop_reason} | {full_reason}" if full_reason else drop_reason
                    if rank_reason and home_rank < away_rank:
                         full_reason = f"{rank_reason} | {full_reason}" if full_reason else rank_reason
                    
                    if full_reason:
                        confidence = analyzer.calculate_confidence(home_stats, home_odd, "home")
                        if drop_reason and "DOMICILE" in drop_reason: confidence = min(100, confidence + 15)
                        if rank_reason and home_rank < away_rank: confidence = min(100, confidence + 10) # Boost for rank
                        stake_info = kelly.get_recommendation(home_odd, confidence)
                        
                        all_bets.append({
                            "match": f"{home_team['name']} vs {away_team['name']}",
                            "date": fixture["date"][:10],
                            "heure": fixture["date"][11:16],
                            "ligue": league_name,
                            "pari": f"Victoire {home_team['name']}",
                            "cote": home_odd,
                            "raison": full_reason,
                            "confiance": confidence,
                            "stake": stake_info['stake'],
                            "recommendation": stake_info['recommendation'],
                            "fixture_id": fixture["id"],
                            "match_id": match_id
                        })

                # Analyze Away Bet
                reason_away = analyzer.analyze_bet(home_stats, away_stats, away_odd, "away", away_team["name"], home_team["name"])
                if reason_away or (drop_reason and "EXTÉRIEUR" in drop_reason) or (rank_reason and "Avantage" in rank_reason and away_rank < home_rank):
                    full_reason = reason_away if reason_away else ""
                    if drop_reason and "EXTÉRIEUR" in drop_reason:
                        full_reason = f"{drop_reason} | {full_reason}" if full_reason else drop_reason
                    if rank_reason and away_rank < home_rank:
                         full_reason = f"{rank_reason} | {full_reason}" if full_reason else rank_reason
                        
                    if full_reason:
                        confidence = analyzer.calculate_confidence(away_stats, away_odd, "away")
                        if drop_reason and "EXTÉRIEUR" in drop_reason: confidence = min(100, confidence + 15)
                        if rank_reason and away_rank < home_rank: confidence = min(100, confidence + 10) # Boost for rank

                        stake_info = kelly.get_recommendation(away_odd, confidence)
                        
                        all_bets.append({
                            "match": f"{home_team['name']} vs {away_team['name']}",
                            "date": fixture["date"][:10],
                            "heure": fixture["date"][11:16],
                            "ligue": league_name,
                            "pari": f"Victoire {away_team['name']}",
                            "cote": away_odd,
                            "raison": full_reason,
                            "confiance": confidence,
                            "stake": stake_info['stake'],
                            "recommendation": stake_info['recommendation'],
                            "fixture_id": fixture["id"],
                            "match_id": match_id
                        })

                # 2. OVER/UNDER 1.5 GOALS (ID 5)
                ou_values = get_bet_values(5)
                over_15_odd = next((float(o["odd"]) for o in ou_values if o["value"] == "Over 1.5"), 0)
                if over_15_odd > 0:
                    reason_ou = analyzer.analyze_over15(home_stats, away_stats, over_15_odd)
                    if reason_ou:
                        confidence = 80 # High base confidence for Over 1.5 strategy
                        stake_info = kelly.get_recommendation(over_15_odd, confidence)
                        all_bets.append({
                            "match": f"{home_team['name']} vs {away_team['name']}",
                            "date": fixture["date"][:10],
                            "heure": fixture["date"][11:16],
                            "ligue": league_name,
                            "pari": "Plus de 1.5 Buts",
                            "cote": over_15_odd,
                            "raison": reason_ou,
                            "confiance": confidence,
                            "stake": stake_info['stake'],
                            "recommendation": stake_info['recommendation'],
                            "fixture_id": fixture["id"],
                            "match_id": match_id
                        })

                # 3. BOTH TEAMS TO SCORE (ID 8)
                btts_values = get_bet_values(8)
                btts_yes_odd = next((float(o["odd"]) for o in btts_values if o["value"] == "Yes"), 0)
                if btts_yes_odd > 0:
                    reason_btts = analyzer.analyze_btts(home_stats, away_stats, btts_yes_odd)
                    if reason_btts:
                        confidence = 75
                        stake_info = kelly.get_recommendation(btts_yes_odd, confidence)
                        all_bets.append({
                            "match": f"{home_team['name']} vs {away_team['name']}",
                            "date": fixture["date"][:10],
                            "heure": fixture["date"][11:16],
                            "ligue": league_name,
                            "pari": "Les 2 équipes marquent",
                            "cote": btts_yes_odd,
                            "raison": reason_btts,
                            "confiance": confidence,
                            "stake": stake_info['stake'],
                            "recommendation": stake_info['recommendation'],
                            "fixture_id": fixture["id"],
                            "match_id": match_id
                        })
                
                # 4. GOALSCORERS (ID 4)
                if top_scorers:
                    scorer_values = get_bet_values(4)
                    if scorer_values:
                        # Check only players with odds > 2.0 (filtered in analyzer)
                        # Optimization: Only check players in top_scorers list to avoid looping 100 players
                        # But odds list has player names.
                        for odd_obj in scorer_values:
                            player_name = odd_obj["value"]
                            player_odd = float(odd_obj["odd"])
                            
                            reason_scorer = analyzer.analyze_goalscorer(player_name, player_odd, top_scorers)
                            if reason_scorer:
                                confidence = 70 # Base confidence for goalscorers
                                stake_info = kelly.get_recommendation(player_odd, confidence)
                                all_bets.append({
                                    "match": f"{home_team['name']} vs {away_team['name']}",
                                    "date": fixture["date"][:10],
                                    "heure": fixture["date"][11:16],
                                    "ligue": league_name,
                                    "pari": f"Buteur: {player_name}",
                                    "cote": player_odd,
                                    "raison": reason_scorer,
                                    "confiance": confidence,
                                    "stake": stake_info['stake'],
                                    "recommendation": stake_info['recommendation'],
                                    "fixture_id": fixture["id"],
                                    "match_id": match_id
                                })
                    
            except Exception as e:
                logger.error(f"Error processing fixture: {e}")
                continue

    # Sort and Save to Pending
    if all_bets:
        all_bets.sort(key=lambda x: x["confiance"], reverse=True)
        top_bets = all_bets[:5]
        
        for bet in top_bets:
            # Save to pending bets
            tracker.add_pending_bet(bet, bet['fixture_id'], bet['match_id'])
            
        logger.info(f"Saved {len(top_bets)} pending bets")
    else:
        logger.info("No value bets found this cycle.")

def run_validation():
    """Check pending bets and validate with lineups."""
    logger.info("Starting validation cycle...")
    
    api = FootballAPI()
    analyzer = BetAnalyzer()
    bot = BettingBot()
    tracker = BetTracker()
    
    pending_bets = tracker.get_pending_bets()
    
    for p_bet in pending_bets:
        try:
            bet_data = p_bet['bet_data']
            match_date = datetime.fromisoformat(bet_data['date'] + "T" + bet_data['heure'] + ":00")
            # Assuming date is YYYY-MM-DD and heure is HH:MM
            # We need to be careful with timezone. Let's assume local time or handle it simpler.
            # Actually, let's use the created_at or just check the API for time.
            
            # Better: Check time difference now
            # We need a robust way to parse the date string we saved.
            # bet_data['date'] is "2024-05-20"
            # bet_data['heure'] is "21:00"
            match_dt = datetime.strptime(f"{bet_data['date']} {bet_data['heure']}", "%Y-%m-%d %H:%M")
            
            # Add timezone info if needed, but let's assume system time matches
            time_diff = match_dt - datetime.now()
            minutes_diff = time_diff.total_seconds() / 60
            
            # If match is in 10 to 75 minutes (Lineups usually out 60 mins before)
            if 10 <= minutes_diff <= 75:
                logger.info(f"Validating match {bet_data['match']}...")
                
                lineups = api.get_fixture_lineups(p_bet['fixture_id'])
                
                if lineups and len(lineups) >= 2:
                    # Extract StartXI
                    home_xi = lineups[0]['startXI']
                    away_xi = lineups[1]['startXI']
                    
                    is_valid, reason = analyzer.validate_lineup(bet_data, home_xi, away_xi)
                    
                    if is_valid:
                        # Add validation reason
                        bet_data['raison'] += f" | {reason}"
                        
                        # Send and Record
                        bet_id = tracker.record_bet(bet_data, bet_data['stake'])
                        bot.send_bet_with_buttons(bet_data, bet_id)
                        
                        # Remove from pending
                        tracker.remove_pending_bet(p_bet['id'])
                        logger.info(f"Validated and sent bet {bet_id}")
                    else:
                        logger.info(f"Bet invalid due to lineup: {reason}")
                        tracker.remove_pending_bet(p_bet['id'])
                else:
                    logger.info("Lineups not yet available.")
            
            elif minutes_diff < 0:
                # Match started, remove pending
                tracker.remove_pending_bet(p_bet['id'])
                
        except Exception as e:
            logger.error(f"Error validating bet {p_bet['id']}: {e}")

def start_scheduler():
    schedule.every(2).hours.do(run_analysis)
    schedule.every(15).minutes.do(run_validation)
    logger.info("Scheduler started (Analysis: 2h, Validation: 15m)...")
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_bot_polling():
    bot = BettingBot()
    tracker = BetTracker()
    
    @bot.bot.callback_query_handler(func=lambda call: True)
    def callback_query(call):
        try:
            action, bet_id = call.data.split("_")
            bet_id = int(bet_id)
            
            if action == "win":
                # Calculate profit
                # We need to fetch the bet to get odds and stake
                # For now, let's just mark it as won. 
                # Ideally BetTracker should handle profit calc.
                # Let's update BetTracker to calculate profit on update
                tracker.update_result(bet_id, "won", 0) # Profit calc needed in tracker
                bot.bot.answer_callback_query(call.id, "✅ Pari marqué comme GAGNÉ !")
                bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                          text=f"{call.message.text}\n\n✅ RÉSULTAT: GAGNÉ")
                
                # Celebration GIF
                import random
                gifs = [
                    "https://media1.tenor.com/m/uy_OBkkROWIAAAAd/yummy-tongue.gif"
                ]
                try:
                    bot.bot.send_animation(call.message.chat.id, random.choice(gifs), caption="🤑 BOOOOM ! ENCAISSÉ !")
                except:
                    pass
            elif action == "loss":
                tracker.update_result(bet_id, "lost", 0)
                bot.bot.answer_callback_query(call.id, "❌ Pari marqué comme PERDU")
                bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                          text=f"{call.message.text}\n\n❌ RÉSULTAT: PERDU")
        except Exception as e:
            logger.error(f"Callback error: {e}")

    logger.info("Bot polling started...")
    bot.bot.infinity_polling()

if __name__ == "__main__":
    import threading
    
    # Initial run
    try:
        bot = BettingBot()
        bot.send_welcome()
        # Run analysis once in a separate thread so it doesn't block polling start
        threading.Thread(target=run_analysis).start()
    except Exception as e:
        logger.error(f"Startup error: {e}")

    # Start Scheduler Thread
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Start Bot Polling (Main Thread)
    start_bot_polling()
