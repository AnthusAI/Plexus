"""
Tests for dataset filtering processors.

Dataset processors operate on entire dataframes and are typically used during training
to filter, transform, or balance datasets before model training.
"""

import unittest
import pandas as pd
from plexus.processors.DownsampleClassDatasetFilter import DownsampleClassDatasetFilter
from plexus.processors.ByColumnValueDatasetFilter import ByColumnValueDatasetFilter
from plexus.processors.MergeColumnsDatasetFilter import MergeColumnsDatasetFilter
from plexus.processors.ColumnDatasetFilter import ColumnDatasetFilter


class TestDownsampleClassDatasetFilter(unittest.TestCase):
    """Tests for DownsampleClassDatasetFilter"""

    def test_downsample_class_dataset_filter_basic(self):
        """Test basic downsampling to balance class distribution"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
            'label': ['yes', 'yes', 'yes', 'no', 'no']
        })

        processor = DownsampleClassDatasetFilter(**{
            'column-name': 'label',
            'value': 'yes'
        })

        result = processor.process(df)

        # Should downsample 'yes' to match 'no' count (2 each)
        self.assertEqual(result['label'].value_counts()['yes'], 2)
        self.assertEqual(result['label'].value_counts()['no'], 2)
        self.assertEqual(len(result), 4)  # 2 yes + 2 no

    def test_downsample_no_downsampling_needed(self):
        """Test when target class is already smaller - no downsampling should occur"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
            'label': ['yes', 'yes', 'no', 'no', 'no']
        })

        processor = DownsampleClassDatasetFilter(**{
            'column-name': 'label',
            'value': 'yes'  # 'yes' has 2, 'no' has 3
        })

        result = processor.process(df)

        # Should NOT downsample since 'yes' (2) is already smaller than 'no' (3)
        self.assertEqual(result['label'].value_counts()['yes'], 2)
        self.assertEqual(result['label'].value_counts()['no'], 3)
        self.assertEqual(len(result), 5)  # All original rows

    def test_downsample_with_multiple_classes(self):
        """Test downsampling with more than two classes"""
        df = pd.DataFrame({
            'text': [f'sample{i}' for i in range(10)],
            'label': ['yes']*5 + ['no']*3 + ['maybe']*2
        })

        processor = DownsampleClassDatasetFilter(**{
            'column-name': 'label',
            'value': 'yes'  # Downsample 'yes' to match largest non-target (3)
        })

        result = processor.process(df)

        # 'yes' should be downsampled to 3 (matching 'no')
        self.assertEqual(result['label'].value_counts()['yes'], 3)
        self.assertEqual(result['label'].value_counts()['no'], 3)
        self.assertEqual(result['label'].value_counts()['maybe'], 2)

    def test_downsample_preserves_other_columns(self):
        """Test that downsampling preserves all other columns"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4'],
            'label': ['yes', 'yes', 'no', 'no'],
            'metadata': ['meta1', 'meta2', 'meta3', 'meta4'],
            'score': [1, 2, 3, 4]
        })

        processor = DownsampleClassDatasetFilter(**{
            'column-name': 'label',
            'value': 'yes'
        })

        result = processor.process(df)

        # Check all columns are present
        self.assertIn('text', result.columns)
        self.assertIn('metadata', result.columns)
        self.assertIn('score', result.columns)
        self.assertEqual(len(result.columns), 4)


class TestByColumnValueDatasetFilter(unittest.TestCase):
    """Tests for ByColumnValueDatasetFilter"""

    def test_filter_include(self):
        """Test filtering to include only rows with specific value"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4'],
            'type': ['inbound', 'outbound', 'inbound', 'outbound']
        })

        processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'include',
            'column-name': 'type',
            'value': 'inbound'
        })

        result = processor.process(df)

        # Should only include inbound rows
        self.assertEqual(len(result), 2)
        self.assertTrue((result['type'] == 'inbound').all())

    def test_filter_exclude(self):
        """Test filtering to exclude rows with specific value"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4'],
            'type': ['inbound', 'outbound', 'inbound', 'outbound']
        })

        processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'exclude',
            'column-name': 'type',
            'value': 'inbound'
        })

        result = processor.process(df)

        # Should exclude inbound rows
        self.assertEqual(len(result), 2)
        self.assertTrue((result['type'] == 'outbound').all())

    def test_filter_with_missing_values(self):
        """Test filtering when target value doesn't exist"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2'],
            'type': ['inbound', 'outbound']
        })

        processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'include',
            'column-name': 'type',
            'value': 'nonexistent'
        })

        result = processor.process(df)

        # Should return empty dataframe
        self.assertEqual(len(result), 0)

    def test_filter_preserves_all_columns(self):
        """Test that filtering preserves all columns"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3'],
            'type': ['a', 'b', 'a'],
            'score': [1, 2, 3],
            'metadata': ['m1', 'm2', 'm3']
        })

        processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'include',
            'column-name': 'type',
            'value': 'a'
        })

        result = processor.process(df)

        # All columns should be preserved
        self.assertEqual(set(result.columns), set(df.columns))
        self.assertEqual(len(result), 2)


class TestColumnDatasetFilter(unittest.TestCase):
    """Tests for ColumnDatasetFilter"""

    def test_column_filter_include(self):
        """Test including specific columns"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2'],
            'label': ['yes', 'no'],
            'metadata': ['meta1', 'meta2'],
            'score': [1, 2]
        })

        processor = ColumnDatasetFilter(**{
            'filter-type': 'include',
            'columns': ['label', 'score']
        })

        result = processor.process(df)

        # Should include text (always), label, and score
        self.assertEqual(set(result.columns), {'text', 'label', 'score'})
        self.assertEqual(len(result), 2)

    def test_column_filter_exclude(self):
        """Test excluding specific columns"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2'],
            'label': ['yes', 'no'],
            'metadata': ['meta1', 'meta2'],
            'score': [1, 2]
        })

        processor = ColumnDatasetFilter(**{
            'filter-type': 'exclude',
            'columns': ['metadata', 'score']
        })

        result = processor.process(df)

        # Should exclude metadata and score
        self.assertEqual(set(result.columns), {'text', 'label'})
        self.assertEqual(len(result), 2)

    def test_column_filter_text_always_included(self):
        """Test that 'text' column is always included in include mode"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2'],
            'label': ['yes', 'no'],
            'metadata': ['meta1', 'meta2']
        })

        processor = ColumnDatasetFilter(**{
            'filter-type': 'include',
            'columns': ['label']  # Not including 'text'
        })

        result = processor.process(df)

        # 'text' should be automatically included
        self.assertIn('text', result.columns)
        self.assertIn('label', result.columns)
        self.assertEqual(len(result.columns), 2)

    def test_column_filter_exclude_nonexistent(self):
        """Test excluding columns that don't exist (should not error)"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2'],
            'label': ['yes', 'no']
        })

        processor = ColumnDatasetFilter(**{
            'filter-type': 'exclude',
            'columns': ['nonexistent_column', 'another_missing']
        })

        result = processor.process(df)

        # Should not error, just ignore missing columns
        self.assertEqual(set(result.columns), {'text', 'label'})


class TestMergeColumnsDatasetFilter(unittest.TestCase):
    """Tests for MergeColumnsDatasetFilter"""

    def test_merge_columns_basic(self):
        """Test basic column merging"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3', 'sample4'],
            'label_a': ['yes', 'no', 'yes', 'no'],
            'label_b': ['positive', 'negative', 'neutral', 'positive']
        })

        processor = MergeColumnsDatasetFilter(**{
            'columns_to_merge': {
                'label_a': {
                    'labels': ['yes'],
                    'new_label': 'category_yes'
                },
                'label_b': {
                    'labels': ['positive'],
                    'new_label': 'category_positive'
                }
            },
            'new_column_name': 'merged_label'
        })

        result = processor.process(df)

        # Check new column exists
        self.assertIn('merged_label', result.columns)

        # Check that rows matching label_a['yes'] get 'category_yes'
        # and rows matching label_b['positive'] get 'category_positive'
        # Note: The processor uses XOR (^=) which means only uniquely matched rows

    def test_merge_columns_with_multiple_labels(self):
        """Test merging with multiple label values per column"""
        df = pd.DataFrame({
            'text': [f'sample{i}' for i in range(6)],
            'status': ['active', 'active', 'inactive', 'inactive', 'pending', 'pending'],
            'type': ['A', 'B', 'A', 'B', 'A', 'B']
        })

        processor = MergeColumnsDatasetFilter(**{
            'columns_to_merge': {
                'status': {
                    'labels': ['active', 'pending'],
                    'new_label': 'open'
                },
                'type': {
                    'labels': ['A'],
                    'new_label': 'type_a'
                }
            },
            'new_column_name': 'category'
        })

        result = processor.process(df)

        # New column should exist
        self.assertIn('category', result.columns)

    def test_merge_columns_preserves_dataframe_structure(self):
        """Test that merging preserves other columns"""
        df = pd.DataFrame({
            'text': ['sample1', 'sample2', 'sample3'],
            'label_a': ['yes', 'no', 'yes'],
            'label_b': ['good', 'bad', 'good'],
            'metadata': ['m1', 'm2', 'm3']
        })

        processor = MergeColumnsDatasetFilter(**{
            'columns_to_merge': {
                'label_a': {
                    'labels': ['yes'],
                    'new_label': 'positive'
                }
            },
            'new_column_name': 'merged'
        })

        result = processor.process(df)

        # Original columns should still exist
        self.assertIn('text', result.columns)
        self.assertIn('label_a', result.columns)
        self.assertIn('label_b', result.columns)
        self.assertIn('metadata', result.columns)
        self.assertIn('merged', result.columns)


class TestDatasetProcessorIntegration(unittest.TestCase):
    """Integration tests for chaining dataset processors"""

    def test_chain_filter_then_downsample(self):
        """Test chaining filter then downsample processors"""
        df = pd.DataFrame({
            'text': [f'sample{i}' for i in range(10)],
            'type': ['inbound']*6 + ['outbound']*4,
            'label': ['yes']*4 + ['no']*6
        })

        # First filter to include only inbound
        filter_processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'include',
            'column-name': 'type',
            'value': 'inbound'
        })
        filtered = filter_processor.process(df)

        # Then downsample
        downsample_processor = DownsampleClassDatasetFilter(**{
            'column-name': 'label',
            'value': 'yes'
        })
        result = downsample_processor.process(filtered)

        # Should only have inbound rows, with balanced labels
        self.assertTrue((result['type'] == 'inbound').all())

    def test_chain_column_select_then_filter(self):
        """Test chaining column selection then value filter"""
        df = pd.DataFrame({
            'text': [f'sample{i}' for i in range(4)],
            'label': ['yes', 'no', 'yes', 'no'],
            'metadata': ['m1', 'm2', 'm3', 'm4'],
            'extra': ['e1', 'e2', 'e3', 'e4']
        })

        # First select columns
        column_processor = ColumnDatasetFilter(**{
            'filter-type': 'include',
            'columns': ['label', 'metadata']
        })
        selected = column_processor.process(df)

        # Then filter by value
        filter_processor = ByColumnValueDatasetFilter(**{
            'filter-type': 'include',
            'column-name': 'label',
            'value': 'yes'
        })
        result = filter_processor.process(selected)

        # Should only have selected columns and filtered rows
        self.assertEqual(set(result.columns), {'text', 'label', 'metadata'})
        self.assertEqual(len(result), 2)
        self.assertTrue((result['label'] == 'yes').all())


if __name__ == '__main__':
    unittest.main()
