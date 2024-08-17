import os
import functools

def ensure_report_directory_exists(func):
    """
    Decorator to ensure the report directory exists before executing the decorated function.

    Parameters
    ----------
    func : function
        The function to be decorated.

    Returns
    -------
    function
        The wrapped function that ensures the report directory exists.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not os.path.exists(self.report_directory_path()):
            os.makedirs(self.report_directory_path())
        return func(self, *args, **kwargs)
    return wrapper

def ensure_model_directory_exists(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not os.path.exists(self.model_directory_path()):
            os.makedirs(self.model_directory_path())
        return func(self, *args, **kwargs)
    return wrapper