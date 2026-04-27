import React from 'react';
import { render, screen } from '@testing-library/react';
import { FeedbackItemView, type FeedbackItem } from './feedback-item-view';

describe('FeedbackItemView identifier rendering', () => {
  it('prefers item.itemIdentifiers.items when available', () => {
    const item: FeedbackItem = {
      id: 'fi-1',
      initialAnswerValue: 'Yes',
      finalAnswerValue: 'No',
      item: {
        id: 'item-1',
        externalId: 'EXT-1',
        itemIdentifiers: {
          items: [
            { name: 'Second', value: 'B-2', position: 2 },
            { name: 'First', value: 'A-1', position: 1 },
          ],
        },
      },
    };

    render(<FeedbackItemView item={item} />);

    expect(screen.getByText('First:')).toBeInTheDocument();
    expect(screen.getByText('A-1')).toBeInTheDocument();
  });

  it('uses top-level item_identifiers when nested identifiers are absent', () => {
    const item: FeedbackItem = {
      id: 'fi-2',
      initialAnswerValue: 'Yes',
      finalAnswerValue: 'Yes',
      item_identifiers: [
        { name: 'Call ID', value: 'CALL-123' },
        { name: 'Account ID', value: 'ACCT-456' },
      ],
      item_external_id: 'EXT-2',
    };

    render(<FeedbackItemView item={item} />);

    expect(screen.getByText('Call ID:')).toBeInTheDocument();
    expect(screen.getByText('CALL-123')).toBeInTheDocument();
  });
});
