import click
from typing import Tuple, Dict

def parse_kv_pairs(params: Tuple[str]) -> Dict[str, str]:
    """
    Parses a tuple of strings in "key=value" format into a dictionary.

    Args:
        params: A tuple of strings, e.g., ("key1=value1", "key2=value2").

    Returns:
        A dictionary of the parsed key-value pairs.

    Raises:
        ValueError: If a parameter string is not in the key=value format.
    """
    parsed_dict = {}
    for param in params:
        if '=' not in param:
            raise ValueError(f"Invalid parameter format: '{param}'. Expected 'key=value'.")
        key, value = param.split('=', 1)
        if not key:
             raise ValueError(f"Invalid parameter format: '{param}'. Key cannot be empty.")
        parsed_dict[key.strip()] = value.strip()
    return parsed_dict 