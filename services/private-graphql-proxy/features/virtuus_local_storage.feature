Feature: File-backed local GraphQL storage
  Scenario: Create and read an Item with no database server
    Given a local GraphQL process configured for Virtuus file storage
    And no database server is running
    When I create an Item through GraphQL
    Then I can read that Item through GraphQL
    And a JSON file on disk contains the Item document

  Scenario: Records survive a FastAPI restart
    Given Items stored as Virtuus files
    When the FastAPI process restarts
    Then those records are still available through GraphQL

  Scenario: Composite Identifier roundtrip persists on disk
    Given a local GraphQL process configured for Virtuus file storage
    When I create an Identifier through GraphQL
    Then I can read that Identifier through GraphQL
    And a JSON file on disk contains the Identifier document
