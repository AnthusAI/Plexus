Feature: Cost analysis report block

  Scenario: Compute unique item stats from score results
    Given score results with costs and item IDs
    When I compute cost analysis item stats
    Then the item count is 2
    And the average cost per item is 0.5
