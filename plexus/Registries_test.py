import unittest

from plexus.Registries import BaseRegistry, ScoreRegistry, ScorecardRegistry

class MockScore:
    pass

class MockScorecard:
    pass

class TestBaseRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = BaseRegistry()

    def test_register_and_get(self):
        self.registry.register('MockScore')(MockScore)
        result = self.registry.get('MockScore')
        self.assertIs(result, MockScore)

    def test_register_family_and_resolve(self):
        self.registry.register('MockScore', family='MockFamily')(MockScore)
        result = self.registry.resolve_family('MockFamily')
        self.assertIs(result, MockScore)

    def test_get_nonexistent(self):
        result = self.registry.get('Nonexistent')
        self.assertIsNone(result)

class TestScoreRegistry(unittest.TestCase):

    def setUp(self):
        self.score_registry = ScoreRegistry()

    def test_register_and_get_score(self):
        self.score_registry.register('MockScore')(MockScore)
        result = self.score_registry.get('MockScore')
        self.assertIs(result, MockScore)

class TestScorecardRegistry(unittest.TestCase):

    def setUp(self):
        self.scorecard_registry = ScorecardRegistry()

    def test_register_and_get_scorecard(self):
        self.scorecard_registry.register('MockScorecard')(MockScorecard)
        result = self.scorecard_registry.get('MockScorecard')
        self.assertIs(result, MockScorecard)

if __name__ == '__main__':
    unittest.main()