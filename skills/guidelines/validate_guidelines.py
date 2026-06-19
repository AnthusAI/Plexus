# /// script
# dependencies = [
#   "rich",
# ]
# ///

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.guidelines.validator import (  # noqa: E402
    ValidationResult,
    determine_classifier_type,
    extract_classes_metadata,
    find_unknown_sections,
    get_optional_sections,
    get_required_sections,
    parse_markdown_sections,
    validate_guidelines_content,
    validate_guidelines_file,
)

console = Console()


def validate_guidelines(filepath: Path) -> ValidationResult:
    return validate_guidelines_file(filepath)


def display_validation_results(result: ValidationResult, filepath: Path) -> None:
    console.print(f"\n[bold]Validation Results for:[/bold] {filepath.name}\n")

    if result.classifier_type:
        type_display = result.classifier_type.replace("_", " ").title()
        console.print(f"[cyan]Classifier Type:[/cyan] {type_display}\n")

    for message in result.messages:
        if message.startswith("✓"):
            console.print(f"[green]{message}[/green]")
        elif message.startswith("✗"):
            console.print(f"[red]{message}[/red]")
        elif message.startswith("Warning"):
            console.print(f"[yellow]{message}[/yellow]")
        else:
            console.print(message)

    if result.missing_sections:
        console.print("\n[bold red]Missing Required Sections:[/bold red]")
        for section in result.missing_sections:
            console.print(f"  • {section}")

    if result.found_sections:
        console.print("\n[bold]Found Sections:[/bold]")
        content = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
        sections = parse_markdown_sections(content)
        classes_metadata = extract_classes_metadata(sections.get("Classes", ""))
        required_sections = (
            get_required_sections(result.classifier_type, classes_metadata)
            if result.classifier_type
            else []
        )

        for section in result.found_sections:
            if section in required_sections or section in ["Objective", "Classes"]:
                console.print(f"  • {section} [green]✓[/green]")
            else:
                console.print(f"  • {section} [dim](optional)[/dim]")

    console.print()

    if result.is_valid:
        console.print("[bold green]✓ Validation PASSED[/bold green]")
    else:
        console.print("[bold red]✗ Validation FAILED[/bold red]")

    console.print()


def main() -> None:
    if len(sys.argv) < 2:
        console.print("[red]Error:[/red] Please provide a guidelines file path")
        console.print("\nUsage: python validate_guidelines.py <guidelines.md>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    result = validate_guidelines(filepath)
    display_validation_results(result, filepath)

    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
