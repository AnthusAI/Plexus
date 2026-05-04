Feature: Frontmatter-aware documentation knowledge base

  Plexus exposes its agent-facing documentation as a knowledge base that
  agents can discover and load incrementally. Each document carries YAML
  frontmatter describing identity, summary, namespace, status, and related
  topics. The knowledge base is consumed by `plexus.docs.list` and
  `plexus.docs.get` in the `execute_tactus` runtime.

  Background:
    Given a documentation knowledge base rooted at a temporary directory
    And a doc at "mcp/execute-tactus.md" with frontmatter:
      """
      id: mcp.execute-tactus.overview
      title: execute_tactus Overview
      summary: How agents call the single execute_tactus tool.
      namespace: mcp
      status: canonical
      disclosure: overview
      tags: [mcp, tactus]
      related:
        - mcp.discovery
      """
    And that doc has body:
      """
      # execute_tactus Overview

      Use the single tool.
      """
    And a doc at "mcp/discovery.md" with frontmatter:
      """
      id: mcp.discovery
      title: Discovery
      summary: How to enumerate available APIs and docs.
      namespace: mcp
      status: canonical
      disclosure: reference
      tags: [mcp, discovery]
      """
    And that doc has body:
      """
      # Discovery

      Use api_list and docs_list.
      """

  Scenario: Listing docs returns metadata summaries
    When the documentation repository lists docs
    Then the response is a list of entries
    And each entry exposes id, title, summary, namespace, and tags
    And the entries do not contain raw markdown bodies
    And the entries are sorted by id

  Scenario: Getting a doc by canonical id returns metadata and content
    When the documentation repository gets the doc with id "mcp.execute-tactus.overview"
    Then the response contains the markdown body without the frontmatter block
    And the response contains the parsed metadata
    And the response metadata includes the related ids

  Scenario: Unsafe keys are rejected
    When the documentation repository gets the doc with id "../../etc/passwd"
    Then the call fails with an unsafe-key error
    And no file outside the documentation root is read

  Scenario: README and _index files are excluded from the agent index
    Given a non-frontmatter file at "mcp/README.md"
    And an index file at "mcp/_index.md"
    When the documentation repository lists docs
    Then no README entries appear in the listing
    And no _index entries appear in the listing

  Scenario: Related ids resolve through the same get API
    When the documentation repository gets the doc with id "mcp.execute-tactus.overview"
    And the documentation repository gets each related id from that response
    Then every related id resolves to a doc

  Scenario: Listing supports filtering by namespace
    When the documentation repository lists docs in namespace "mcp"
    Then every entry has namespace "mcp"
    And every other namespace is omitted from the response

  Scenario: Documents missing required frontmatter are surfaced as invalid
    Given a non-frontmatter file at "mcp/no-frontmatter.md"
    When the documentation repository lists docs
    Then the invalid file is reported as an invalid entry
    And valid entries are still returned alongside invalid entries
