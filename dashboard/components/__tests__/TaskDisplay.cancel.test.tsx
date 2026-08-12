import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

jest.mock('@/utils/amplify-client', () => ({ graphqlRequest: jest.fn(() => Promise.resolve({ data: { cancelCommand: { taskId: 'command-1' } } })) }));
jest.mock('@/app/contexts/AccountContext', () => ({
  useOptionalAccount: () => ({ selectedAccount: { id: 'account-1' } }),
}));
jest.mock('@/components/EvaluationTask', () => ({ __esModule: true, default: ({ controlButtons }: any) => <div>{controlButtons}</div> }));
jest.mock('@/components/ReportTask', () => ({ __esModule: true, default: ({ task, controlButtons }: any) => <div><span>{task.status}</span>{controlButtons}</div> }));

import { TaskDisplay } from '@/components/TaskDisplay';
import { graphqlRequest } from '@/utils/amplify-client';
const mockGraphqlRequest = graphqlRequest as jest.Mock;

const evaluationData = { id: 'evaluation-1', type: 'Accuracy', createdAt: '2026-01-01T00:00:00Z', status: 'RUNNING' } as any;

describe('TaskDisplay command cancellation', () => {
  it('renders and invokes cancellation only for a selected-account cancellable command Task', async () => {
    render(<TaskDisplay variant="grid" task={{ id: 'command-1', accountId: 'account-1', type: 'Evaluation', status: 'RUNNING', target: 'evaluation', command: 'evaluate accuracy', commandPayload: { argv: ['evaluate', 'accuracy'] }, idempotencyKey: 'key', lifecycleStatus: 'RUNNING' } as any} evaluationData={evaluationData} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(mockGraphqlRequest).toHaveBeenCalledWith(expect.stringContaining('CancelCommand'), { accountId: 'account-1', taskId: 'command-1' }));
  });

  it('does not render cancellation for another account or terminal command Task', async () => {
    const { rerender } = render(<TaskDisplay variant="grid" task={{ id: 'command-2', accountId: 'other', type: 'Evaluation', status: 'RUNNING', commandPayload: {}, idempotencyKey: 'key', lifecycleStatus: 'RUNNING' } as any} evaluationData={evaluationData} />);
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull();
    rerender(<TaskDisplay variant="grid" task={{ id: 'command-2', accountId: 'account-1', type: 'Evaluation', status: 'COMPLETED', commandPayload: {}, idempotencyKey: 'key', lifecycleStatus: 'SUCCEEDED' } as any} evaluationData={evaluationData} />);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull());
  });

  it('rerenders cancellation controls when realtime lifecycle state changes', async () => {
    const running = { id: 'command-3', accountId: 'account-1', type: 'Evaluation', status: 'RUNNING', commandPayload: {}, idempotencyKey: 'key', lifecycleStatus: 'RUNNING' } as any;
    const { rerender } = render(<TaskDisplay variant="grid" task={running} evaluationData={evaluationData} />);
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();

    rerender(<TaskDisplay variant="grid" task={{ ...running, lifecycleStatus: 'CANCEL_REQUESTED' }} evaluationData={evaluationData} />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancelling…' })).toBeDisabled());
  });

  it('preserves cancelled status for report command Tasks', async () => {
    render(<TaskDisplay variant="grid" task={{ id: 'command-4', accountId: 'account-1', type: 'Report', status: 'CANCELLED', commandPayload: {}, idempotencyKey: 'key', lifecycleStatus: 'CANCELLED' } as any} evaluationData={null as any} reportData={{ id: 'report-1', name: 'Report', createdAt: '2026-01-01T00:00:00Z' } as any} />);

    await waitFor(() => expect(screen.getByText('CANCELLED')).toBeInTheDocument());
  });
});
