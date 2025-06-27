# Localization & Translation Strategy

This document outlines the formal plan for handling localization and translation within the Plexus project. The goal is to ensure a consistent, high-quality, multi-language user experience.

## Core Principles

1.  **English as Source of Truth**: The English message file (`dashboard/messages/en.json`) is the canonical source for all text in the application. All new text and changes must start here.
2.  **Automated Translation**: To ensure efficiency, translations for other languages will be automatically generated from the English source file.
3.  **Brand Consistency**: A "Brand Glossary" is maintained to govern the translation of specific terms, ensuring that brand names, trademarks, and key concepts are handled consistently across all languages.

## Current Implementation

-   **Technology**: The dashboard utilizes the [`next-intl`](https://next-intl.dev/) library, integrated with the Next.js App Router.
-   **Message Files**: Translation messages are stored as JSON files in the `dashboard/messages/` directory.
-   **Routing**: Internationalized routing is handled via a `[locale]` dynamic segment in the `dashboard/app/` directory.

## Translation Status

-   **English (`en`)**: Complete. This is the source of truth.
-   **Spanish (`es`)**: Draft translations exist in `dashboard/messages/es.json`. These were generated before the formal glossary was established and have **not been proofread**. They should not be considered final and are subject to change based on the rules defined in this document.

## Translation Workflow

1.  **Adding New Text**: All new user-facing text must be added as a key-value pair to `dashboard/messages/en.json`.
2.  **Automatic Generation**: The localization pipeline will automatically detect changes in `en.json` and generate corresponding draft translations for all other supported languages.
3.  **Applying Glossary Rules**: The pipeline will consult the Brand Glossary to apply specific rules, such as preventing the translation of certain words or enforcing specific translations.
4.  **Proofreading**: Generated translations must be proofread by a native speaker before they are considered ready for production.

## Brand Glossary

This glossary defines how specific terms should be handled by the translation process.

| Term    | Language | Instruction         | Translation | Notes                                                                                                                  |
| :------ | :------- | :------------------ | :---------- | :--------------------------------------------------------------------------------------------------------------------- |
| `Plexus`  | `All`      | Do not translate    | `Plexus`      | This is a brand name.                                                                                                  |
| `item`    | `es`       | Force translation   | `ítem`        | The Spanish word "ítem" is preferred for consistency, as advised by our Spanish language consultants. The accent is important. |

</rewritten_file> 