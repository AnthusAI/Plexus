"""Step definitions for the agent documentation knowledge base feature."""

from __future__ import annotations

import os
import shutil
import tempfile

from behave import given, then, when

from plexus.documentation.repository import (
    DocumentationRepository,
    InvalidDocumentationKeyError,
)


def _write_file(root: str, relpath: str, contents: str) -> str:
    full = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(contents)
    return full


def _cleanup_root(context) -> None:
    root = getattr(context, "kb_root", None)
    if root and os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)


@given("a documentation knowledge base rooted at a temporary directory")
def step_kb_temp_root(context):
    _cleanup_root(context)
    context.kb_root = tempfile.mkdtemp(prefix="plexus-doc-kb-")
    context.repo = DocumentationRepository(context.kb_root)
    context.last_get = None
    context.last_get_error = None
    context.last_list = None
    context.last_doc_relpath = None


@given('a doc at "{relpath}" with frontmatter')
@given('a doc at "{relpath}" with frontmatter:')
def step_doc_with_frontmatter(context, relpath):
    frontmatter = context.text.strip()
    contents = "---\n" + frontmatter + "\n---\n"
    _write_file(context.kb_root, relpath, contents)
    context.last_doc_relpath = relpath


@given('that doc has body')
@given('that doc has body:')
def step_that_doc_has_body(context):
    body = context.text
    relpath = context.last_doc_relpath
    if not relpath:
        raise AssertionError("body provided without an active doc")
    full = os.path.join(context.kb_root, relpath)
    with open(full, "a", encoding="utf-8") as handle:
        handle.write(body)


@given('a non-frontmatter file at "{relpath}"')
def step_non_frontmatter_file(context, relpath):
    _write_file(context.kb_root, relpath, "# No Frontmatter\n")


@given('an index file at "{relpath}"')
def step_index_file(context, relpath):
    contents = (
        "---\n"
        "id: mcp._index\n"
        "title: MCP Namespace\n"
        "summary: index landing page\n"
        "namespace: mcp\n"
        "status: canonical\n"
        "---\n# Index\n"
    )
    _write_file(context.kb_root, relpath, contents)


@when("the documentation repository lists docs")
def step_list_docs(context):
    context.last_list = context.repo.list_docs()


@when('the documentation repository lists docs in namespace "{namespace}"')
def step_list_docs_namespace(context, namespace):
    context.last_list = context.repo.list_docs(namespace=namespace)


@when('the documentation repository gets the doc with id "{doc_id}"')
def step_get_doc(context, doc_id):
    context.last_get = None
    context.last_get_error = None
    try:
        context.last_get = context.repo.get_doc(doc_id)
    except InvalidDocumentationKeyError as exc:
        context.last_get_error = exc


@when("the documentation repository gets each related id from that response")
def step_get_related(context):
    related = context.last_get.metadata.get("related", []) or []
    context.last_related_results = {rid: context.repo.get_doc(rid) for rid in related}


@then("the response is a list of entries")
def step_response_is_list(context):
    assert isinstance(context.last_list.entries, list), context.last_list


@then("each entry exposes id, title, summary, namespace, and tags")
def step_entries_expose_fields(context):
    for entry in context.last_list.entries:
        for field in ("id", "title", "summary", "namespace", "tags"):
            assert field in entry, f"missing {field} in {entry}"


@then("the entries do not contain raw markdown bodies")
def step_entries_no_body(context):
    for entry in context.last_list.entries:
        assert "body" not in entry and "content" not in entry, entry


@then("the entries are sorted by id")
def step_entries_sorted(context):
    ids = [entry["id"] for entry in context.last_list.entries]
    assert ids == sorted(ids), ids


@then("the response contains the markdown body without the frontmatter block")
def step_get_returns_body(context):
    assert context.last_get is not None
    body = context.last_get.body
    assert body
    assert not body.lstrip().startswith("---"), body[:60]


@then("the response contains the parsed metadata")
def step_get_returns_metadata(context):
    metadata = context.last_get.metadata
    assert metadata.get("id") == "mcp.execute-tactus.overview"
    assert metadata.get("title") == "execute_tactus Overview"


@then("the response metadata includes the related ids")
def step_get_returns_related(context):
    related = context.last_get.metadata.get("related") or []
    assert "mcp.discovery" in related, related


@then("the call fails with an unsafe-key error")
def step_get_unsafe_key(context):
    assert context.last_get_error is not None, "expected an error"
    assert isinstance(context.last_get_error, InvalidDocumentationKeyError)


@then("no file outside the documentation root is read")
def step_no_external_read(context):
    assert context.last_get is None


@then("no README entries appear in the listing")
def step_no_readme(context):
    for entry in context.last_list.entries:
        assert not entry["id"].lower().endswith("readme"), entry


@then("no _index entries appear in the listing")
def step_no_index(context):
    for entry in context.last_list.entries:
        assert not entry["id"].endswith("._index"), entry


@then("every related id resolves to a doc")
def step_every_related_resolves(context):
    for rid, doc in context.last_related_results.items():
        assert doc is not None, rid
        assert doc.metadata.get("id") == rid


@then('every entry has namespace "{namespace}"')
def step_every_entry_namespace(context, namespace):
    for entry in context.last_list.entries:
        assert entry["namespace"] == namespace, entry


@then("every other namespace is omitted from the response")
def step_only_namespace(context):
    namespaces = {entry["namespace"] for entry in context.last_list.entries}
    assert len(namespaces) <= 1, namespaces


@then("the invalid file is reported as an invalid entry")
def step_invalid_reported(context):
    invalid = list(context.last_list.invalid)
    assert invalid, context.last_list.invalid


@then("valid entries are still returned alongside invalid entries")
def step_valid_alongside_invalid(context):
    assert context.last_list.entries, "expected valid entries"
    assert context.last_list.invalid, "expected invalid entries"
