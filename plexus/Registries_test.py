import unittest

from plexus.Registries import Registry, ScoreRegistry, ScorecardRegistry

class MockScore:
    pass

class MockScorecard:
    pass

class TestRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = Registry()

    def test_register_and_get(self):
        self.registry.register(MockScore, {}, name='MockScore')
        result = self.registry.get('MockScore')
        self.assertIs(result, MockScore)

    def test_get_nonexistent(self):
        result = self.registry.get('Nonexistent')
        self.assertIsNone(result)

    def test_get_properties(self):
        properties = {'key': 'value'}
        self.registry.register(MockScore, properties, name='MockScore')
        result = self.registry.get_properties('MockScore')
        self.assertEqual(result, properties)

class TestScoreRegistry(unittest.TestCase):

    def setUp(self):
        self.score_registry = ScoreRegistry()

    def test_register_and_get_score(self):
        self.score_registry.register(MockScore, {}, name='MockScore')
        result = self.score_registry.get('MockScore')
        self.assertIs(result, MockScore)

class TestScorecardRegistry(unittest.TestCase):

    def setUp(self):
        self.scorecard_registry = ScorecardRegistry()

    def test_register_and_get_scorecard(self):
        self.scorecard_registry.register(MockScorecard, {}, name='MockScorecard')
        result = self.scorecard_registry.get('MockScorecard')
        self.assertIs(result, MockScorecard)

if __name__ == '__main__':
    unittest.main()