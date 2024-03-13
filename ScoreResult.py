class ScoreResult:
    def __init__(self, *, value, name=None, element_results=None, metadata=None, decision_tree=None, error=None):
        self.name = name
        self.value = value
        self.element_results = element_results or []
        self.metadata = metadata or {}
        self.reasoning = []
        self.relevant_quotes = []
        self.decision_tree = decision_tree
        self.error = error

    def __eq__(self, other):
        if isinstance(other, ScoreResult):
            return self.value.lower() == other.value.lower()
        elif isinstance(other, str):
            return self.value.lower() == other.lower()
        return NotImplemented

    def __repr__(self):
        string = f"ScoreResult({self.value})\n"
        if self.element_results:
            string += f", element_results={self.element_results}"
        if self.metadata:
            string += f", metadata={self.metadata}"
        return string
    
    def is_yes(self):
        return self.value.lower() == 'yes'

    def is_no(self):
        return self.value.lower() == 'no'
