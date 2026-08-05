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

  Scenario: A long execution renews both leases before completing
    Given an announced command delivery with automatic heartbeats
    And lifecycle renewal rotates the fencing token
    And an executor that fires a heartbeat, reports progress, and succeeds
    When worker "worker-one" processes the delivery
    Then lifecycle ownership is renewed before the delivery lease
    And later progress and completion use the rotated fencing token

  Scenario: Rejected lifecycle renewal cooperatively stops the execution
    Given an announced command delivery with automatic heartbeats
    And lifecycle renewal will be rejected
    And an executor that fires a heartbeat and observes ownership loss
    When worker "worker-one" processes the delivery
    Then no terminal lifecycle mutation is stored
    And the delivery is released without acknowledgement

  Scenario: Failed delivery renewal safely relinquishes lifecycle ownership
    Given an announced command delivery with automatic heartbeats
    And delivery lease renewal will fail
    And an executor that fires a heartbeat and observes ownership loss
    When worker "worker-one" processes the delivery
    Then no terminal lifecycle mutation is stored
    And the delivery is released without acknowledgement

  Scenario: Heartbeats settle before terminal completion
    Given an announced command delivery with automatic heartbeats
    And an executor that fires a heartbeat and succeeds
    When worker "worker-one" processes the delivery
    Then heartbeat scheduling stops before completion
    And no heartbeat can run after execution returns

  Scenario: The legacy Celery command worker remains available
    When the legacy Celery command modules are imported
    Then both legacy modules are importable
