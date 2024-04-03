import yaml
import re
import mistune

class PromptTemplateLoader:
    def __init__(self, *, markdown_content):
        self.markdown_content = markdown_content
        self.sections = self.parse_markdown_sections(markdown_content)

    def get_template(self, *, section_name, content_type='prompt'):
        if section_name in self.sections:
            section_content = self.sections[section_name]
            if content_type == 'rules' and 'rules' in section_content:
                return section_content['rules']
            elif content_type == 'prompt':
                return section_content['prompt']
        if content_type == 'rules':
            raise ValueError(f"Rules for '{section_name}' not found in the template.")
        else:
            raise ValueError(f"Section '{section_name}' not found in the template.")

    def parse_markdown_sections(self, markdown_content):
        sections = {}
        current_section = None
        parsing_rules = False

        markdown = mistune.create_markdown(renderer=None)
        ast = markdown(markdown_content)

        def extract_text_from_node(node):
            if 'raw' in node:
                return node['raw']
            elif 'children' in node:
                return ''.join([extract_text_from_node(child) for child in node['children']])
            return ''

        def process_node(node, sections, current_section, parsing_rules):
            if node['type'] == 'heading':
                text = extract_text_from_node(node)
                if text == 'Rules' and current_section:
                    parsing_rules = True
                    sections[current_section]['rules'] = ''
                else:
                    current_section = text
                    parsing_rules = False
                    sections[current_section] = {'prompt': '', 'rules': None}
            elif node['type'] in ['blank_line', 'paragraph', 'block_code', 'block_quote', 'list_item']:
                text = extract_text_from_node(node)
                if node['type'] == 'block_code':
                    text = "```\n" + text + "\n```"
                elif node['type'] == 'list_item':
                    text = '* ' + text
                elif node['type'] == 'block_quote':
                    text = '> ' + text
                if current_section:
                    if parsing_rules:
                        sections[current_section]['rules'] += text + '\n'
                    else:
                        sections[current_section]['prompt'] += text + '\n'
            elif node['type'] == 'list':
                for child in node['children']:
                    current_section, parsing_rules = process_node(child, sections, current_section, parsing_rules)

            return current_section, parsing_rules

        for node in ast:
            current_section, parsing_rules = process_node(node, sections, current_section, parsing_rules)

        return sections

    def load_decision_tree(self):
        if 'Decision Tree' in self.sections:
            decision_tree_yaml = self.sections['Decision Tree']
            decision_tree = yaml.safe_load(decision_tree_yaml)
            return self.process_decision_tree(decision_tree)
        else:
            raise ValueError("'Decision Tree' section not found in the template.")

    def process_decision_tree(self, decision_tree):
        if isinstance(decision_tree, dict):
            processed_tree = {}
            for key, value in decision_tree.items():
                if key == 'decision':
                    processed_tree['element'] = value
                else:
                    processed_tree[key] = self.process_decision_tree(value)
            return processed_tree
        else:
            return decision_tree

    def load_preprocessing_steps(self):
        if 'Preprocessing' in self.sections:
            preprocessing_yaml = self.sections['Preprocessing']
            preprocessing_steps = yaml.safe_load(preprocessing_yaml)
            return self.process_preprocessing_steps(preprocessing_steps)
        else:
            raise ValueError("'Preprocessing' section not found in the template.")

    def process_preprocessing_steps(self, preprocessing_steps):
        processed_steps = []
        for step in preprocessing_steps:
            processed_step = {}
            for key, value in step.items():
                if key == 'processor':
                    processed_step['processor'] = value
                elif key == 'keywords':
                    processed_step['keywords'] = [self.process_keyword(keyword) for keyword in value]
            processed_steps.append(processed_step)
        return processed_steps

    def process_keyword(self, keyword):
        if isinstance(keyword, str) and keyword.startswith('!regex'):
            return re.compile(keyword[len('!regex'):].strip())
        else:
            return keyword