Feature: Drainable command worker service
  A warm command worker waits for deliveries and drains without abandoning work.

  Scenario: An idle service receives and completes one command, then continues waiting
    Given a command service with one delivery followed by an empty receive
    When the command service runs until drained
    Then one delivery is processed successfully
    And the service receives again after completing the command

  Scenario: A drain request while idle exits without receiving more work
    Given a command service whose idle wait requests drain
    When the command service runs until drained
    Then the service exits without a second receive

  Scenario: A drain request during active execution lets that command settle and prevents a second receive
    Given a command service whose active execution requests drain
    When the command service runs until drained
    Then the active delivery settles successfully
    And the service does not receive a second delivery

  Scenario: A drain request after receive but before execution releases the delivery without running it
    Given a command service that observes drain after receiving a delivery
    When the command service runs until drained
    Then the untouched delivery is released without acknowledgement
    And the received delivery is not processed

  Scenario: Empty receives use the configured idle wait rather than tight-looping
    Given a command service with an empty receive
    When the command service runs until drained
    Then the configured idle wait is used once
