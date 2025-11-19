import config

class KellyCriterion:
    def __init__(self, bankroll, kelly_fraction=0.25):
        """
        Initialize Kelly Criterion calculator.
        
        Args:
            bankroll: Total amount of money available for betting
            kelly_fraction: Fraction of Kelly to use (0.25 = Quarter Kelly, safer)
        """
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
    
    def calculate_stake(self, odds, confidence):
        """
        Calculate optimal stake using Kelly Criterion.
        
        Args:
            odds: Decimal odds (e.g., 2.0)
            confidence: Confidence percentage (0-100)
        
        Returns:
            Recommended stake amount
        """
        # Convert confidence to probability
        win_probability = confidence / 100.0
        
        # Kelly formula: f = (bp - q) / b
        # where:
        # f = fraction of bankroll to bet
        # b = odds - 1 (net odds)
        # p = probability of winning
        # q = probability of losing (1 - p)
        
        b = odds - 1
        p = win_probability
        q = 1 - p
        
        # Calculate Kelly percentage
        kelly_percentage = (b * p - q) / b
        
        # If Kelly is negative or zero, don't bet
        if kelly_percentage <= 0:
            return 0
        
        # Apply Kelly fraction for safety (Quarter Kelly is common)
        adjusted_kelly = kelly_percentage * self.kelly_fraction
        
        # Calculate stake
        stake = self.bankroll * adjusted_kelly
        
        # Round to 2 decimals
        return round(max(0, stake), 2)
    
    def update_bankroll(self, new_bankroll):
        """Update the bankroll amount."""
        self.bankroll = new_bankroll
    
    def get_recommendation(self, odds, confidence):
        """
        Get a human-readable betting recommendation.
        
        Returns:
            Dictionary with stake and recommendation text
        """
        stake = self.calculate_stake(odds, confidence)
        
        if stake == 0:
            return {
                'stake': 0,
                'recommendation': "❌ Ne pas parier (Kelly négatif)"
            }
        
        percentage = (stake / self.bankroll) * 100
        
        if percentage < 1:
            risk_level = "🟢 Très faible"
        elif percentage < 3:
            risk_level = "🟡 Faible"
        elif percentage < 5:
            risk_level = "🟠 Modéré"
        else:
            risk_level = "🔴 Élevé"
        
        return {
            'stake': stake,
            'percentage': round(percentage, 2),
            'recommendation': f"Mise recommandée: {stake}€ ({percentage:.1f}% de la banque) - Risque: {risk_level}"
        }
