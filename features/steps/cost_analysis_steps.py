from behave import given, then, when
from unittest.mock import MagicMock

from plexus.reports.blocks.cost_analysis import CostAnalysis


@given("score results with costs and item IDs")
def step_given_score_results_with_costs(context):
    context.results = [
        {"itemId": "i1", "cost": {"total_cost": "0.40"}},
        {"itemId": "i1", "cost": {"total_cost": "0.10"}},
        {"itemId": "i2", "cost": {"total_cost": "0.50"}},
        {"itemId": "i3", "cost": {}},
        {"cost": {"total_cost": "0.20"}},
    ]


@when("I compute cost analysis item stats")
def step_when_i_compute_item_stats(context):
    api_client = MagicMock()
    api_client.account_id = "test-account-id"
    block = CostAnalysis(
        config={}, params={"account_id": "acct"}, api_client=api_client
    )
    context.item_analysis = block._compute_item_analysis(
        results=context.results,
        total_cost_str="1.00",
        total_calls_str="10",
    )


@then("the item count is {expected_count:d}")
def step_then_item_count(context, expected_count):
    assert context.item_analysis["count"] == expected_count


@then("the average cost per item is {expected_avg_cost:f}")
def step_then_average_cost(context, expected_avg_cost):
    assert context.item_analysis["average_cost"] == expected_avg_cost
