#!/usr/bin/env python3
"""
Setup a demo-safe scorecard using public call-center data.

This creates a scorecard via the AppSync GraphQL API that's safe for demos
and testing without using any real client data or scorecards.
"""

import sys
import os
import requests
from pathlib import Path


def load_env_file(env_path: str) -> dict:
    """Load environment variables from .env.local file."""
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                env_vars[key] = value

    return env_vars


def create_demo_scorecard(api_url: str, api_key: str, account_id: str) -> dict:
    """Create a demo scorecard with generic call-center quality scores."""

    print("🎯 Creating demo call-center quality scorecard...")

    # Create the scorecard
    scorecard_mutation = """
    mutation CreateScorecard($input: CreateScorecardInput!) {
        createScorecard(input: $input) {
            id
            key
            name
            accountId
        }
    }
    """

    scorecard_input = {
        "input": {
            "key": "demo_call_center_quality",
            "name": "Demo Call Center Quality",
            "accountId": account_id,
            "description": "Demo-safe scorecard for call-center quality evaluation using public datasets"
        }
    }

    print("   Creating scorecard...")
    response = requests.post(
        api_url,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        json={
            "query": scorecard_mutation,
            "variables": scorecard_input
        }
    )

    if response.status_code != 200:
        print(f"   ❌ Failed to create scorecard: HTTP {response.status_code}")
        print(response.text)
        return None

    data = response.json()
    if 'errors' in data:
        print(f"   ❌ GraphQL errors: {data['errors']}")
        return None

    scorecard = data['data']['createScorecard']
    scorecard_id = scorecard['id']
    print(f"   ✅ Created scorecard: {scorecard['key']} (ID: {scorecard_id})")

    # Create a section for the scores
    section_mutation = """
    mutation CreateSection($input: CreateScorecardSectionInput!) {
        createScorecardSection(input: $input) {
            id
            name
            scorecardId
        }
    }
    """

    section_input = {
        "input": {
            "name": "Call Quality Metrics",
            "order": 1,
            "scorecardId": scorecard_id
        }
    }

    print("   Creating scorecard section...")
    response = requests.post(
        api_url,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        json={
            "query": section_mutation,
            "variables": section_input
        }
    )

    if response.status_code != 200:
        print(f"   ❌ Failed to create section: HTTP {response.status_code}")
        print(response.text)
        return None

    data = response.json()
    if 'errors' in data:
        print(f"   ❌ GraphQL errors: {data['errors']}")
        return None

    section = data['data']['createScorecardSection']
    section_id = section['id']
    print(f"   ✅ Created section: {section['name']} (ID: {section_id})")

    # Define the scores with proper LangGraphScore structure
    scores = [
        {
            "name": "ProfessionalTone",
            "key": "professional-tone",
            "description": "Evaluate if the agent maintained a professional tone throughout the call",
            "class": "LangGraphScore",
            "model_name": "gpt-5.4-nano-2026-03-17",
            "model_provider": "ChatOpenAI",
            "reasoning_effort": "medium",
            "max_tokens": 3000,
            "valid_classes": ["Yes", "No"],
            "system_message": """Objective: Determine whether the agent maintained a professional tone throughout the call.

Valid classes: Yes, No

Core rule for Yes: Mark Yes only if professional throughout the entire call.

What counts as professional:
- Polite greetings and closings
- Respectful language
- Professional vocabulary
- Calm and controlled tone

What does not count as Yes:
- Any slang or casual language
- Showing frustration or impatience
- Dismissive responses
- Any unprofessional tone at any point""",
            "user_message": """Review the transcript and classify whether the agent maintained a professional tone.

Transcript:
{{text}}

Output format (MANDATORY):
1) Provide 2-3 sentences of reasoning
2) Final line must be exactly: Yes or No"""
        },
        {
            "name": "ActiveListening",
            "key": "active-listening",
            "description": "Evaluate if the agent demonstrated active listening skills",
            "class": "LangGraphScore",
            "model_name": "gpt-5.4-nano-2026-03-17",
            "model_provider": "ChatOpenAI",
            "reasoning_effort": "medium",
            "max_tokens": 3000,
            "valid_classes": ["Yes", "No"],
            "system_message": """Objective: Determine whether the agent demonstrated active listening skills.

Valid classes: Yes, No

Core rule for Yes: Mark Yes if multiple indicators of active listening are present.

What counts as active listening:
- Acknowledging customer concerns
- Verbal affirmations ('I understand', 'I see')
- Clarifying questions
- Paraphrasing customer issues
- Not interrupting inappropriately

What does not count as Yes:
- Minimal acknowledgments only ('okay')
- Jumping to solutions without confirming understanding
- Ignoring customer questions
- Frequent interrupting""",
            "user_message": """Review the transcript and classify whether the agent demonstrated active listening.

Transcript:
{{text}}

Output format (MANDATORY):
1) Provide 2-3 sentences of reasoning
2) Final line must be exactly: Yes or No"""
        },
        {
            "name": "ProperCallOpening",
            "key": "proper-call-opening",
            "description": "Evaluate if the agent properly opened the call",
            "class": "LangGraphScore",
            "model_name": "gpt-5.4-nano-2026-03-17",
            "model_provider": "ChatOpenAI",
            "reasoning_effort": "medium",
            "max_tokens": 3000,
            "valid_classes": ["Yes", "No", "NA"],
            "system_message": """Objective: Determine whether the agent properly opened the call.

Valid classes: Yes, No, NA

Core rule for Yes: Mark Yes only if opening includes ALL three elements:
1. A greeting
2. Identification of themselves/company
3. An offer of assistance

NA rule: Mark NA for outbound calls (agent calling customer)

What counts as proper opening:
- 'Good afternoon, thank you for calling TechSupport. My name is Sarah, how may I assist you?'
- All three elements present in opening

What does not count as Yes:
- Missing any of the three elements
- Greeting only without identification
- Unprofessional opening""",
            "user_message": """Review the transcript and classify whether the agent properly opened the call.

Transcript:
{{text}}

Output format (MANDATORY):
1) Provide 2-3 sentences of reasoning
2) Final line must be exactly: Yes, No, or NA"""
        },
        {
            "name": "ProperCallClosing",
            "key": "proper-call-closing",
            "description": "Evaluate if the agent properly closed the call",
            "class": "LangGraphScore",
            "model_name": "gpt-5.4-nano-2026-03-17",
            "model_provider": "ChatOpenAI",
            "reasoning_effort": "medium",
            "max_tokens": 3000,
            "valid_classes": ["Yes", "No"],
            "system_message": """Objective: Determine whether the agent properly closed the call.

Valid classes: Yes, No

Core rule for Yes: Mark Yes if closing includes at least THREE of these four elements:
1. Asking if there's anything else they can help with
2. Summarizing next steps or resolution (when applicable)
3. Thanking the customer
4. Professional goodbye

What counts as proper closing:
- 'Is there anything else I can help you with? Thank you for calling, have a great day!'
- At least 3 of the 4 elements present

What does not count as Yes:
- Abrupt ending with only 'goodbye'
- Missing thanks or offer of additional help
- Only one or two elements present""",
            "user_message": """Review the transcript and classify whether the agent properly closed the call.

Transcript:
{{text}}

Output format (MANDATORY):
1) Provide 2-3 sentences of reasoning
2) Final line must be exactly: Yes or No"""
        },
        {
            "name": "ProblemResolution",
            "key": "problem-resolution",
            "description": "Evaluate how well the agent resolved the customer's issue",
            "class": "LangGraphScore",
            "model_name": "gpt-5.4-nano-2026-03-17",
            "model_provider": "ChatOpenAI",
            "reasoning_effort": "medium",
            "max_tokens": 3000,
            "valid_classes": ["Resolved", "Partially Resolved", "Not Resolved"],
            "system_message": """Objective: Determine how well the agent resolved the customer's issue.

Valid classes: Resolved, Partially Resolved, Not Resolved

Resolved: Issue fully addressed and customer satisfied
Partially Resolved: Some progress but issues remain
Not Resolved: Issue not addressed or customer dissatisfied

Decision process:
1. Identify customer's main issue
2. Trace how agent addressed it
3. Determine if complete solution provided
4. Check customer satisfaction""",
            "user_message": """Review the transcript and classify how well the agent resolved the issue.

Transcript:
{{text}}

Output format (MANDATORY):
1) Provide 2-3 sentences of reasoning
2) Final line must be exactly: Resolved, Partially Resolved, or Not Resolved"""
        }
    ]

    # Create each score
    score_mutation = """
    mutation CreateScore($input: CreateScoreInput!) {
        createScore(input: $input) {
            id
            name
            key
            scorecardId
        }
    }
    """

    score_version_mutation = """
    mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
        createScoreVersion(input: $input) {
            id
            scoreId
            configuration
        }
    }
    """

    import uuid
    import yaml

    created_scores = []
    order = 1
    for score_def in scores:
        print(f"   Creating score: {score_def['name']}...")

        # Create the Score record (metadata only)
        score_input = {
            "input": {
                "scorecardId": scorecard_id,
                "sectionId": section_id,
                "name": score_def['name'],
                "key": score_def['key'],
                "order": order,
                "type": "classification",
                "externalId": f"{score_def['key']}-{uuid.uuid4()}"
            }
        }

        response = requests.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key
            },
            json={
                "query": score_mutation,
                "variables": score_input
            }
        )

        if response.status_code != 200:
            print(f"      ❌ Failed to create score: HTTP {response.status_code}")
            print(response.text)
            continue

        data = response.json()
        if 'errors' in data:
            print(f"      ❌ GraphQL errors creating score: {data['errors']}")
            continue

        score = data['data']['createScore']
        score_id = score['id']
        print(f"      ✅ Created score: {score['key']} (ID: {score_id})")

        # Build the YAML configuration
        graph = [{
            "name": "classifier",
            "class": "Classifier",
            "batch": False,
            "valid_classes": score_def['valid_classes'],
            "system_message": score_def['system_message'],
            "user_message": score_def['user_message'],
            "output": {
                "value": "classification",
                "explanation": "explanation"
            }
        }]

        config_dict = {
            "name": score_def['name'],
            "key": score_def['key'],
            "description": score_def['description'],
            "class": score_def['class'],
            "model_name": score_def['model_name'],
            "model_provider": score_def['model_provider'],
            "reasoning_effort": score_def['reasoning_effort'],
            "max_tokens": score_def['max_tokens'],
            "graph": graph,
            "output": {
                "value": "classification",
                "explanation": "explanation"
            }
        }

        # Convert to YAML string
        config_yaml = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        # Create the ScoreVersion with the configuration
        version_input = {
            "input": {
                "scoreId": score_id,
                "configuration": config_yaml,
                "isFeatured": "true"
            }
        }

        response = requests.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key
            },
            json={
                "query": score_version_mutation,
                "variables": version_input
            }
        )

        if response.status_code != 200:
            print(f"      ❌ Failed to create score version: HTTP {response.status_code}")
            print(response.text)
            continue

        data = response.json()
        if 'errors' in data:
            print(f"      ❌ GraphQL errors creating version: {data['errors']}")
            continue

        version = data['data']['createScoreVersion']
        print(f"      ✅ Created score version (ID: {version['id']})")

        created_scores.append(score)
        order += 1

    return {
        'scorecard': scorecard,
        'scores': created_scores
    }


def main():
    """Create and upload the demo scorecard."""
    import argparse

    parser = argparse.ArgumentParser(description='Setup demo scorecard in AppSync')
    parser.add_argument('--api-url', help='AppSync GraphQL URL (or set in dashboard/.env.local)')
    parser.add_argument('--api-key', help='API key (or set in dashboard/.env.local)')
    parser.add_argument('--account-id', help='Account ID (or use PLEXUS_ACCOUNT_UUID from .env.local)')

    args = parser.parse_args()

    # Load from dashboard/.env.local if not provided
    env_path = Path(__file__).parent.parent.parent / 'dashboard' / '.env.local'
    env_vars = load_env_file(str(env_path))

    api_url = args.api_url or env_vars.get('PLEXUS_API_URL') or env_vars.get('VITE_PLEXUS_API_URL')
    api_key = args.api_key or env_vars.get('PLEXUS_API_KEY') or env_vars.get('VITE_PLEXUS_API_KEY')
    account_id = args.account_id or env_vars.get('PLEXUS_ACCOUNT_UUID')

    if not api_url or not api_key:
        print("❌ Error: API URL and API Key required")
        print("   Either set them in dashboard/.env.local or pass as arguments:")
        print("   --api-url <url> --api-key <key>")
        return 1

    if not account_id:
        print("❌ Error: Account ID required")
        print("   Either set PLEXUS_ACCOUNT_UUID in dashboard/.env.local or pass --account-id")
        return 1

    print("🎯 Setting Up Demo Call-Center Quality Scorecard")
    print("=" * 60)
    print(f"   API URL: {api_url}")
    print(f"   Account: {account_id}")
    print()

    result = create_demo_scorecard(api_url, api_key, account_id)

    if not result:
        print("\n❌ Failed to create scorecard")
        return 1

    print("\n✅ Demo scorecard setup complete!")
    print(f"   Scorecard: {result['scorecard']['key']}")
    print(f"   Scores: {len(result['scores'])}")
    for score in result['scores']:
        print(f"   - {score['name']}")

    print(f"\n💡 You can now use scorecard '{result['scorecard']['key']}' for demos")
    print(f"   Example: ./demo_k8s.sh ProfessionalTone")

    return 0


if __name__ == "__main__":
    sys.exit(main())
