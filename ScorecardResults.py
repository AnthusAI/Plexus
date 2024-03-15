import json
from decimal import Decimal

class ScorecardResultsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        try:
            return obj.to_dict()
        except AttributeError:
            return super().default(obj)

class ScorecardResults:
    def __init__(self, data=None):
        self.data = data if data is not None else []

    @classmethod
    def load_from_file(cls, file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return cls(data)

    def save_to_file(self, file_path):
        with open(file_path, 'w') as file:
            json.dump(self.data, file, indent=4, cls=ScorecardResultsEncoder)

    def total_costs(self):
        total_cost = 0
        for result in self.data:
            # Assuming each result has a 'cost' field within 'metadata'
            total_cost += Decimal(result.get('metadata', {}).get('total_cost', 0))
        return total_cost

    def find_by_session_id(self, session_id):
        return next((result for result in self.data if result.get('session_id') == session_id), None)

    def average_cost_per_score(self):
        total_cost = self.total_costs()
        num_scores = len(self.data)
        return total_cost / num_scores if num_scores else Decimal('0')
