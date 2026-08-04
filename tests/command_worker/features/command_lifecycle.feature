Feature: Portable command lifecycle
  The command worker coordinates durable lifecycle state with broker delivery
  without depending on a particular cloud or queue implementation.

  Scenario: A command completes before its delivery is acknowledged
    Given an announced command delivery
    And an executor that reports 50 percent progress and succeeds
    When worker "worker-one" processes the delivery
    Then the command is executed once
    And progress of 50 percent is stored
    And completion is stored before the delivery is acknowledged

  Scenario: An active lease prevents concurrent execution
    Given an announced command delivery
    And worker "worker-one" holds an active lease for the command
    When worker "worker-two" processes a duplicate delivery
    Then the command is not executed
    And the duplicate delivery is released for retry

  Scenario: A completed duplicate is absorbed
    Given an announced command delivery
    And the command has already completed
    When worker "worker-two" processes a duplicate delivery
    Then the command is not executed
    And the duplicate delivery is acknowledged

  Scenario: A failed terminal duplicate is absorbed
    Given an announced command delivery
    And the command has already failed
    When worker "worker-two" processes a duplicate delivery
    Then the command is not executed
    And the duplicate delivery is acknowledged

  Scenario: A superseded lease fences the stale worker
    Given worker "worker-one" claimed an announced command
    And its lease expired
    And worker "worker-two" claimed the command
    When the stale worker reports progress and completes
    Then both stale lifecycle mutations are rejected
    And worker "worker-two" remains the lease owner

  Scenario: The legacy Celery command worker remains available
    When the legacy Celery command modules are imported
    Then both legacy modules are importable
