import { activityConfig } from './activity';

describe('activity command actions', () => {
  it('exposes only registered structured dispatch actions', () => {
    const dispatchActions = activityConfig.actions.filter((action) => action.actionType !== 'ui');

    expect(dispatchActions.map((action) => action.name)).toEqual(['Evaluate Accuracy']);
    expect(dispatchActions.every((action) => 'action' in action && Boolean(action.action))).toBe(true);
  });
});
