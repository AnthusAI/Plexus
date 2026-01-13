import importlib
import inspect
import logging
import sys


class InputSourceFactory:
    """
    Factory for creating input source instances from class names.
    Mirrors ProcessorFactory pattern for consistency.
    """

    @staticmethod
    def create_input_source(source_name: str, **options):
        """
        Create an input source instance dynamically.

        Args:
            source_name: Class name (e.g., "TextFileInputSource")
            **options: Configuration options passed to __init__

        Returns:
            Instantiated InputSource subclass
        """
        try:
            importlib.import_module("plexus.input_sources")

            # Dynamically load all classes from the module
            source_classes = {
                name: cls
                for name, cls in inspect.getmembers(
                    sys.modules["plexus.input_sources"], inspect.isclass
                )
            }

            if source_name not in source_classes:
                raise ValueError(f"Unknown input source: {source_name}")

            source_class = source_classes[source_name]
            return source_class(**options)

        except Exception as e:
            logging.error(f"Error creating input source {source_name}: {e}")
            raise
