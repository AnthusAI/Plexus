Feature: Programmatic detector Score

  Scenario: YAML class resolves
    Given a score YAML whose class names SourceSpanOverlapScore
    When the scorecard loads that score
    Then predict() runs that class
    And Tactus is not used

  Scenario: Overlapping finding is Yes
    Given an Item for a file and line span
    And findings that overlap that span
    When I score that Item
    Then the prediction is Yes

  Scenario: No overlapping finding is No
    Given an Item for a file present in the scan inventory
    And findings that do not overlap that span
    When I score that Item
    Then the prediction is No

  Scenario: Wrong file is not a hit
    Given an Item for file src/a.ts lines 10-12
    And a finding on src/b.ts with overlapping line numbers
    When I score that Item
    Then the prediction is No

  Scenario: Snippet text is not the scan input
    Given an Item whose text would match a naive keyword
    And findings that do not overlap the Item span
    When I score that Item
    Then the prediction is No
