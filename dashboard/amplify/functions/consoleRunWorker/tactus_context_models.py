"""Slim context model exports for worker runtime.

This keeps Tactus registry imports working without requiring full Biblicus
context-engine dependencies in the Lambda worker bundle.
"""

from pydantic import BaseModel, ConfigDict


try:
    from biblicus.context_engine import (
        AssistantMessageSpec,
        CompactorDeclaration,
        ContextBudgetSpec,
        ContextDeclaration,
        ContextExpansionSpec,
        ContextInsertSpec,
        ContextMessageSpec,
        ContextPackBudgetSpec,
        ContextPackSpec,
        ContextPolicySpec,
        ContextRetrieverRequest,
        ContextTemplateSpec,
        CorpusDeclaration,
        HistoryInsertSpec,
        RetrieverDeclaration,
        SystemMessageSpec,
        UserMessageSpec,
    )
except Exception:
    class _ContextModel(BaseModel):
        model_config = ConfigDict(extra="allow")

    class AssistantMessageSpec(_ContextModel):
        pass

    class CompactorDeclaration(_ContextModel):
        pass

    class ContextBudgetSpec(_ContextModel):
        pass

    class ContextDeclaration(_ContextModel):
        pass

    class ContextExpansionSpec(_ContextModel):
        pass

    class ContextInsertSpec(_ContextModel):
        pass

    class ContextMessageSpec(_ContextModel):
        pass

    class ContextPackBudgetSpec(_ContextModel):
        pass

    class ContextPackSpec(_ContextModel):
        pass

    class ContextPolicySpec(_ContextModel):
        pass

    class ContextRetrieverRequest(_ContextModel):
        pass

    class ContextTemplateSpec(_ContextModel):
        pass

    class CorpusDeclaration(_ContextModel):
        pass

    class HistoryInsertSpec(_ContextModel):
        pass

    class RetrieverDeclaration(_ContextModel):
        pass

    class SystemMessageSpec(_ContextModel):
        pass

    class UserMessageSpec(_ContextModel):
        pass


__all__ = [
    "AssistantMessageSpec",
    "CompactorDeclaration",
    "ContextBudgetSpec",
    "ContextDeclaration",
    "ContextExpansionSpec",
    "ContextInsertSpec",
    "ContextMessageSpec",
    "ContextPackBudgetSpec",
    "ContextPackSpec",
    "ContextPolicySpec",
    "ContextRetrieverRequest",
    "ContextTemplateSpec",
    "CorpusDeclaration",
    "HistoryInsertSpec",
    "RetrieverDeclaration",
    "SystemMessageSpec",
    "UserMessageSpec",
]
