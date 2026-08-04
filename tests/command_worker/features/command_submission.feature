Feature: Portable command submission
  Authenticated adapters can announce and inspect commands without coupling the
  application contract to a transport or deployment provider.

  Scenario: A valid submission announces one discoverable command
    Given a portable command service
    When tenant "tenant-one" submits command "evaluate" with idempotency key "request-one"
    Then a new announced command is returned
    And exactly one dispatch is discoverable for the command

  Scenario: An identical submission is idempotent
    Given a portable command service
    When tenant "tenant-one" submits command "evaluate" with idempotency key "request-one"
    And tenant "tenant-one" repeats the identical submission
    Then the original command is returned as existing
    And exactly one dispatch is discoverable for the command

  Scenario Outline: Reusing an idempotency key for different work conflicts
    Given a portable command service
    And tenant "tenant-one" submitted command "evaluate" with idempotency key "request-one"
    When the same tenant reuses that key with a different <difference>
    Then the submission reports an idempotency conflict

    Examples:
      | difference |
      | payload    |
      | target     |

  Scenario: Idempotency keys are independent between tenants
    Given a portable command service
    When tenant "tenant-one" submits command "evaluate" with idempotency key "shared-key"
    And tenant "tenant-two" submits command "evaluate" with idempotency key "shared-key"
    Then both tenants receive different new commands

  Scenario: Idempotency keys are independent between principals in one tenant
    Given a portable command service
    When principal "principal-one" submits a command for tenant "tenant-one" with key "shared-key"
    And principal "principal-two" submits a command for tenant "tenant-one" with key "shared-key"
    Then both principals receive different new commands

  Scenario: Wrong-tenant access does not disclose a command
    Given a portable command service
    And tenant "tenant-one" submitted command "evaluate" with idempotency key "request-one"
    When tenant "tenant-two" gets and cancels that command
    Then both operations report the same not-found behavior

  Scenario: Cancelling announced work prevents dispatch
    Given a portable command service
    And tenant "tenant-one" submitted command "evaluate" with idempotency key "request-one"
    When tenant "tenant-one" cancels the command
    Then the command is cancelled
    And no dispatch is discoverable for the command

  Scenario: A delivery published before cancellation cannot execute
    Given a portable command service
    And tenant "tenant-one" submitted command "evaluate" with idempotency key "request-one"
    When the command is cancelled before its earlier delivery is processed
    Then the late delivery is acknowledged without execution

  Scenario: A delivery that does not match durable command state is quarantined
    Given a portable command service
    And tenant "tenant-one" submitted command "evaluate" with idempotency key "request-one"
    When a delivery with a changed payload is processed
    Then the mismatched delivery is quarantined without execution

  Scenario: Cancelling running work requests cooperative cancellation
    Given a portable command service
    And tenant "tenant-one" has a running command
    When tenant "tenant-one" cancels the command twice
    Then cancellation is requested without status regression

  Scenario Outline: Cancelling terminal work preserves its status
    Given a portable command service
    And tenant "tenant-one" has a <status> command
    When tenant "tenant-one" cancels the command
    Then the command remains <status>

    Examples:
      | status    |
      | succeeded |
      | failed    |
      | cancelled |
