from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry

@scorecard_registry.register('term-life-ai', family='term-life-ai')
class TermLifeAI(Scorecard):
    """
    A scorecard for the TermLifeAI model.
    """

    @classmethod
    def name(cls):
        return "SelectQuote Term Life AI 3.0"

    scorecard_folder_path = "scorecards/TermLifeAI"

    scores = {
        "Dependents": {},
        "Debt Amount": {},
        "Spouse/Partner Income": {},
        "PI Income": {},
        "Free/Independent/Impartial": {},
        "Carrier Access": {},
        "Competitive Advantage": {},
        "Carrier Highlights/Rationale": {},
        "Existing Insurance": {},
        "Term Explanation": {},
        "Temperature Check": {},
        "Apples to Apples": {},
        "Self Endorsement": {},
        "Assumptive Close": {},
        "Total loss to family": {},
        "Solution Fit": {},
        # "Ask Doubles Pitch": {},
        # "Assumptive Doubles Pitch": {"primary": "Ask Doubles Pitch"},
        "Length of Debt": {},
        "Wrap Up - Carrier Name": {},
        "Wrap Up - Coverage Amount": {},
        "Wrap Up - Exam and Details": {},
        "Wrap Up - Agent Contact Info": {},
        "Wrap Up - Application Underwrite": {}
    }

    @classmethod
    def score_names(cls):
        """
        The list of scores in the whole scorecard.
        """
        return cls.scores.keys()

    @classmethod
    def score_names_to_process(cls):
        """
        Some scores are comuted implicitly by other scores and don't need to be directly processed.
        """
        return [
            score_name for score_name, details in cls.scores.items()
            if not details.get('primary')
        ]

TermLifeAI.load_and_register_scores()
