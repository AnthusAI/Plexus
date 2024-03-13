import unittest
from unittest.mock import mock_open, patch
from jinja2 import Environment
from jinja2.exceptions import TemplateNotFound

from .PromptTemplateLoader import PromptTemplateLoader

class TestPromptTemplateLoader(unittest.TestCase):
    def setUp(self):
        self.markdown_content = """
# Title
This is the content of section one.

## Element One
This is the content of subsection 1.

### Rules
This is the content of clarification 1.

## Element Two
This is the content of subsection 2.
        """
        self.loader = PromptTemplateLoader(markdown_content=self.markdown_content)

    def test_section_loading(self):
        section_name = 'Element One'
        template = self.loader.get_template(section_name=section_name)
        expected_content = "This is the content of subsection 1.\n"
        self.assertEqual(
            template.strip(),
            expected_content.strip(),
            "The loader should correctly load the content of Subsection One.")

    def test_section_rules(self):
        section_name = 'Element One'
        template = self.loader.get_template(
            section_name=section_name,
            content_type='rules')
        expected_content = "This is the content of clarification 1.\n"
        self.assertEqual(
            template.strip(),
            expected_content.strip(),
            "The loader should correctly load the rules content of Subsection One.")

    def test_missing_section(self):
        section_name = 'Element Three'
        with self.assertRaises(ValueError):
            self.loader.get_template(
                section_name=section_name)

    def test_missing_rules(self):
        section_name = 'Element Two'
        template = self.loader.get_template(
            section_name=section_name,
            content_type='rules')
        self.assertIsNone(
            template,
            "Expected None for missing rules, but got something else.")

    def test_section_parsing(self):
        section_name = 'Element Two'
        template = self.loader.get_template(section_name=section_name)
        expected_content = "This is the content of subsection 2.\n"
        self.assertEqual(
            template.strip(),
            expected_content.strip(),
            "The loader should correctly parse and load the content of Subsection Two.")
        
if __name__ == '__main__':
    unittest.main()