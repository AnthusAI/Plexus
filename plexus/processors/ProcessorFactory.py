import importlib
import inspect
import sys

class ProcessorFactory:
    """
    Factory for creating processor instances based on the name of the processor's class.
    """
    @staticmethod
    def create_processor(processor_name, **parameters):
        module = importlib.import_module('plexus.processors')
        
        # Dynamically load all classes from the module
        processor_classes = {name: cls for name, cls in inspect.getmembers(sys.modules['plexus.processors'], inspect.isclass)}
        
        if processor_name not in processor_classes:
            raise ValueError(f"Unknown processor: {processor_name}")
        
        processor_class = processor_classes[processor_name]
        return processor_class(**parameters)