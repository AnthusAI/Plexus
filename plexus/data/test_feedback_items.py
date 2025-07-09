#!/usr/bin/env python3
"""
Simple test script for FeedbackItems data cache.
This script validates that the class can be instantiated and parameters are validated correctly.
"""

import sys
import logging
from pydantic import ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    from FeedbackItems import FeedbackItems
    print("✓ Successfully imported FeedbackItems class")
except ImportError as e:
    print(f"✗ Failed to import FeedbackItems: {e}")
    sys.exit(1)

def test_parameter_validation():
    """Test parameter validation."""
    print("\n--- Testing Parameter Validation ---")
    
    # Test valid parameters
    try:
        valid_params = {
            'scorecard': 'test-scorecard',
            'score': 'test-score',
            'days': 14,
            'limit': 200,
            'limit_per_cell': 100
        }
        feedback_items = FeedbackItems(**valid_params)
        print("✓ Valid parameters accepted")
    except Exception as e:
        print(f"✗ Valid parameters rejected: {e}")
        return False
    
    # Test missing required parameters
    try:
        missing_params = {
            'scorecard': 'test-scorecard',
            # 'score' is missing
            'days': 14
        }
        FeedbackItems(**missing_params)
        print("✗ Missing required parameters should have been rejected")
        return False
    except ValidationError:
        print("✓ Missing required parameters correctly rejected")
    except Exception as e:
        print(f"✗ Unexpected error with missing parameters: {e}")
        return False
    
    # Test invalid days (negative)
    try:
        invalid_days = {
            'scorecard': 'test-scorecard',
            'score': 'test-score',
            'days': -1
        }
        FeedbackItems(**invalid_days)
        print("✗ Negative days should have been rejected")
        return False
    except ValidationError:
        print("✓ Negative days correctly rejected")
    except Exception as e:
        print(f"✗ Unexpected error with negative days: {e}")
        return False
    
    # Test invalid limit (zero)
    try:
        invalid_limit = {
            'scorecard': 'test-scorecard',
            'score': 'test-score',
            'days': 14,
            'limit': 0
        }
        FeedbackItems(**invalid_limit)
        print("✗ Zero limit should have been rejected")
        return False
    except ValidationError:
        print("✓ Zero limit correctly rejected")
    except Exception as e:
        print(f"✗ Unexpected error with zero limit: {e}")
        return False
    
    return True

def test_cache_methods():
    """Test cache-related methods."""
    print("\n--- Testing Cache Methods ---")
    
    try:
        params = {
            'scorecard': 'test-scorecard',
            'score': 'test-score', 
            'days': 14,
            'limit': 200,
            'limit_per_cell': 100
        }
        feedback_items = FeedbackItems(**params)
        
        # Test cache identifier generation
        identifier = feedback_items._generate_cache_identifier('sc123', 'score456')
        print(f"✓ Cache identifier generated: {identifier}")
        
        # Test cache file path generation
        cache_path = feedback_items._get_cache_file_path(identifier)
        print(f"✓ Cache file path generated: {cache_path}")
        
        # Test cache existence check (should be False for new identifier)
        exists = feedback_items._cache_exists(identifier)
        print(f"✓ Cache existence check: {exists}")
        
        return True
    except Exception as e:
        print(f"✗ Cache methods failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing FeedbackItems Data Cache Implementation")
    print("=" * 50)
    
    success = True
    
    # Test parameter validation
    if not test_parameter_validation():
        success = False
    
    # Test cache methods
    if not test_cache_methods():
        success = False
    
    print(f"\n{'='*50}")
    if success:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())