from types import SimpleNamespace
import json
from unittest.mock import AsyncMock

import pytest

from plexus.reports.blocks.feedback_contradictions import FeedbackContradictions


class _DummyClient:
    def __init__(self):
        self.context = SimpleNamespace(account_id='account-1')

    def execute(self, *_args, **_kwargs):
        return {}


def _parse_output(payload: str):
    json_text = '\n'.join(line for line in payload.split('\n') if not line.startswith('#'))
    return json.loads(json_text)


@pytest.mark.asyncio
async def test_feedback_contradictions_mode_returns_contradiction_payload(monkeypatch):
    block = FeedbackContradictions(
        config={'scorecard': 'CMG EDU', 'score': 'Branding and Matching', 'mode': 'contradictions'},
        params={},
        api_client=_DummyClient(),
    )
    block.report_block_id = 'block-123'

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_contradictions.Scorecard.get_by_external_id',
        lambda external_id, client: SimpleNamespace(id='scorecard-1', name='CMG EDU'),
    )
    monkeypatch.setattr(
        block,
        '_resolve_score',
        AsyncMock(return_value=SimpleNamespace(id='score-1', name='Branding and Matching')),
    )
    monkeypatch.setattr(block, '_fetch_guidelines', AsyncMock(return_value='Guideline text'))

    async def _fetch_items(*_args, **_kwargs):
        return [SimpleNamespace(id='fi-1', itemId='item-1', isInvalid=False)]

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_contradictions.feedback_utils.fetch_feedback_items_for_score',
        _fetch_items,
    )
    monkeypatch.setattr(block, '_fetch_score_results_by_item_ids', AsyncMock(return_value={}))

    class _Service:
        async def analyze_items(self, *args, **kwargs):
            return [
                {
                    'feedback_item_id': 'fi-1',
                    'reason': 'Policy contradiction.',
                    'voting': [{'model': 'sonnet', 'result': True}],
                    'confidence': 'high',
                    'verdict': 'contradiction',
                    'associated_dataset_eligible': False,
                    'edited_at': None,
                }
            ]

    monkeypatch.setattr('plexus.reports.blocks.feedback_contradictions.GuidelineVettingService', _Service)
    monkeypatch.setattr(
        block,
        '_cluster_topics',
        AsyncMock(return_value=[
            {'label': 'Topic A', 'count': 1, 'summary': '', 'guideline_quote': '', 'exemplars': []}
        ]),
    )

    output, _log = await block.generate()
    parsed = _parse_output(output)
    assert parsed['mode'] == 'contradictions'
    assert parsed['contradictions_found'] == 1
    assert parsed['aligned_found'] == 0
    assert len(parsed['topics']) == 1


@pytest.mark.asyncio
async def test_feedback_contradictions_mode_aligned_includes_dataset_payload(monkeypatch):
    block = FeedbackContradictions(
        config={'scorecard': 'CMG EDU', 'score': 'Branding and Matching', 'mode': 'aligned'},
        params={},
        api_client=_DummyClient(),
    )
    block.report_block_id = 'block-456'

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_contradictions.Scorecard.get_by_external_id',
        lambda external_id, client: SimpleNamespace(id='scorecard-1', name='CMG EDU'),
    )
    monkeypatch.setattr(
        block,
        '_resolve_score',
        AsyncMock(return_value=SimpleNamespace(id='score-1', name='Branding and Matching')),
    )
    monkeypatch.setattr(block, '_fetch_guidelines', AsyncMock(return_value='Guideline text'))

    async def _fetch_items(*_args, **_kwargs):
        return [SimpleNamespace(id='fi-1', itemId='item-1', isInvalid=False)]

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_contradictions.feedback_utils.fetch_feedback_items_for_score',
        _fetch_items,
    )
    monkeypatch.setattr(block, '_fetch_score_results_by_item_ids', AsyncMock(return_value={}))

    class _Service:
        async def analyze_items(self, *args, **kwargs):
            return [
                {
                    'feedback_item_id': 'fi-1',
                    'reason': 'Aligned with guideline.',
                    'voting': [{'model': 'sonnet', 'result': False}],
                    'confidence': 'high',
                    'verdict': 'aligned',
                    'associated_dataset_eligible': True,
                    'edited_at': None,
                }
            ]

    monkeypatch.setattr('plexus.reports.blocks.feedback_contradictions.GuidelineVettingService', _Service)
    monkeypatch.setattr(
        block,
        '_cluster_topics',
        AsyncMock(return_value=[
            {'label': 'Topic A', 'count': 1, 'summary': '', 'guideline_quote': '', 'exemplars': []}
        ]),
    )

    output, _log = await block.generate()
    parsed = _parse_output(output)
    assert parsed['mode'] == 'aligned'
    assert parsed['eligible_associated_feedback_item_ids'] == ['fi-1']
    assert parsed['eligible_count'] == 1
    assert parsed['eligibility_rule'] == 'unanimous non-contradiction'
    assert parsed['source_report_block_id'] == 'block-456'
