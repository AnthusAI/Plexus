#!/usr/bin/env python3
"""
Test script for CloudWatch Logs PII masking.

Creates a test log group, logs messages with known PII patterns,
and verifies that the data protection policy is applied.

Usage:
    python scripts/test_pii_masking.py
"""

import json
import time
from plexus.logging.cloudwatch_logger import PlexusCloudWatchLogger

def main():
    print("Testing CloudWatch Logs PII masking...")
    print("=" * 60)

    # Create a test logger
    logger = PlexusCloudWatchLogger(
        account_key="test-pii-masking",
        component_name="test/pii",
        invocation_id=f"test-{int(time.time())}",
        log_category="test"
    )

    print(f"\nLog group: {logger.log_group}")
    print(f"Run stream: {logger._run_stream}")
    print(f"LLM context stream: {logger._llm_stream}")

    # Open the logger (creates log group and applies data protection policy)
    logger.open()
    print("\n✓ Log group created and data protection policy applied")

    # Test messages with PII that should be masked
    test_cases = [
        {
            "name": "Email address",
            "message": "User email is john.doe@example.com",
            "expected_mask": "***@***.***"
        },
        {
            "name": "Phone number",
            "message": "Contact: 555-123-4567",
            "expected_mask": "***-***-****"
        },
        {
            "name": "SSN",
            "message": "SSN: 123-45-6789",
            "expected_mask": "***-**-****"
        },
        {
            "name": "Credit card",
            "message": "Card: 4532-1234-5678-9010",
            "expected_mask": "****-****-****-****"
        },
        {
            "name": "AWS Secret Key",
            "message": "Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "expected_mask": "***"
        },
        {
            "name": "Normal message (no PII)",
            "message": "Processing evaluation for score quality-check",
            "expected_mask": "No masking expected"
        }
    ]

    print("\nLogging test messages...")
    print("-" * 60)

    for test in test_cases:
        payload = {
            "test_case": test["name"],
            "message": test["message"],
            "timestamp": time.time()
        }
        logger.log_llm_context(payload)
        print(f"✓ Logged: {test['name']}")
        print(f"  Original: {test['message']}")
        print(f"  Expected: {test['expected_mask']}")
        time.sleep(0.1)  # Small delay to ensure log ordering

    logger.close()
    print("\n✓ Logger closed")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("\nTo verify masking:")
    print(f"1. Go to CloudWatch Logs console")
    print(f"2. Navigate to log group: {logger.log_group}")
    print(f"3. Open log stream: {logger._llm_stream}")
    print(f"4. Verify that PII is masked with asterisks")
    print("\nNote: It may take a few seconds for logs to appear in CloudWatch.")
    print("=" * 60)

if __name__ == "__main__":
    main()
