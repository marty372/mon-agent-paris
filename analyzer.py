import config
import math

class BetAnalyzer:
    def poisson_probability(self, lmbda, k):
        """Calculate Poisson probability P(k; lambda)."""
        return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

    def calculate_fair_odds(self, home_avg, away_avg):
        """
        Calculate fair odds using Poisson distribution.
        Returns (home_fair_odd, draw_fair_odd, away_fair_odd)
        """
        # Limit goals to reasonable max for calculation
        max_goals = 6
        
        prob_home_win = 0
        prob_draw = 0
        prob_away_win = 0
        
        for home_goals in range(max_goals):
            for away_goals in range(max_goals):
                p = self.poisson_probability(home_avg, home_goals) * self.poisson_probability(away_avg, away_goals)
                
                if home_goals > away_goals:
                    prob_home_win += p
                elif home_goals == away_goals:
                    prob_draw += p
                else:
                    prob_away_win += p
                    
        # Avoid division by zero
        fair_home = 1 / prob_home_win if prob_home_win > 0 else 999
        fair_draw = 1 / prob_draw if prob_draw > 0 else 999
        fair_away = 1 / prob_away_win if prob_away_win > 0 else 999
        
        return fair_home, fair_draw, fair_away
    def analyze_bet(self, home_stats, away_stats, odd, location, team_name, opponent_name):
        """
        Analyze if a bet is valuable based on improved criteria.
        location: 'home' or 'away' (perspective of the team we are betting on)
        """
        
        # 1. Check odds range
        if odd < config.COTE_MIN or odd > config.COTE_MAX:
            return None
            
        reasons = []
        
        # Extract specific stats based on location
        # API-Football structure: response.fixtures.wins.home, etc.
        # We need to be careful with the structure returned by api_client.get_team_stats
        # Assuming api_client returns the full 'response' object from 'teams/statistics'
        
        # Helper to safely get nested keys
        def get_stat(stats, path, default=0):
            val = stats
            for key in path:
                if isinstance(val, dict):
                    val = val.get(key, default)
                else:
                    return default
            return val

        # Stats for the team we are betting on (Home or Away specific)
        team_wins_l5 = get_stat(home_stats, ["form"], "").count('W') if location == 'home' else get_stat(away_stats, ["form"], "").count('W')
        # Actually, the 'form' string is usually global. Let's stick to global form for now as it's a good indicator, 
        # but we should look at home/away specific goals.
        
        # Let's use the 'fixtures' object for wins
        if location == 'home':
            team_wins = get_stat(home_stats, ["fixtures", "wins", "home"])
            team_played = get_stat(home_stats, ["fixtures", "played", "home"])
            team_goals_for = get_stat(home_stats, ["goals", "for", "average", "home"])
            team_goals_against = get_stat(home_stats, ["goals", "against", "average", "home"])
            
            opp_goals_for = get_stat(away_stats, ["goals", "for", "average", "away"])
            opp_goals_against = get_stat(away_stats, ["goals", "against", "average", "away"])
        else:
            team_wins = get_stat(away_stats, ["fixtures", "wins", "away"])
            team_played = get_stat(away_stats, ["fixtures", "played", "away"])
            team_goals_for = get_stat(away_stats, ["goals", "for", "average", "away"])
            team_goals_against = get_stat(away_stats, ["goals", "against", "average", "away"])
            
            opp_goals_for = get_stat(home_stats, ["goals", "for", "average", "home"])
            opp_goals_against = get_stat(home_stats, ["goals", "against", "average", "home"])

        # Convert string averages to float if necessary (API sometimes returns strings)
        try:
            team_goals_for = float(team_goals_for) if team_goals_for else 0.0
            team_goals_against = float(team_goals_against) if team_goals_against else 0.0
            opp_goals_for = float(opp_goals_for) if opp_goals_for else 0.0
            opp_goals_against = float(opp_goals_against) if opp_goals_against else 0.0
        except ValueError:
            pass

        # CRITERIA 1: Win Rate > 50% in respective location
        win_rate = (team_wins / team_played) if team_played > 0 else 0
        if win_rate >= 0.5:
            reasons.append(f"✅ Solide à {location} ({int(win_rate*100)}% victoires)")

        # CRITERIA 2: Form (Last 5) - Global
        # We use the form string "WWLDW"
        form = get_stat(home_stats if location == 'home' else away_stats, ["form"])
        last_5_wins = form[-5:].count('W')
        if last_5_wins >= config.VICTORIES_MIN:
            reasons.append(f"🔥 Forme récente: {last_5_wins}/5 victoires")

        # CRITERIA 3: Attack Strength (Scoring more than opponent concedes)
        if team_goals_for > opp_goals_against:
            reasons.append(f"⚽ Attaque performante ({team_goals_for} buts/m)")

        # CRITERIA 4: Defense Strength (Conceding less than opponent scores)
        if team_goals_against < opp_goals_for:
            reasons.append(f"🛡️ Défense solide ({team_goals_against} enc./m)")

        # CRITERIA 5: Poisson Value Bet (The Math Check)
        # We calculate fair odds based on averages
        try:
            if location == 'home':
                fair_home, _, _ = self.calculate_fair_odds(team_goals_for, opp_goals_against) # Simplified: using team attack vs opp defense
                # Better approach: Use team home attack and opp away defense for lambda 1, etc.
                # Let's stick to the passed averages which are already location specific
                lmbda_home = (team_goals_for + opp_goals_against) / 2
                lmbda_away = (opp_goals_for + team_goals_against) / 2
                
                fair_home, _, _ = self.calculate_fair_odds(lmbda_home, lmbda_away)
                fair_odd = fair_home
            else:
                lmbda_away = (team_goals_for + opp_goals_against) / 2
                lmbda_home = (opp_goals_for + team_goals_against) / 2
                
                _, _, fair_away = self.calculate_fair_odds(lmbda_home, lmbda_away)
                fair_odd = fair_away

            # If Bookmaker Odd is 10% higher than Fair Odd, it's a VALUE BET
            if odd > fair_odd * 1.10:
                reasons.append(f"💎 VALUE BET (Cote juste: {fair_odd:.2f})")
        except:
            pass

        # Decision
        if len(reasons) >= 2:
            return " | ".join(reasons)
        
        return None

    def calculate_confidence(self, stats, odd, location):
        """Calculate confidence score (0-100)."""
        score = 0
        
        # 1. Form (Max 30)
        form = stats.get("form", "")
        wins = form[-5:].count('W')
        score += wins * 6
        
        # 2. Odds Value (Max 30)
        if odd < 2.0: score += 30
        elif odd < 2.5: score += 20
        else: score += 10
        
        # 3. Location Strength (Max 40)
        # Using average goals as proxy for strength
        try:
            key = "home" if location == "home" else "away"
            gf = float(stats["goals"]["for"]["average"][key])
            ga = float(stats["goals"]["against"]["average"][key])
            
            if gf > 1.5: score += 20
            if ga < 1.0: score += 20
        except:
            pass
            
        return min(score, 100)

    def analyze_standings(self, home_rank, away_rank):
        """Analyze based on league standings."""
        diff = away_rank - home_rank # Positive if Home is better (lower rank)
        
        if diff >= 10: # Huge gap (e.g. 1st vs 12th)
            return f"🔝 Écart de niveau ({home_rank}e vs {away_rank}e)"
        elif diff >= 5:
            return f"📈 Avantage classement ({home_rank}e vs {away_rank}e)"
            
        return None

    def analyze_over15(self, home_stats, away_stats, over_odd):
        """Analyze Over 1.5 Goals market."""
        if over_odd < 1.20 or over_odd > 2.00: # Safety range
            return None
            
        try:
            # Get averages
            h_gf = float(home_stats["goals"]["for"]["average"]["home"])
            a_gf = float(away_stats["goals"]["for"]["average"]["away"])
            h_ga = float(home_stats["goals"]["against"]["average"]["home"])
            a_ga = float(away_stats["goals"]["against"]["average"]["away"])
            
            avg_total_goals = (h_gf + a_gf + h_ga + a_ga) / 2
            
            reasons = []
            if avg_total_goals > 2.5: # High scoring potential
                reasons.append(f"⚽ Match ouvert ({avg_total_goals:.1f} buts/m moy.)")
                
            # Check recent form scoring
            h_form = home_stats.get("form", "")
            a_form = away_stats.get("form", "")
            
            # If both teams scored in recent games (proxy for good attack)
            if reasons:
                return " | ".join(reasons)
                
        except:
            pass
        return None

    def analyze_btts(self, home_stats, away_stats, btts_odd):
        """Analyze Both Teams To Score market."""
        if btts_odd < 1.50 or btts_odd > 2.50:
            return None
            
        try:
            h_gf = float(home_stats["goals"]["for"]["average"]["home"])
            a_gf = float(away_stats["goals"]["for"]["average"]["away"])
            h_ga = float(home_stats["goals"]["against"]["average"]["home"])
            a_ga = float(away_stats["goals"]["against"]["average"]["away"])
            
            if h_gf > 1.2 and a_gf > 1.2 and h_ga > 1.0 and a_ga > 1.0:
                return f"🥅 Les deux équipes marquent et encaissent souvent (Dom: {h_gf}/{h_ga}, Ext: {a_gf}/{a_ga})"
        except:
            pass
        return None

    def analyze_goalscorer(self, player_name, odds, top_scorers):
        """Analyze Goalscorer market."""
        if odds < 2.00: # Minimum value
            return None
            
        # Check if player is in top scorers
        # top_scorers is a list of player objects from API
        for scorer in top_scorers:
            if scorer['player']['name'] in player_name or player_name in scorer['player']['name']:
                goals = scorer['statistics'][0]['goals']['total']
                return f"🎯 Top Buteur: {scorer['player']['name']} ({goals} buts)"
                
        return None

    def validate_lineup(self, bet_data, lineup_home, lineup_away):
        """
        Validate a bet against confirmed lineups.
        Returns (is_valid, reason)
        """
        bet_type = bet_data['pari']
        
        # Helper to check player presence
        def is_in_lineup(name, lineup):
            if not lineup: return False
            # API-Football lineup structure: list of {player: {id, name, ...}}
            for item in lineup:
                p_name = item['player']['name']
                # Simple substring match
                if name.lower() in p_name.lower() or p_name.lower() in name.lower():
                    return True
            return False

        # 1. Goalscorer Bet
        if "Buteur:" in bet_type:
            player_name = bet_type.replace("Buteur: ", "")
            
            # Check Home and Away lineups
            in_home = is_in_lineup(player_name, lineup_home)
            in_away = is_in_lineup(player_name, lineup_away)
            
            if in_home or in_away:
                return True, "✅ Joueur titulaire confirmé"
            else:
                return False, "❌ Joueur non titulaire (Remplaçant ou Absent)"
                
        # 2. For other bets (Win, Over/Under), we assume valid if lineups are out
        # We could add logic here to check if Top Scorer is missing for a Win bet
        return True, "✅ Compo officielle disponible"
