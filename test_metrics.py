import json
from datetime import datetime, timezone

class TestEval:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc)
        self.experiment_id = 'test-id'
        self.processed_items = 40
        self.number_of_texts_to_sample = 100
        
    def _get_update_variables(self, metrics, status):
        metrics_for_api = []
        if metrics.get('accuracy') is not None:
            metrics_for_api.append({'name': 'Accuracy', 'value': metrics['accuracy'] * 100})
        if metrics.get('precision') is not None:
            metrics_for_api.append({'name': 'Precision', 'value': metrics['precision'] * 100})
        if metrics.get('alignment') is not None:
            alignment_value = metrics['alignment']
            display_value = alignment_value * 100 if alignment_value >= 0 else 0
            metrics_for_api.append({'name': 'Alignment', 'value': display_value})
        if metrics.get('specificity') is not None:
            metrics_for_api.append({'name': 'Specificity', 'value': metrics['specificity'] * 100})
        
        update_input = {
            'id': self.experiment_id,
            'status': status,
            'accuracy': metrics['accuracy'] * 100,
            'processedItems': self.processed_items,
            'metrics': json.dumps(metrics_for_api)
        }
        return {'input': update_input}

# Test with positive alignment value
metrics = {
    'accuracy': 0.95, 
    'precision': 0.96, 
    'alignment': 0.85, 
    'specificity': 0.87
}
test = TestEval()
result = test._get_update_variables(metrics, 'RUNNING')
print(f'Metrics in API request: {result["input"].get("metrics")}')

# Test with negative alignment value
metrics['alignment'] = -0.3
result = test._get_update_variables(metrics, 'RUNNING')
print(f'Metrics with negative alignment: {result["input"].get("metrics")}') 