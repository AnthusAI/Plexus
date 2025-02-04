from typing import Dict, Any, Union, List

def truncate_dict_strings_inner(
    data: Dict[str, Any],
    max_length: int = 100,
    truncation_indicator: str = "..."
) -> Dict[str, Any]:
    def truncate_value(value: Any) -> Any:
        # Handle string values
        if isinstance(value, str) and len(value) > max_length:
            return value[:max_length - len(truncation_indicator)] + truncation_indicator
        
        # Handle dictionaries
        elif isinstance(value, dict):
            return truncate_dict_strings_inner(value, max_length, truncation_indicator)
        
        # Handle lists
        elif isinstance(value, list):
            return [truncate_value(item) for item in value]
        
        # Handle objects with __dict__ attribute (like Parameters)
        elif hasattr(value, '__dict__'):
            obj_dict = value.__dict__
            truncated_dict = truncate_dict_strings_inner(obj_dict, max_length, truncation_indicator)
            # Return as dict rather than trying to reconstruct the object
            return truncated_dict
        
        # Handle objects that need string conversion
        elif not isinstance(value, (int, float, bool, type(None))):
            str_value = str(value)
            if len(str_value) > max_length:
                return str_value[:max_length - len(truncation_indicator)] + truncation_indicator
            return str_value
            
        return value

    if isinstance(data, dict):
        return {key: truncate_value(value) for key, value in data.items()}
    try:
        dict_data = dict(data)
        return {key: truncate_value(value) for key, value in dict_data.items()}
    except (TypeError, ValueError):
        return f"<Non-dictionary value of type {type(data).__name__}>"

def truncate_dict_strings(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    max_length: int = 100,
    truncation_indicator: str = "..."
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    if isinstance(data, list):
        return [truncate_dict_strings_inner(d, max_length, truncation_indicator) 
                for d in data]
    return truncate_dict_strings_inner(data, max_length, truncation_indicator)