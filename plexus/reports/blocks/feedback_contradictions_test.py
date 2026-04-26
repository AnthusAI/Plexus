from types import SimpleNamespace
import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from plexus.reports.blocks.feedback_contradictions import FeedbackContradictions


class _DummyClient:
    def __init__(self):
        self.context = SimpleNamespace(account_id='account-1')

    def execute(self, *_args, **_kwargs):
        return {}


@pytest.mark.asyncio
async def test_resolve_scorecard_accepts_hyphenated_name(monkeypatch):
    block = FeedbackContradictions(
        config={"scorecard": "Prime - EDU 3rd Party", "score": "Agent Branding"},
        params={},
        api_client=_DummyClient(),
    )

    monkeypatch.setattr(
        "plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_key",
        lambda key, client: None,
    )
    monkeypatch.setattr(
        "plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name",
        lambda name, client: SimpleNamespace(id="scorecard-1", name=name),
    )
    monkeypatch.setattr(
        "plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_external_id",
        lambda external_id, client: None,
    )

    resolved = await block._resolve_scorecard("Prime - EDU 3rd Party")

    assert resolved is not None
    assert resolved.name == "Prime - EDU 3rd Party"


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
        'plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name',
        lambda name, client: SimpleNamespace(id='scorecard-1', name='CMG EDU'),
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
    assert output.startswith("# CMG EDU - Branding and Matching - Feedback Contradictions")
    parsed = _parse_output(output)
    assert parsed['report_type'] == 'feedback_contradictions'
    assert parsed['scope'] == 'single_score'
    assert parsed['scorecard_name'] == 'CMG EDU'
    assert parsed['score_id'] == 'score-1'
    assert parsed['block_title'] == 'Feedback Contradictions'
    assert parsed['mode'] == 'contradictions'
    assert parsed['contradictions_found'] == 1
    assert parsed['aligned_found'] == 0
    assert len(parsed['topics']) == 1
    assert 'rubric_evidence_packs' not in parsed


@pytest.mark.asyncio
async def test_feedback_contradictions_mode_aligned_includes_dataset_payload(monkeypatch):
    block = FeedbackContradictions(
        config={'scorecard': 'CMG EDU', 'score': 'Branding and Matching', 'mode': 'aligned'},
        params={},
        api_client=_DummyClient(),
    )
    block.report_block_id = 'block-456'

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name',
        lambda name, client: SimpleNamespace(id='scorecard-1', name='CMG EDU'),
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
                    'edited_at': '2026-04-02T00:00:00Z',
                    'final_value': 'Yes',
                },
                {
                    'feedback_item_id': 'fi-2',
                    'reason': 'Also aligned.',
                    'voting': [{'model': 'gpt', 'result': False}],
                    'confidence': 'high',
                    'verdict': 'aligned',
                    'associated_dataset_eligible': True,
                    'edited_at': '2026-04-03T00:00:00Z',
                    'final_value': 'No',
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
    assert output.startswith("# CMG EDU - Branding and Matching - Feedback Aligned Items")
    parsed = _parse_output(output)
    assert parsed['report_type'] == 'feedback_contradictions'
    assert parsed['scope'] == 'single_score'
    assert parsed['scorecard_name'] == 'CMG EDU'
    assert parsed['score_id'] == 'score-1'
    assert parsed['block_title'] == 'Feedback Contradictions'
    assert parsed['mode'] == 'aligned'
    assert parsed['eligible_associated_feedback_item_ids'] == ['fi-2', 'fi-1']
    assert parsed['eligible_associated_feedback_items'] == [
        {
            'feedback_item_id': 'fi-2',
            'edited_at': '2026-04-03T00:00:00Z',
            'final_value': 'No',
        },
        {
            'feedback_item_id': 'fi-1',
            'edited_at': '2026-04-02T00:00:00Z',
            'final_value': 'Yes',
        },
    ]
    assert parsed['eligible_count'] == 2
    assert parsed['eligibility_rule'] == 'unanimous non-contradiction'
    assert parsed['source_report_block_id'] == 'block-456'
    assert 'rubric_evidence_packs' not in parsed


@pytest.mark.asyncio
async def test_feedback_contradictions_applies_max_feedback_items_cap(monkeypatch):
    block = FeedbackContradictions(
        config={
            'scorecard': 'CMG EDU',
            'score': 'Branding and Matching',
            'mode': 'aligned',
            'max_feedback_items': 1,
        },
        params={},
        api_client=_DummyClient(),
    )
    block.report_block_id = 'block-789'

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name',
        lambda name, client: SimpleNamespace(id='scorecard-1', name='CMG EDU'),
    )
    monkeypatch.setattr(
        block,
        '_resolve_score',
        AsyncMock(return_value=SimpleNamespace(id='score-1', name='Branding and Matching')),
    )
    monkeypatch.setattr(block, '_fetch_guidelines', AsyncMock(return_value='Guideline text'))

    async def _fetch_items(*_args, **_kwargs):
        return [
            SimpleNamespace(id='fi-1', itemId='item-1', isInvalid=False),
            SimpleNamespace(id='fi-2', itemId='item-2', isInvalid=False),
        ]

    monkeypatch.setattr(
        'plexus.reports.blocks.feedback_contradictions.feedback_utils.fetch_feedback_items_for_score',
        _fetch_items,
    )
    captured_item_ids = []

    async def _fetch_score_results(item_ids, _score_id):
        captured_item_ids.extend(item_ids)
        return {}

    monkeypatch.setattr(block, '_fetch_score_results_by_item_ids', _fetch_score_results)

    class _Service:
        async def analyze_items(self, items, *_args, **_kwargs):
            return [
                {
                    'feedback_item_id': items[0].id,
                    'reason': 'Aligned with guideline.',
                    'voting': [{'model': 'sonnet', 'result': False}],
                    'confidence': 'high',
                    'verdict': 'aligned',
                    'associated_dataset_eligible': True,
                    'edited_at': '2026-04-03T00:00:00Z',
                    'final_value': 'Yes',
                }
            ]

    monkeypatch.setattr('plexus.reports.blocks.feedback_contradictions.GuidelineVettingService', _Service)
    monkeypatch.setattr(block, '_cluster_topics', AsyncMock(return_value=[]))

    output, _log = await block.generate()
    parsed = _parse_output(output)
    assert parsed['scorecard_name'] == 'CMG EDU'
    assert parsed['score_id'] == 'score-1'
    assert captured_item_ids == ['item-1']
    assert parsed['total_items_analyzed'] == 1
    assert parsed['block_configuration']['max_feedback_items'] == 1


@pytest.mark.asyncio
async def test_resolve_score_accepts_uuid_via_section_scorecard_lookup(monkeypatch):
    client = MagicMock()
    client.context = SimpleNamespace(account_id="account-1")
    client.execute.return_value = {
        "getScorecard": {"sections": {"items": [{"id": "section-1"}]}}
    }

    block = FeedbackContradictions(
        config={"scorecard": "scorecard-1", "score": "72db3535-2a93-48f3-8900-bb275490cc28"},
        params={},
        api_client=client,
    )

    monkeypatch.setattr(
        "plexus.reports.blocks.score_resolution.Score.get_by_id",
        lambda id, client: SimpleNamespace(
            id=id,
            name="Property Type and Home Value Metadata AI",
            sectionId="section-1",
        ),
    )

    resolved = await block._resolve_score("72db3535-2a93-48f3-8900-bb275490cc28", "scorecard-1")

    assert resolved is not None
    assert resolved.id == "72db3535-2a93-48f3-8900-bb275490cc28"


@pytest.mark.asyncio
async def test_feedback_contradictions_generate_propagates_failures(monkeypatch):
    block = FeedbackContradictions(
        config={"scorecard": "CMG EDU", "score": "Branding and Matching"},
        params={},
        api_client=_DummyClient(),
    )

    monkeypatch.setattr(
        block,
        "_resolve_scorecard",
        AsyncMock(return_value=SimpleNamespace(id="scorecard-1", name="CMG EDU")),
    )
    monkeypatch.setattr(
        block,
        "_resolve_score",
        AsyncMock(side_effect=ValueError("Score not found: broken")),
    )

    with pytest.raises(ValueError, match="Score not found: broken"):
        await block.generate()
