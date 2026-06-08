#!/usr/bin/env python3
"""
Fetch real call-center transcripts from HuggingFace for demo purposes.

This downloads transcripts from the AppTek Call-Center Dialogues dataset
and creates items in Plexus for demo/testing.
"""

import os
import sys
import json
from typing import List, Dict
import requests

def fetch_transcripts_from_huggingface(num_samples: int = 10) -> List[Dict]:
    """
    Fetch sample transcripts from the AppTek call-center dataset.

    Args:
        num_samples: Number of transcripts to fetch

    Returns:
        List of transcript dictionaries
    """
    print(f"📥 Fetching {num_samples} sample transcripts from HuggingFace...")

    try:
        from datasets import load_dataset

        # Load the dataset (test split for demo purposes)
        print("   Loading dataset: apptek-com/apptek_callcenter_dialogues...")
        dataset = load_dataset(
            "apptek-com/apptek_callcenter_dialogues",
            split="test",
            streaming=True  # Stream to avoid downloading entire dataset
        )

        transcripts = []
        for i, example in enumerate(dataset):
            if i >= num_samples:
                break

            # The dataset has 'text' field with the transcript
            if 'text' in example and example['text']:
                transcripts.append({
                    'text': example['text'],
                    'metadata': {
                        'source': 'apptek_callcenter_dialogues',
                        'index': i,
                        'id': example.get('id', f'sample-{i}'),
                        'domain': example.get('domain', 'unknown'),
                        'accent': example.get('accent', 'unknown')
                    }
                })
                print(f"   ✓ Fetched transcript {i+1}/{num_samples}")

        print(f"✅ Fetched {len(transcripts)} transcripts")
        return transcripts

    except Exception as e:
        print(f"❌ Error loading from HuggingFace: {e}")
        print("   Falling back to example transcripts...")
        return get_example_transcripts(num_samples)


def get_example_transcripts(num_samples: int = 10) -> List[Dict]:
    """
    Get example transcripts as fallback if HuggingFace fails.
    """
    examples = [
        {
            'text': """Agent: Good afternoon, thank you for calling TechSupport Inc. My name is Sarah, how may I assist you today?

Customer: Hi Sarah, I'm having trouble with my internet connection. It keeps dropping every few minutes.

Agent: I understand how frustrating that must be. Let me help you troubleshoot this. Can you tell me if this started recently or has it been happening for a while?

Customer: It started about two days ago. I haven't changed anything on my end.

Agent: Thank you for that information. Let's start by checking a few things. First, could you please restart your modem by unplugging it for 30 seconds and then plugging it back in?

Customer: Okay, give me a moment... Alright, it's back on now.

Agent: Perfect. While we wait for it to fully reconnect, let me check your account status on our end. I can see your connection has been stable for the past few months until recently. There might be an issue with the local network in your area. Let me run a diagnostic test.

Customer: Okay, thank you.

Agent: The diagnostic shows there's some signal interference. I'm going to schedule a technician to come out and check the line. Would tomorrow between 2-5 PM work for you?

Customer: Yes, that works for me.

Agent: Excellent. I've scheduled the appointment and you'll receive a confirmation email shortly. The technician will call you 30 minutes before arrival. Is there anything else I can help you with today?

Customer: No, that's everything. Thank you for your help, Sarah.

Agent: You're very welcome! Thank you for calling TechSupport Inc. Have a great day!""",
            'metadata': {'source': 'example', 'domain': 'tech_support'}
        },
        {
            'text': """Agent: Thank you for calling BankCorp customer service. This is Michael speaking. How can I help you today?

Customer: Hi, I need to report a fraudulent charge on my credit card.

Agent: I'm sorry to hear that. I'll be happy to help you with this right away. For security purposes, can you please verify your account by providing the last four digits of your card?

Customer: Sure, it's 4729.

Agent: Thank you. I can see your account now. Can you tell me which charge you believe is fraudulent?

Customer: There's a charge for $247 from an online retailer I've never heard of, dated yesterday.

Agent: I see that charge here. I'm going to immediately freeze your card to prevent any additional unauthorized charges. We'll issue you a new card that will arrive in 5-7 business days. I'm also filing a fraud dispute for the $247 charge. You won't be responsible for this amount.

Customer: Oh thank goodness. Will I get that money back?

Agent: Yes, the disputed amount will be credited back to your account within 7-10 business days while we investigate. In the meantime, I'm sending you a confirmation email with a fraud case number. Is there anything else I can help you with?

Customer: No, that covers everything. Thank you so much for your help.

Agent: You're very welcome. We take fraud very seriously and I'm glad we could help protect your account. Have a great day.""",
            'metadata': {'source': 'example', 'domain': 'banking'}
        },
        {
            'text': """Agent: Good morning, Retail Solutions, this is Jennifer. How may I assist you?

Customer: Hi Jennifer, I ordered a laptop from your website two weeks ago and it still hasn't arrived.

Agent: I apologize for the delay. Let me look into this for you right away. Can you please provide your order number?

Customer: Yes, it's RS-447892.

Agent: Thank you. I'm pulling up your order now... I see the issue. It looks like there was a delay at our warehouse due to high volume. Your order is currently in transit and should arrive within the next 2 business days. I sincerely apologize for this delay.

Customer: That's frustrating. I needed it for work this week.

Agent: I completely understand your frustration, and I apologize for the inconvenience this has caused. To make this right, I'm going to upgrade your shipping to overnight at no charge, and I'll also apply a 15% discount to your order. You should receive it by tomorrow afternoon.

Customer: Really? That would be great, thank you.

Agent: Absolutely. I've processed those changes and you'll receive a confirmation email shortly with your updated delivery date and the adjusted total. Is there anything else I can help you with today?

Customer: No, that's perfect. I appreciate you fixing this.

Agent: You're very welcome. Thank you for your patience and for shopping with Retail Solutions. Have a wonderful day!""",
            'metadata': {'source': 'example', 'domain': 'retail'}
        }
    ]

    return examples[:num_samples]


def create_items_in_plexus(transcripts: List[Dict], proxy_url: str, api_key: str, account_id: str) -> List[str]:
    """
    Create items in Plexus from the fetched transcripts.

    Args:
        transcripts: List of transcript dictionaries
        proxy_url: GraphQL proxy URL
        api_key: API key for authentication
        account_id: Account ID for the items

    Returns:
        List of created item IDs
    """
    print(f"\n📤 Creating {len(transcripts)} items in Plexus...")

    item_ids = []

    for i, transcript in enumerate(transcripts):
        mutation = """
        mutation CreateItem($input: CreateItemInput!) {
            createItem(input: $input) {
                id
                accountId
                text
            }
        }
        """

        variables = {
            "input": {
                "accountId": account_id,
                "text": transcript['text'],
                "externalId": f"demo-transcript-{i}-{transcript['metadata'].get('id', i)}",
                "isEvaluation": False,
                "createdByType": "prediction"
            }
        }

        response = requests.post(
            f"{proxy_url}/graphql",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key
            },
            json={
                "query": mutation,
                "variables": variables
            }
        )

        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'createItem' in data['data']:
                item_id = data['data']['createItem']['id']
                item_ids.append(item_id)
                print(f"   ✓ Created item {i+1}/{len(transcripts)}: {item_id}")
                print(f"     Domain: {transcript['metadata'].get('domain', 'unknown')}")
            else:
                print(f"   ✗ Failed to create item {i+1}: {data}")
        else:
            print(f"   ✗ HTTP {response.status_code} for item {i+1}")

    print(f"✅ Created {len(item_ids)} items")
    return item_ids


def save_item_ids(item_ids: List[str], output_file: str = "demo_items.json"):
    """Save the created item IDs to a file for later use."""
    output_path = os.path.join(os.path.dirname(__file__), output_file)

    with open(output_path, 'w') as f:
        json.dump({
            'item_ids': item_ids,
            'created_at': __import__('datetime').datetime.now().isoformat(),
            'count': len(item_ids)
        }, f, indent=2)

    print(f"\n💾 Saved item IDs to: {output_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch demo transcripts and create items in Plexus')
    parser.add_argument('--num-samples', type=int, default=10, help='Number of transcripts to fetch')
    parser.add_argument('--proxy-url', default='http://localhost:8000', help='GraphQL proxy URL')
    parser.add_argument('--api-key', default='local-dev-key', help='API key')
    parser.add_argument('--account-id', default='demo-account', help='Account ID')
    parser.add_argument('--output', default='demo_items.json', help='Output file for item IDs')

    args = parser.parse_args()

    print("🎯 Fetching Demo Transcripts for Kubernetes Testing")
    print("=" * 60)

    # Fetch transcripts
    transcripts = fetch_transcripts_from_huggingface(args.num_samples)

    if not transcripts:
        print("❌ No transcripts fetched")
        return 1

    # Create items in Plexus
    item_ids = create_items_in_plexus(
        transcripts,
        args.proxy_url,
        args.api_key,
        args.account_id
    )

    if not item_ids:
        print("❌ No items created")
        return 1

    # Save item IDs
    save_item_ids(item_ids, args.output)

    print("\n✅ Demo data setup complete!")
    print(f"   {len(item_ids)} items ready for testing")
    print(f"\n💡 Use these items with: ./demo_k8s.sh <score-name>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
