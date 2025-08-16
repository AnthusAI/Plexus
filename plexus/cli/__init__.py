# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'scorecards':
        from plexus.cli.scorecard.scorecards import scorecards
        return scorecards
    elif name == 'scores':
        from plexus.cli.score.scores import scores
        return scores
    elif name == 'score':
        from plexus.cli.score.scores import score
        return score
    elif name == 'results':
        from plexus.cli.result.results import results
        return results
    elif name == 'feedback':
        from plexus.cli.feedback.commands import feedback
        return feedback
    elif name == 'tasks':
        from plexus.cli.task.tasks import tasks
        return tasks
    elif name == 'task':
        from plexus.cli.task.tasks import task
        return task
    elif name == 'items':
        from plexus.cli.item.items import items
        return items
    elif name == 'item':
        from plexus.cli.item.items import item
        return item
    elif name == 'iterative_config_fetching':
        from plexus.cli.shared import iterative_config_fetching
        return iterative_config_fetching
    elif name == 'memoized_resolvers':
        from plexus.cli.shared import memoized_resolvers
        return memoized_resolvers
    elif name == 'experiment':
        from plexus.cli.experiment.experiments import experiment
        return experiment
    else:
        raise AttributeError(f"module 'plexus.cli' has no attribute '{name}'")

__all__ = ['scorecards', 'scores', 'score', 'results', 'feedback', 'tasks', 'task', 'items', 'item', 'iterative_config_fetching', 'memoized_resolvers', 'experiment']
