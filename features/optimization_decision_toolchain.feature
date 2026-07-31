Feature: Optimization decision packet
  As a platform operator
  I want deterministic optimization decisions from frozen evidence
  So that transport adapters can report safe, auditable next actions.

  Scenario: Ranking remains stable and marks incomplete coverage
    Given eligible and ineligible score evidence with equal reviewed-error opportunity
    When the portfolio is ranked with incomplete coverage
    Then eligible scores are ordered by opportunity and the documented tie breakers
    And disabled or championless scores remain visible but unranked
    And the portfolio is not represented as exact
    And the common decision packet records retry and coverage failure evidence

  Scenario: Investment policy distinguishes evidence collection from optimization
    Given complete feedback evidence for all reachable classes
    When the Wilson disagreement bound exceeds the acceptable policy limit
    Then the decision is ready to optimize
    And a stable low-disagreement result is a monitoring candidate

  Scenario: A promotion recommendation requires all safety evidence
    Given a completed candidate with matched recent and historical regression evidence
    When class metrics, RCA artifacts, and safe improvement are present without collapse
    Then the review is promotion ready

  Scenario: Every stage has the same portable decision-packet contract
    Given an account, scope, frozen window, champion version, and feedback watermark
    When I rank, assess, diagnose, validate a batch, review, or summarize optimization evidence
    Then each result contains the common versioned decision fields

  Scenario: Alignment metric aliases exclude unusable reviewed feedback
    Given score evidence using total items, disagreements, disabled, and champion-version aliases
    When unusable or incomplete feedback pairs are declared
    Then ranking uses only valid pairs and leaves disabled scores unranked

  Scenario: Public optimizer dispatch requires explicit bounded limits and ready evidence
    Given an approved exact target with a complete ready assessment and current provenance
    When any required cost, sample, iteration, or concurrency limit is absent or invalid
    Then public run dispatch rejects the target without launching work

  Scenario: Portfolio summary retains every selected score outcome
    Given decision packets for selected scores in a chosen order
    When I summarize the portfolio
    Then the compact per-score outcomes preserve each exact scope, decision, blockers, and next action in that order
