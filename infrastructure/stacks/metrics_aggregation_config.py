METRICS_TABLE_TYPES = ['item', 'scoreresult', 'task', 'evaluation', 'procedure']

METRICS_STREAM_CONFIGS = {
    'item': {'batch_size': 10, 'batch_window': 15},
    'scoreresult': {'batch_size': 100, 'batch_window': 15},
    'task': {'batch_size': 1, 'batch_window': 15},
    'evaluation': {'batch_size': 1, 'batch_window': 15},
    'procedure': {'batch_size': 1, 'batch_window': 15},
}
