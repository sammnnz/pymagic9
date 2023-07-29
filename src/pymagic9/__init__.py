"""
PyMagic9 - a library for analyzing call stacks using frames.
"""
from .pymagic9 import getframe, isfunctionincallchain, nameof

__author__ = "Sam Nazarov"
__version__ = "0.1.0rc"

# noinspection SpellCheckingInspection
__all__ = ['getframe', 'isfunctionincallchain', 'nameof']
