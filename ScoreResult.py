class ScoreResult:
    def __init__(self, *,
            value,
            name=None,
            element_results=None,
            metadata=None,
            decision_tree=None,
            llm_request_history=None,
            error=None):
        self.name = name
        self.value = value
        self.element_results = element_results or []
        self.metadata = metadata or {}
        self.reasoning = []
        self.relevant_quotes = []
        self.decision_tree = decision_tree
        self.llm_request_history = llm_request_history
        self.error = error

    def to_dict(self):
        return {
            'name': self.name,
            'value': self.value,
            'element_results': self.element_results,
            'llm_request_history': self.llm_request_history,
            'metadata': self.metadata,
            'reasoning': self.reasoning,
            'relevant_quotes': self.relevant_quotes,
            'decision_tree': self.decision_tree,
            'error': self.error
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            value=data['value'],
            name=data.get('name'),
            element_results=data.get('element_results', []),
            metadata=data.get('metadata', {}),
            decision_tree=data.get('decision_tree'),
            error=data.get('error')
        )

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
