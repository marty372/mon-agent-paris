import sqlite3
import pandas as pd
import logging
import os
import psycopg2
from urllib.parse import urlparse

class BetTracker:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_url = os.getenv("DATABASE_URL")
        self.is_postgres = bool(self.db_url)
        
        if not self.is_postgres:
            self.db_path = "bets.db"
            self.logger.info(f"Using SQLite database at {self.db_path}")
        else:
            self.logger.info("Using PostgreSQL database")
            
        self._init_db()

    def _get_connection(self):
        """Get database connection based on configuration."""
        if self.is_postgres:
            return psycopg2.connect(self.db_url)
        else:
            return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database with tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # SQL syntax differences
        id_type = "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        timestamp_default = "CURRENT_TIMESTAMP"
        
        # Create Bets Table
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS bets (
                id {id_type},
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                league TEXT NOT NULL,
                match TEXT NOT NULL,
                bet_type TEXT NOT NULL,
                odds REAL NOT NULL,
                confidence INTEGER NOT NULL,
                reason TEXT,
                stake REAL,
                result TEXT,
                profit REAL,
                created_at TIMESTAMP DEFAULT {timestamp_default}
            )
        ''')
            
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS odds_history (
                match_id TEXT PRIMARY KEY,
                opening_home_odd REAL,
                opening_away_odd REAL,
                last_updated TIMESTAMP DEFAULT {timestamp_default}
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialized")

    def check_dropping_odds(self, match_id, current_home, current_away):
        """Check for dropping odds."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT opening_home_odd, opening_away_odd FROM odds_history WHERE match_id = %s" if self.is_postgres else "SELECT opening_home_odd, opening_away_odd FROM odds_history WHERE match_id = ?"
        cursor.execute(query, (match_id,))
        row = cursor.fetchone()
        
        alerts = []
        
        if row:
            open_home, open_away = row
            
            # Check Home Drop
            if open_home > 0:
                drop_home = (open_home - current_home) / open_home
                if drop_home >= 0.10: # 10% drop
                    alerts.append(f"📉 CHUTE COTE DOMICILE: {open_home} -> {current_home} (-{int(drop_home*100)}%)")
            
            # Check Away Drop
            if open_away > 0:
                drop_away = (open_away - current_away) / open_away
                if drop_away >= 0.10: # 10% drop
                    alerts.append(f"📉 CHUTE COTE EXTÉRIEUR: {open_away} -> {current_away} (-{int(drop_away*100)}%)")
        else:
            # First time seeing this match, record opening odds
            query = "INSERT INTO odds_history (match_id, opening_home_odd, opening_away_odd) VALUES (%s, %s, %s)" if self.is_postgres else "INSERT INTO odds_history (match_id, opening_home_odd, opening_away_odd) VALUES (?, ?, ?)"
            cursor.execute(query, (match_id, current_home, current_away))
            conn.commit()
            
        conn.close()
        return alerts
    
    def record_bet(self, bet_data, stake=None):
        """Record a bet in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            INSERT INTO bets (date, time, league, match, bet_type, odds, confidence, reason, stake)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''' if self.is_postgres else '''
            INSERT INTO bets (date, time, league, match, bet_type, odds, confidence, reason, stake)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        if self.is_postgres:
            query += " RETURNING id"
        
        cursor.execute(query, (
            bet_data['date'],
            bet_data['heure'],
            bet_data['ligue'],
            bet_data['match'],
            bet_data['pari'],
            bet_data['cote'],
            bet_data['confiance'],
            bet_data['raison'],
            stake
        ))
        
        if self.is_postgres:
            bet_id = cursor.fetchone()[0]
        else:
            bet_id = cursor.lastrowid
            
        conn.commit()
        conn.close()
        self.logger.info(f"Recorded bet: {bet_data['match']} (ID: {bet_id})")
        return bet_id
    
    def update_result(self, bet_id, result, profit=0):
        """Update the result of a bet (won/lost)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Calculate profit if not provided
        if profit == 0:
            query = "SELECT odds, stake FROM bets WHERE id = %s" if self.is_postgres else "SELECT odds, stake FROM bets WHERE id = ?"
            cursor.execute(query, (bet_id,))
            row = cursor.fetchone()
            if row:
                odds, stake = row
                if stake is None: stake = 0
                
                if result == "won":
                    profit = (stake * odds) - stake
                elif result == "lost":
                    profit = -stake
        
        query = '''
            UPDATE bets 
            SET result = %s, profit = %s
            WHERE id = %s
        ''' if self.is_postgres else '''
            UPDATE bets 
            SET result = ?, profit = ?
            WHERE id = ?
        '''
        
        cursor.execute(query, (result, profit, bet_id))
        
        conn.commit()
        conn.close()
        self.logger.info(f"Updated bet {bet_id}: {result} ({profit}€)")
    
    def get_statistics(self):
        """Get overall betting statistics."""
        conn = self._get_connection()
        # pandas read_sql works with psycopg2 connection too
        df = pd.read_sql_query("SELECT * FROM bets", conn)
        conn.close()
        
        if df.empty:
            return "Aucun pari enregistré."
            
        total_bets = len(df)
        won_bets = len(df[df['result'] == 'won'])
        lost_bets = len(df[df['result'] == 'lost'])
        win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
        total_profit = df['profit'].sum()
        
        return f"""
📊 STATISTIQUES
Total Paris: {total_bets}
Gagnés: {won_bets} | Perdus: {lost_bets}
Win Rate: {win_rate:.1f}%
Profit Total: {total_profit:.2f}€
        """
        
    def export_to_csv(self):
        """Export bets to CSV."""
        conn = self._get_connection()
        df = pd.read_sql_query("SELECT * FROM bets", conn)
        conn.close()
        df.to_csv("bets_export.csv", index=False)
        self.logger.info("Exported bets to bets_export.csv")
