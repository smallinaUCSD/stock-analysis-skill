"""Trade layer: ATR-based setup + position sizing, options-strategy suggestions.
Informational risk framework, not personalized advice.
"""

from .setup import TradeSetup, atr_trade_setup, PositionSize, position_size
from .options_strategy import OptionIdea, implied_move, suggest_options

__all__ = [
    "TradeSetup", "atr_trade_setup", "PositionSize", "position_size",
    "OptionIdea", "implied_move", "suggest_options",
]
