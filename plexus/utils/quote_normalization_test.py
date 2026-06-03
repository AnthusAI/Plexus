"""Tests for quote normalization utilities."""

from plexus.utils.quote_normalization import normalize_quotes


class TestNormalizeQuotes:
    """Tests for the normalize_quotes function."""

    def test_normalizes_curly_double_quotes_to_straight(self):
        """Should replace curly double quotes with straight quotes."""
        # Build test string with curly quotes using chr()
        left_curly = chr(0x201C)   # U+201C LEFT DOUBLE QUOTATION MARK
        right_curly = chr(0x201D)  # U+201D RIGHT DOUBLE QUOTATION MARK
        text = f'The agent said {left_curly}hello world{right_curly}'

        # Verify input has curly quotes
        assert left_curly in text and right_curly in text

        result = normalize_quotes(text)

        # Output should have straight quotes (build expected without curly quotes)
        expected = 'The agent said ' + '"' + 'hello world' + '"'
        assert result == expected
        assert left_curly not in result
        assert right_curly not in result

    def test_normalizes_curly_single_quotes_to_straight(self):
        """Should replace curly single quotes with straight apostrophes."""
        # Build test string with curly quotes using chr()
        left_single = chr(0x2018)  # U+2018 LEFT SINGLE QUOTATION MARK
        right_single = chr(0x2019)  # U+2019 RIGHT SINGLE QUOTATION MARK
        text = f'The customer replied {left_single}yes, that{right_single}s correct{right_single}'

        # Verify input has curly quotes
        assert left_single in text and right_single in text

        result = normalize_quotes(text)

        # Output should have straight quotes (build expected without curly quotes)
        expected = "The customer replied 'yes, that's correct'"
        assert result == expected
        assert left_single not in result
        assert right_single not in result

    def test_normalizes_mixed_quote_types(self):
        """Should handle text with both double and single curly quotes."""
        # Build test string with mixed curly quotes
        left_dbl = chr(0x201C)
        right_dbl = chr(0x201D)
        left_sgl = chr(0x2018)
        right_sgl = chr(0x2019)
        text = f'Agent: {left_dbl}The customer said {left_sgl}yes{right_sgl} to the offer{right_dbl}'

        result = normalize_quotes(text)

        # Output should have straight quotes only (build expected without curly quotes)
        expected = 'Agent: ' + '"' + 'The customer said ' + "'" + 'yes' + "'" + ' to the offer' + '"'
        assert result == expected
        assert left_dbl not in result and right_dbl not in result
        assert left_sgl not in result and right_sgl not in result

    def test_handles_empty_string(self):
        """Should handle empty string without error."""
        assert normalize_quotes('') == ''

    def test_handles_none(self):
        """Should return None for None input."""
        assert normalize_quotes(None) is None

    def test_preserves_straight_quotes(self):
        """Should not modify text that already has straight quotes."""
        text = 'The agent said "hello" and the customer replied \'yes\''
        result = normalize_quotes(text)
        assert result == text

    def test_handles_text_without_quotes(self):
        """Should return unchanged text that contains no quotes."""
        text = 'This text has no quotes at all'
        result = normalize_quotes(text)
        assert result == text

    def test_real_world_llm_output(self):
        """Should normalize typical LLM output with curly quotes."""
        # Build test string with curly quotes and markdown
        left_dbl = chr(0x201C)
        right_dbl = chr(0x201D)
        text = f'The agent said {left_dbl}we ask for **60 to 90 minutes**{right_dbl} and confirmed {left_dbl}Is that right?{right_dbl}'

        result = normalize_quotes(text)

        # Output should have straight quotes (build expected without curly quotes)
        expected = 'The agent said ' + '"' + 'we ask for **60 to 90 minutes**' + '"' + ' and confirmed ' + '"' + 'Is that right?' + '"'
        assert result == expected

        # Should preserve markdown
        assert '**60 to 90 minutes**' in result

        # Should have no curly quotes
        assert left_dbl not in result and right_dbl not in result

    def test_multiple_occurrences(self):
        """Should normalize all occurrences of curly quotes."""
        # Build test string with multiple curly quotes
        left_dbl = chr(0x201C)
        right_dbl = chr(0x201D)
        text = f'{left_dbl}First quote{right_dbl} and {left_dbl}second quote{right_dbl} and {left_dbl}third quote{right_dbl}'

        result = normalize_quotes(text)

        # Output should have straight quotes (build expected without curly quotes)
        expected = '"' + 'First quote' + '"' + ' and ' + '"' + 'second quote' + '"' + ' and ' + '"' + 'third quote' + '"'
        assert result == expected
        assert result.count('"') == 6  # 3 pairs of straight quotes
        assert left_dbl not in result and right_dbl not in result
