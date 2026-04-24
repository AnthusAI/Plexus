Report CLI commands
===================

The report CLI is implemented in the ``plexus.cli.report`` package and exposed
through the top-level ``plexus report`` command group.

Primary entry points:

- ``plexus.cli.report.reports`` (group registration)
- ``plexus.cli.report.report_commands`` (run/list/show/last/delete/purge)
- ``plexus.cli.report.config_commands`` (configuration CRUD)
- ``plexus.cli.report.action_items`` (action item extraction from reports)
- ``plexus.cli.shared.report`` (``check-s3`` diagnostic command)

Common commands:

- ``plexus report config list``
- ``plexus report config show <id_or_name>``
- ``plexus report config create --name "My Config" --file ./config.md``
- ``plexus report config delete <id_or_name>``
- ``plexus report run --config <id_or_name> [param=value ...]``
- ``plexus report list``
- ``plexus report show <id_or_name>``
- ``plexus report last``
- ``plexus report delete <id_or_name>``
- ``plexus report purge --older-than <days> --limit <n>``
- ``plexus report action-items [report_id]``
- ``plexus report check-s3``

Notes:

- ``report run`` executes synchronously in the current process while still
  creating a Task record for progress and observability.
- Generated report content is split between ``Report.output`` (template
  markdown) and ``ReportBlock`` records (block outputs/logs/artifacts).
