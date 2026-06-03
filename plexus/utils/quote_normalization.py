"""
Utilities for normalizing quote characters in text.

LLMs often return curly quotes (", ", ', ') instead of straight quotes (", ').
This module provides functions to normalize these for consistent text matching.
"""


def normalize_quotes(text: str) -> str:
    """
    Normalize curly quotes to straight quotes for transcript matching.

    Replaces Unicode curly quotes with their ASCII equivalents:
    - U+201C (") LEFT DOUBLE QUOTATION MARK  -> U+0022 (") QUOTATION MARK
    - U+201D (") RIGHT DOUBLE QUOTATION MARK -> U+0022 (") QUOTATION MARK
    - U+2018 (') LEFT SINGLE QUOTATION MARK  -> U+0027 (') APOSTROPHE
    - U+2019 (') RIGHT SINGLE QUOTATION MARK -> U+0027 (') APOSTROPHE

    Parameters
    ----------
    text : str
        Text that may contain curly quotes

    Returns
    -------
    str
        Text with all curly quotes replaced with straight quotes

    Examples
    --------
    >>> normalize_quotes('The agent said "hello" and the customer replied 'yes'')
    'The agent said "hello" and the customer replied 'yes''
    """
    if not text:
        return text

    # Replace double quotation marks using chr() to avoid curly quotes in source
    text = text.replace(chr(0x201C), chr(0x0022))  # LEFT DOUBLE QUOTATION MARK -> QUOTATION MARK
    text = text.replace(chr(0x201D), chr(0x0022))  # RIGHT DOUBLE QUOTATION MARK -> QUOTATION MARK

    # Replace single quotation marks
    text = text.replace(chr(0x2018), chr(0x0027))  # LEFT SINGLE QUOTATION MARK -> APOSTROPHE
    text = text.replace(chr(0x2019), chr(0x0027))  # RIGHT SINGLE QUOTATION MARK -> APOSTROPHE

    return text
