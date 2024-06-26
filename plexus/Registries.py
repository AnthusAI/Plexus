import logging

class BaseRegistry:
    def __init__(self):
        self._registry = {}
        self._family_registry = {}
        self.logger = logging.getLogger(__name__)

    def register(self, name, family=None):
        def decorator(cls):
            self._registry[name.lower()] = cls
            if family:
                family_lower = family.lower()
                if family_lower not in self._family_registry:
                    self._family_registry[family_lower] = []
                self._family_registry[family_lower].append(name.lower())
            self.logger.debug(f"Registered {name} in {self.__class__.__name__}")
            return cls
        return decorator

    def get(self, name_or_family):
        name_or_family_lower = name_or_family.lower()
        # Direct name lookup
        if name_or_family_lower in self._registry:
            self.logger.debug(f"Retrieved {name_or_family} from {self.__class__.__name__}")
            return self._registry[name_or_family_lower]
        
        # Family name lookup with custom logic to select the correct one
        if name_or_family_lower in self._family_registry:
            self.logger.debug(f"Retrieved {name_or_family} from {self.__class__.__name__}")
            return self.resolve_family(name_or_family_lower)

        return None

    def resolve_family(self, family):
        family_lower = family.lower()
        # Implement the logic to select the correct classifier/scorecard for the family
        # This is a placeholder for the selection logic
        current_names = self._family_registry[family_lower]
        # Placeholder for the logic to select the correct one
        # For example, it could be the most recently added, or based on some versioning
        selected_name = current_names[-1]  # This is just a placeholder
        self.logger.debug(f"Resolved family {family} to {selected_name} in {self.__class__.__name__}")
        return self._registry[selected_name]
    
class ScoreRegistry(BaseRegistry):
    """
    A registry for scores.
    """
    # Inherits all the functionality from BaseRegistry
    # Additional classifier-specific logic can be added here

class ScorecardRegistry(BaseRegistry):
    """
    A registry for scorecards.
    """
    # Inherits all the functionality from BaseRegistry
    # Additional scorecard-specific logic can be added here

# Global Scorecard registry
scorecard_registry = ScorecardRegistry()