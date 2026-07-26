"""stockskill: reproducible stock analysis. The LLM never does the math --
every number comes from the tested functions in these submodules.
"""

from .cli import main

__all__ = ["main"]
__version__ = "0.1.0"
