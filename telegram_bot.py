import telebot
import logging
import config

class BettingBot:
    def __init__(self):
        self.bot = telebot.TeleBot(config.TELEGRAM_TOKEN)
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.logger = logging.getLogger(__name__)

    def send_message(self, message):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message)
            self.logger.info("Message sent to Telegram")
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")

    def send_welcome(self):
        self.send_message("✅ Agent Paris Intelligence activé ! Prêt à analyser les matchs.")

    def format_bets(self, bets):
        if not bets:
            return "ℹ️ Aucun pari intéressant trouvé pour le moment."
            
        msg = "🎯 TOP PARIS DU JOUR\n\n"
        for i, bet in enumerate(bets, 1):
            msg += f"{i}. {bet['match']}\n"
            msg += f"   📅 {bet['date']} à {bet['heure']}\n"
            msg += f"   🎭 {bet['ligue']}\n"
            msg += f"   🎯 Pari: {bet['pari']}\n"
            msg += f"   💰 Cote: {bet['cote']}\n"
            msg += f"   📈 Confiance: {bet['confiance']}%\n"
            msg += f"   💵 {bet['recommendation']}\n"
            msg += f"   {bet['raison']}\n\n"
        return msg

    def send_bet_with_buttons(self, bet_data, bet_id):
        """Send a single bet with interactive buttons and premium formatting."""
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(
            InlineKeyboardButton("✅ Gagné", callback_data=f"win_{bet_id}"),
            InlineKeyboardButton("❌ Perdu", callback_data=f"loss_{bet_id}")
        )
        
        # Create confidence bar (e.g., [🟩🟩🟩🟩⬜])
        conf_score = bet_data['confiance']
        blocks = int(conf_score / 20)
        bar = "🟩" * blocks + "⬜" * (5 - blocks)
        
        # Format Reasons as bullet points
        reasons_list = bet_data['raison'].split(' | ')
        formatted_reasons = "\n".join([f"• {r}" for r in reasons_list])
        
        msg = f"🚨 **{bet_data['pari']}** @ **{bet_data['cote']}**\n"
        msg += f"⚽️ {bet_data['match']}\n"
        msg += f"🛡 Confiance: `{bar}` {conf_score}%\n"
        msg += f"💵 **{bet_data['recommendation']}**\n\n"
        msg += f"{formatted_reasons}"
        
        try:
            self.bot.send_message(chat_id=self.chat_id, text=msg, reply_markup=markup, parse_mode="Markdown")
            self.logger.info(f"Sent interactive bet {bet_id}")
        
        except Exception as e:
            self.logger.error(f"Failed to send interactive message: {e}")
