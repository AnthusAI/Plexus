# /// script
# dependencies = [
#   "pytest",
#   "rich",
# ]
# ///

import pytest
from pathlib import Path
from validate_guidelines import (
    validate_guidelines,
    parse_markdown_sections,
    extract_classes_metadata,
    determine_classifier_type,
    get_required_sections,
    get_optional_sections,
    find_unknown_sections,
)


@pytest.fixture
def tmp_guidelines_file(tmp_path):
    def _create_file(content: str, filename: str = "test_guidelines.md") -> Path:
        filepath = tmp_path / filename
        filepath.write_text(content)
        return filepath
    return _create_file


class TestBinaryClassifier:
    
    @pytest.fixture
    def valid_binary_guidelines(self):
        return """# Spam Classifier

## Objective

Detect spam messages in customer communications.

## Classes
- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Messages that are unsolicited commercial content or malicious.

## Conditions for Yes

- Contains promotional language
- Includes suspicious links
- Requests personal information

## Definition of No

Legitimate customer communications.
"""

    @pytest.fixture
    def binary_with_optional_sections(self):
        return """# Spam Classifier

## Objective

Detect spam messages in customer communications.

## Classes
- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Messages that are unsolicited commercial content or malicious.

## Conditions for Yes

- Contains promotional language
- Includes suspicious links
- Requests personal information

## Definition of No

Legitimate customer communications.

## Examples

### Clear Yes Cases

Example spam message here.

### Clear No Cases

Example legitimate message here.

### Boundary Cases

Example ambiguous case here.
"""

    def test_valid_binary_classifier_passes(self, tmp_guidelines_file, valid_binary_guidelines):
        filepath = tmp_guidelines_file(valid_binary_guidelines)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert result.classifier_type == 'binary'
        assert len(result.missing_sections) == 0
        assert 'Objective' in result.found_sections
        assert 'Classes' in result.found_sections
        assert 'Definition of Yes' in result.found_sections
        assert 'Conditions for Yes' in result.found_sections
        assert 'Definition of No' in result.found_sections
    
    def test_binary_with_optional_sections_passes(self, tmp_guidelines_file, binary_with_optional_sections):
        filepath = tmp_guidelines_file(binary_with_optional_sections)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert result.classifier_type == 'binary'
        assert len(result.missing_sections) == 0
        assert 'Examples' in result.found_sections
        assert 'Clear Yes Cases' in result.found_sections
        assert 'Clear No Cases' in result.found_sections
        assert 'Boundary Cases' in result.found_sections
        assert len(result.unknown_sections) == 0
    
    def test_missing_objective_fails(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("## Objective\n\nDetect spam messages in customer communications.\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Objective' in result.missing_sections
    
    def test_missing_definition_of_yes_fails(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("## Definition of Yes\n\nMessages that are unsolicited commercial content or malicious.\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Definition of Yes' in result.missing_sections
    
    def test_missing_conditions_for_yes_fails(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("## Conditions for Yes\n\n- Contains promotional language\n- Includes suspicious links\n- Requests personal information\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Conditions for Yes' in result.missing_sections
    
    def test_missing_definition_of_no_fails(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("## Definition of No\n\nLegitimate customer communications.\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Definition of No' in result.missing_sections
    
    def test_unknown_section_produces_warning(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines + "\n## Random Section\n\nThis should not be here.\n"
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert 'Random Section' in result.unknown_sections
        assert any('non-standard section' in msg for msg in result.messages)
    
    def test_missing_target_class_metadata_produces_warning(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("- Target class: Yes\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert any('Target class not specified' in msg for msg in result.messages)
    
    def test_missing_default_class_metadata_produces_warning(self, tmp_guidelines_file, valid_binary_guidelines):
        content = valid_binary_guidelines.replace("- Default class: No\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert any('Default class not specified' in msg for msg in result.messages)


class TestBinaryWithAbstentions:
    
    @pytest.fixture
    def valid_ternary_guidelines(self):
        return """# Medical Necessity Classifier

## Objective

Determine if a medical procedure is necessary for insurance approval.

## Classes
- Valid labels: [Yes, No, NA]
- Target class: No
- Default class: Yes
- Abstain class: NA

## Definition of No

Procedure is not medically necessary.

## Conditions for No

- Elective cosmetic procedure
- No supporting diagnosis
- Alternative treatment available

## Definition of NA

Cannot determine necessity from provided information.

## Conditions for NA

- Missing diagnostic codes
- Incomplete medical history
- Conflicting provider notes

## Definition of Yes

Procedure is medically necessary.
"""

    @pytest.fixture
    def ternary_with_optional_sections(self):
        return """# Medical Necessity Classifier

## Objective

Determine if a medical procedure is necessary for insurance approval.

## Classes
- Valid labels: [Yes, No, NA]
- Target class: No
- Default class: Yes
- Abstain class: NA

## Definition of No

Procedure is not medically necessary.

## Conditions for No

- Elective cosmetic procedure
- No supporting diagnosis
- Alternative treatment available

## Definition of NA

Cannot determine necessity from provided information.

## Conditions for NA

- Missing diagnostic codes
- Incomplete medical history
- Conflicting provider notes

## Definition of Yes

Procedure is medically necessary.

## Examples

### Clear No Cases

Example denied procedure.

### Clear Yes Cases

Example approved procedure.

### Clear NA Cases

Example with insufficient information.

### Boundary Cases

Example edge case.
"""

    def test_valid_ternary_classifier_passes(self, tmp_guidelines_file, valid_ternary_guidelines):
        filepath = tmp_guidelines_file(valid_ternary_guidelines)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert result.classifier_type == 'binary_with_abstentions'
        assert len(result.missing_sections) == 0
        assert 'Definition of NA' in result.found_sections
        assert 'Conditions for NA' in result.found_sections
    
    def test_ternary_with_optional_sections_passes(self, tmp_guidelines_file, ternary_with_optional_sections):
        filepath = tmp_guidelines_file(ternary_with_optional_sections)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert 'Examples' in result.found_sections
        assert 'Clear NA Cases' in result.found_sections
        assert len(result.unknown_sections) == 0
    
    def test_missing_definition_of_na_fails(self, tmp_guidelines_file, valid_ternary_guidelines):
        content = valid_ternary_guidelines.replace("## Definition of NA\n\nCannot determine necessity from provided information.\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Definition of NA' in result.missing_sections
    
    def test_missing_conditions_for_na_fails(self, tmp_guidelines_file, valid_ternary_guidelines):
        content = valid_ternary_guidelines.replace("## Conditions for NA\n\n- Missing diagnostic codes\n- Incomplete medical history\n- Conflicting provider notes\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Conditions for NA' in result.missing_sections
    
    def test_missing_abstain_class_metadata_produces_warning(self, tmp_guidelines_file, valid_ternary_guidelines):
        content = valid_ternary_guidelines.replace("- Abstain class: NA\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert any('Abstain class not specified' in msg for msg in result.messages)


class TestMultiClassClassifier:
    
    @pytest.fixture
    def valid_multiclass_guidelines(self):
        return """# Customer Inquiry Router

## Objective

Route customer inquiries to the appropriate team.

## Classes
- Valid labels: [Technical, Billing, Sales]

## Definition of Technical

Customer needs help with product functionality or technical issues.

## Conditions for Technical

- Error messages or bugs
- Questions about features
- Performance issues

## Definition of Billing

Customer has questions about invoices or payments.

## Conditions for Billing

- Invoice discrepancies
- Payment failures
- Subscription changes

## Definition of Sales

Customer is evaluating a purchase.

## Conditions for Sales

- Product comparisons
- Demo requests
- Pricing questions
"""

    @pytest.fixture
    def multiclass_with_optional_sections(self):
        return """# Customer Inquiry Router

## Objective

Route customer inquiries to the appropriate team.

## Classes
- Valid labels: [Technical, Billing, Sales]

## Definition of Technical

Customer needs help with product functionality or technical issues.

## Conditions for Technical

- Error messages or bugs
- Questions about features
- Performance issues

## Definition of Billing

Customer has questions about invoices or payments.

## Conditions for Billing

- Invoice discrepancies
- Payment failures
- Subscription changes

## Definition of Sales

Customer is evaluating a purchase.

## Conditions for Sales

- Product comparisons
- Demo requests
- Pricing questions

## Boundary Conditions

### Technical vs Billing

Technical issues are about functionality; billing issues are about payments.

### Billing vs Sales

Billing is for existing customers; sales is for prospects.

### Technical vs Sales

Technical is for current users; sales is for evaluators.

## Examples

### Clear Technical Cases

Example technical inquiry.

### Clear Billing Cases

Example billing inquiry.

### Clear Sales Cases

Example sales inquiry.

### Boundary Cases

Example ambiguous case.
"""

    def test_valid_multiclass_classifier_passes(self, tmp_guidelines_file, valid_multiclass_guidelines):
        filepath = tmp_guidelines_file(valid_multiclass_guidelines)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert result.classifier_type == 'multi_class'
        assert len(result.missing_sections) == 0
        assert 'Definition of Technical' in result.found_sections
        assert 'Conditions for Technical' in result.found_sections
        assert 'Definition of Billing' in result.found_sections
        assert 'Conditions for Billing' in result.found_sections
        assert 'Definition of Sales' in result.found_sections
        assert 'Conditions for Sales' in result.found_sections
    
    def test_multiclass_with_optional_sections_passes(self, tmp_guidelines_file, multiclass_with_optional_sections):
        filepath = tmp_guidelines_file(multiclass_with_optional_sections)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert 'Boundary Conditions' in result.found_sections
        assert 'Technical vs Billing' in result.found_sections
        assert 'Billing vs Sales' in result.found_sections
        assert 'Technical vs Sales' in result.found_sections
        assert 'Examples' in result.found_sections
        assert 'Clear Technical Cases' in result.found_sections
        assert 'Clear Billing Cases' in result.found_sections
        assert 'Clear Sales Cases' in result.found_sections
        assert len(result.unknown_sections) == 0
    
    def test_missing_definition_for_one_class_fails(self, tmp_guidelines_file, valid_multiclass_guidelines):
        content = valid_multiclass_guidelines.replace("## Definition of Sales\n\nCustomer is evaluating a purchase.\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Definition of Sales' in result.missing_sections
    
    def test_missing_conditions_for_one_class_fails(self, tmp_guidelines_file, valid_multiclass_guidelines):
        content = valid_multiclass_guidelines.replace("## Conditions for Billing\n\n- Invoice discrepancies\n- Payment failures\n- Subscription changes\n\n", "")
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert 'Conditions for Billing' in result.missing_sections
    
    def test_unknown_boundary_condition_produces_warning(self, tmp_guidelines_file, multiclass_with_optional_sections):
        content = multiclass_with_optional_sections + "\n### Technical vs Unknown\n\nThis is not a valid class pair.\n"
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert result.is_valid
        assert 'Technical vs Unknown' in result.unknown_sections


class TestEdgeCases:
    
    def test_file_not_found(self):
        filepath = Path("nonexistent_file.md")
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert any('File not found' in msg for msg in result.messages)
    
    def test_no_title_produces_warning(self, tmp_guidelines_file):
        content = """## Objective

Test objective.

## Classes
- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Test definition.

## Conditions for Yes

Test conditions.

## Definition of No

Test definition.
"""
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert any('No top-level title' in msg for msg in result.messages)
    
    def test_missing_classes_section_fails(self, tmp_guidelines_file):
        content = """# Test Classifier

## Objective

Test objective.

## Definition of Yes

Test definition.
"""
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert result.classifier_type is None
        assert any('Classes' in msg for msg in result.messages)
    
    def test_missing_valid_labels_fails(self, tmp_guidelines_file):
        content = """# Test Classifier

## Objective

Test objective.

## Classes
- Target class: Yes
- Default class: No

## Definition of Yes

Test definition.
"""
        filepath = tmp_guidelines_file(content)
        result = validate_guidelines(filepath)
        
        assert not result.is_valid
        assert result.classifier_type is None
        assert any('Valid labels not found' in msg for msg in result.messages)


class TestHelperFunctions:
    
    def test_parse_markdown_sections(self):
        content = """# Title

## Section 1

Content 1

## Section 2

Content 2
"""
        sections = parse_markdown_sections(content)
        
        assert 'Title' in sections
        assert 'Section 1' in sections
        assert 'Section 2' in sections
        assert sections['Section 1'].strip() == 'Content 1'
        assert sections['Section 2'].strip() == 'Content 2'
    
    def test_extract_classes_metadata(self):
        classes_content = """- Valid labels: [Yes, No, NA]
- Target class: No
- Default class: Yes
- Abstain class: NA"""
        
        metadata = extract_classes_metadata(classes_content)
        
        assert metadata['valid_labels'] == ['Yes', 'No', 'NA']
        assert metadata['target_class'] == 'No'
        assert metadata['default_class'] == 'Yes'
        assert metadata['abstain_class'] == 'NA'
    
    def test_determine_classifier_type_binary(self):
        sections = {
            'Classes': """- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No"""
        }
        
        classifier_type, messages = determine_classifier_type(sections)
        
        assert classifier_type == 'binary'
    
    def test_determine_classifier_type_ternary(self):
        sections = {
            'Classes': """- Valid labels: [Yes, No, NA]
- Target class: No
- Default class: Yes
- Abstain class: NA"""
        }
        
        classifier_type, messages = determine_classifier_type(sections)
        
        assert classifier_type == 'binary_with_abstentions'
    
    def test_determine_classifier_type_multiclass(self):
        sections = {
            'Classes': """- Valid labels: [A, B, C, D]"""
        }
        
        classifier_type, messages = determine_classifier_type(sections)
        
        assert classifier_type == 'multi_class'
    
    def test_get_required_sections_binary(self):
        classes_metadata = {'valid_labels': ['Yes', 'No']}
        required = get_required_sections('binary', classes_metadata)

        assert 'Objective' in required
        assert 'Classes' in required
        assert 'Definition of Yes' in required
        assert 'Conditions for Yes' in required
        assert 'Definition of No' in required
        # Note: 'Conditions for No' is optional, not required
    
    def test_get_optional_sections_binary(self):
        classes_metadata = {'valid_labels': ['Yes', 'No']}
        optional = get_optional_sections('binary', classes_metadata)
        
        assert 'Examples' in optional
        assert 'Clear Yes Cases' in optional
        assert 'Clear No Cases' in optional
        assert 'Boundary Cases' in optional
    
    def test_get_optional_sections_multiclass(self):
        classes_metadata = {'valid_labels': ['A', 'B', 'C']}
        optional = get_optional_sections('multi_class', classes_metadata)
        
        assert 'Boundary Conditions' in optional
        assert 'Examples' in optional
        assert 'Clear A Cases' in optional
        assert 'Clear B Cases' in optional
        assert 'Clear C Cases' in optional
        assert 'A vs B' in optional
        assert 'B vs C' in optional
        assert 'A vs C' in optional
    
    def test_find_unknown_sections(self):
        found = ['Objective', 'Classes', 'Random Section', 'Another Bad One']
        required = ['Objective', 'Classes']
        optional = {'Examples', 'Boundary Cases'}
        
        unknown = find_unknown_sections(found, required, optional)
        
        assert 'Random Section' in unknown
        assert 'Another Bad One' in unknown
        assert len(unknown) == 2