import logging

class Registry:
    def __init__(self):
        self._classes_by_id = {}
        self._classes_by_key = {}
        self._classes_by_name = {}
        self._properties_by_id = {}
        self._properties_by_key = {}
        self._properties_by_name = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, cls, properties, id=None, key=None, name=None):
        if not any([id, key, name]):
            raise ValueError("At least one of id, key, or name must be provided")

        if id is not None:
            id = str(id)
            self._classes_by_id[id] = cls
            self._properties_by_id[id] = properties
        if key is not None:
            key = key.lower()
            self._classes_by_key[key] = cls
            self._properties_by_key[key] = properties
        if name is not None:
            name = name.lower()
            self._classes_by_name[name] = cls
            self._properties_by_name[name] = properties

        class_name = cls.__name__ if hasattr(cls, '__name__') else str(cls)
        identifiers = [f"{k}={v}" for k, v in {'id': id, 'key': key, 'name': name}.items() if v is not None]
        self.logger.debug(f"Registered {class_name} with {', '.join(identifiers)}")

    def get(self, identifier):
        identifier = str(identifier).lower() if identifier is not None else None
        return (self._classes_by_id.get(identifier) or
                self._classes_by_key.get(identifier) or
                self._classes_by_name.get(identifier))

    def get_properties(self, identifier):
        identifier = str(identifier).lower() if identifier is not None else None
        return (self._properties_by_id.get(identifier) or
                self._properties_by_key.get(identifier) or
                self._properties_by_name.get(identifier))

    def __contains__(self, identifier):
        return bool(self.get(identifier))

class ScorecardRegistry(Registry):
    pass

class ScoreRegistry(Registry):
    pass

scorecard_registry = ScorecardRegistry()