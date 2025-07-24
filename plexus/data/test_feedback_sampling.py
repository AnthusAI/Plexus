#!/usr/bin/env python3
"""
Test cases for FeedbackItems sampling logic.
Tests the different scenarios for prioritizing items with edit comments.
"""

import unittest
from unittest.mock import Mock
from typing import List

# Mock FeedbackItem class for testing
class MockFeedbackItem:
    """Mock FeedbackItem for testing purposes."""
    
    def __init__(self, item_id: str, initial_value: str, final_value: str, 
                 edit_comment: str = None, **kwargs):
        self.itemId = item_id
        self.initialAnswerValue = initial_value
        self.finalAnswerValue = final_value
        self.editCommentValue = edit_comment
        # Add other attributes with defaults
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        # Set default attributes
        if not hasattr(self, 'scorecardId'):
            self.scorecardId = 'test-scorecard'
        if not hasattr(self, 'scoreId'):
            self.scoreId = 'test-score'
        if not hasattr(self, 'accountId'):
            self.accountId = 'test-account'
        if not hasattr(self, 'createdAt'):
            self.createdAt = '2024-01-01T00:00:00Z'
        if not hasattr(self, 'updatedAt'):
            self.updatedAt = '2024-01-01T00:00:00Z'
        if not hasattr(self, 'editedAt'):
            self.editedAt = None
        if not hasattr(self, 'editorName'):
            self.editorName = None
        if not hasattr(self, 'isAgreement'):
            self.isAgreement = None
        if not hasattr(self, 'cacheKey'):
            self.cacheKey = None
        if not hasattr(self, 'initialCommentValue'):
            self.initialCommentValue = None
        if not hasattr(self, 'finalCommentValue'):
            self.finalCommentValue = None
        if not hasattr(self, 'item'):
            self.item = None

# Mock FeedbackItems class for testing just the sampling method
class MockFeedbackItems:
    """Mock FeedbackItems class with just the sampling method for testing."""
    
    def _prioritize_items_with_edit_comments(self, items: List[MockFeedbackItem], limit: int) -> List[MockFeedbackItem]:
        """
        Prioritize items with edit comments when applying a limit.
        
        Rules:
        1. If there are fewer items than the limit, take them all
        2. If there are more than the limit, prioritize ones with edit comments
        3. If still more than limit after including all with edit comments, 
           randomly sample from the items with edit comments
        """
        import random
        
        # Rule 1: If fewer items than limit, take them all
        if len(items) <= limit:
            return items
        
        # Separate items with and without edit comments
        items_with_comments = [item for item in items if item.editCommentValue]
        items_without_comments = [item for item in items if not item.editCommentValue]
        
        # Rule 2: Prioritize items with edit comments
        if len(items_with_comments) <= limit:
            # We can fit all items with comments, plus some without comments
            result = items_with_comments.copy()
            remaining_slots = limit - len(items_with_comments)
            
            if remaining_slots > 0 and items_without_comments:
                # Randomly sample from items without comments to fill remaining slots
                random.shuffle(items_without_comments)
                result.extend(items_without_comments[:remaining_slots])
            
            return result
        else:
            # Rule 3: More items with comments than limit - randomly sample from them
            random.shuffle(items_with_comments)
            return items_with_comments[:limit]


class TestFeedbackItemsSampling(unittest.TestCase):
    """Test cases for FeedbackItems sampling logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.feedback_items = MockFeedbackItems()
        # Set random seed for reproducible tests
        import random
        random.seed(42)
    
    def test_scenario_1_fewer_items_than_limit(self):
        """
        Test Scenario 1: If there are fewer items than the limit, take them all.
        """
        print("\n--- Testing Scenario 1: Fewer items than limit ---")
        
        # Create 5 items (3 with comments, 2 without)
        items = [
            MockFeedbackItem("1", "Yes", "Yes", "Good call"),
            MockFeedbackItem("2", "No", "Yes", "Actually yes"),
            MockFeedbackItem("3", "Yes", "No", "Actually no"),
            MockFeedbackItem("4", "Yes", "Yes"),  # No comment
            MockFeedbackItem("5", "No", "No"),   # No comment
        ]
        
        # Limit is 10 (more than available items)
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=10)
        
        # Should return all 5 items
        self.assertEqual(len(result), 5)
        print(f"✓ With 5 items and limit=10, returned all {len(result)} items")
        
        # Verify all original items are included
        result_ids = {item.itemId for item in result}
        expected_ids = {"1", "2", "3", "4", "5"}
        self.assertEqual(result_ids, expected_ids)
        print("✓ All original items are included")
    
    def test_scenario_2_prioritize_edit_comments_with_room_for_others(self):
        """
        Test Scenario 2: More items than limit, but can fit all with edit comments plus some without.
        """
        print("\n--- Testing Scenario 2: Prioritize edit comments with room for others ---")
        
        # Create 8 items (3 with comments, 5 without)
        items = [
            MockFeedbackItem("1", "Yes", "Yes", "Good call"),
            MockFeedbackItem("2", "No", "Yes", "Actually yes"),
            MockFeedbackItem("3", "Yes", "No", "Actually no"),
            MockFeedbackItem("4", "Yes", "Yes"),  # No comment
            MockFeedbackItem("5", "No", "No"),   # No comment
            MockFeedbackItem("6", "Yes", "Yes"),  # No comment
            MockFeedbackItem("7", "No", "No"),   # No comment
            MockFeedbackItem("8", "Yes", "No"),  # No comment
        ]
        
        # Limit is 6
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=6)
        
        # Should return 6 items
        self.assertEqual(len(result), 6)
        print(f"✓ With 8 items and limit=6, returned {len(result)} items")
        
        # All 3 items with comments should be included
        items_with_comments = [item for item in result if item.editCommentValue]
        self.assertEqual(len(items_with_comments), 3)
        print("✓ All 3 items with edit comments are included")
        
        # Should have 3 items without comments (to fill remaining slots)
        items_without_comments = [item for item in result if not item.editCommentValue]
        self.assertEqual(len(items_without_comments), 3)
        print("✓ Filled remaining 3 slots with items without comments")
        
        # Verify all items with comments are included
        comment_ids = {item.itemId for item in items_with_comments}
        expected_comment_ids = {"1", "2", "3"}
        self.assertEqual(comment_ids, expected_comment_ids)
        print("✓ Correct items with comments are included")
    
    def test_scenario_3_more_items_with_comments_than_limit(self):
        """
        Test Scenario 3: More items with edit comments than the limit - randomly sample from them.
        """
        print("\n--- Testing Scenario 3: More items with comments than limit ---")
        
        # Create 10 items (7 with comments, 3 without)
        items = [
            MockFeedbackItem("1", "Yes", "Yes", "Good call"),
            MockFeedbackItem("2", "No", "Yes", "Actually yes"),
            MockFeedbackItem("3", "Yes", "No", "Actually no"),
            MockFeedbackItem("4", "Yes", "Yes", "Correct"),
            MockFeedbackItem("5", "No", "No", "Correct"),
            MockFeedbackItem("6", "Yes", "No", "Wrong"),
            MockFeedbackItem("7", "No", "Yes", "Should be yes"),
            MockFeedbackItem("8", "Yes", "Yes"),  # No comment
            MockFeedbackItem("9", "No", "No"),   # No comment
            MockFeedbackItem("10", "Yes", "No"), # No comment
        ]
        
        # Limit is 5 (less than the 7 items with comments)
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=5)
        
        # Should return exactly 5 items
        self.assertEqual(len(result), 5)
        print(f"✓ With 10 items (7 with comments) and limit=5, returned {len(result)} items")
        
        # All returned items should have comments
        all_have_comments = all(item.editCommentValue for item in result)
        self.assertTrue(all_have_comments)
        print("✓ All returned items have edit comments")
        
        # Should be a subset of the original items with comments
        result_ids = {item.itemId for item in result}
        comment_item_ids = {"1", "2", "3", "4", "5", "6", "7"}
        self.assertTrue(result_ids.issubset(comment_item_ids))
        print("✓ All returned items are from the original items with comments")
    
    def test_scenario_4_no_items_with_comments(self):
        """
        Test Scenario 4: No items have edit comments - randomly sample from all.
        """
        print("\n--- Testing Scenario 4: No items with comments ---")
        
        # Create 6 items, none with comments
        items = [
            MockFeedbackItem("1", "Yes", "Yes"),
            MockFeedbackItem("2", "No", "Yes"),
            MockFeedbackItem("3", "Yes", "No"),
            MockFeedbackItem("4", "Yes", "Yes"),
            MockFeedbackItem("5", "No", "No"),
            MockFeedbackItem("6", "Yes", "No"),
        ]
        
        # Limit is 4
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=4)
        
        # Should return 4 items
        self.assertEqual(len(result), 4)
        print(f"✓ With 6 items (none with comments) and limit=4, returned {len(result)} items")
        
        # None should have comments (as expected)
        any_have_comments = any(item.editCommentValue for item in result)
        self.assertFalse(any_have_comments)
        print("✓ No returned items have edit comments (as expected)")
        
        # Should be a subset of original items
        result_ids = {item.itemId for item in result}
        original_ids = {"1", "2", "3", "4", "5", "6"}
        self.assertTrue(result_ids.issubset(original_ids))
        print("✓ All returned items are from the original items")
    
    def test_scenario_5_all_items_have_comments(self):
        """
        Test Scenario 5: All items have edit comments - randomly sample from all.
        """
        print("\n--- Testing Scenario 5: All items have comments ---")
        
        # Create 6 items, all with comments
        items = [
            MockFeedbackItem("1", "Yes", "Yes", "Good call"),
            MockFeedbackItem("2", "No", "Yes", "Actually yes"),
            MockFeedbackItem("3", "Yes", "No", "Actually no"),
            MockFeedbackItem("4", "Yes", "Yes", "Correct"),
            MockFeedbackItem("5", "No", "No", "Correct"),
            MockFeedbackItem("6", "Yes", "No", "Wrong"),
        ]
        
        # Limit is 4
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=4)
        
        # Should return 4 items
        self.assertEqual(len(result), 4)
        print(f"✓ With 6 items (all with comments) and limit=4, returned {len(result)} items")
        
        # All should have comments
        all_have_comments = all(item.editCommentValue for item in result)
        self.assertTrue(all_have_comments)
        print("✓ All returned items have edit comments")
        
        # Should be a subset of original items
        result_ids = {item.itemId for item in result}
        original_ids = {"1", "2", "3", "4", "5", "6"}
        self.assertTrue(result_ids.issubset(original_ids))
        print("✓ All returned items are from the original items")
    
    def test_edge_case_limit_zero(self):
        """
        Test Edge Case: Limit is zero.
        """
        print("\n--- Testing Edge Case: Limit is zero ---")
        
        items = [
            MockFeedbackItem("1", "Yes", "Yes", "Good call"),
            MockFeedbackItem("2", "No", "Yes"),
        ]
        
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=0)
        
        # Should return empty list
        self.assertEqual(len(result), 0)
        print("✓ With limit=0, returned empty list")
    
    def test_edge_case_empty_items(self):
        """
        Test Edge Case: No items provided.
        """
        print("\n--- Testing Edge Case: Empty items list ---")
        
        items = []
        
        result = self.feedback_items._prioritize_items_with_edit_comments(items, limit=5)
        
        # Should return empty list
        self.assertEqual(len(result), 0)
        print("✓ With empty items list, returned empty list")


def main():
    """Run all test cases."""
    print("Testing FeedbackItems Sampling Logic")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFeedbackItemsSampling)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=0, stream=open('/dev/null', 'w'))
    result = runner.run(suite)
    
    # Run individual tests with our custom output
    test_instance = TestFeedbackItemsSampling()
    test_instance.setUp()
    
    try:
        test_instance.test_scenario_1_fewer_items_than_limit()
        test_instance.test_scenario_2_prioritize_edit_comments_with_room_for_others()
        test_instance.test_scenario_3_more_items_with_comments_than_limit()
        test_instance.test_scenario_4_no_items_with_comments()
        test_instance.test_scenario_5_all_items_have_comments()
        test_instance.test_edge_case_limit_zero()
        test_instance.test_edge_case_empty_items()
        
        print(f"\n{'='*50}")
        print("✓ All sampling tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n{'='*50}")
        print(f"✗ Test failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())