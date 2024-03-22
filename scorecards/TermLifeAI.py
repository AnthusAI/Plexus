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
        "Ask Doubles Pitch": {},
        "Assumptive Doubles Pitch": {"primary": "Ask Doubles Pitch"},
        "Length of Debt": {},
        "Wrap Up - Carrier Name": {},
        "Wrap Up - Coverage Amount": {},
        "Wrap Up - Exam and Details": {},
        "Wrap Up - Agent Contact Info": {},
        "Wrap Up - Application Underwrite": {}
    }

TermLifeAI.load_and_register_scores()
