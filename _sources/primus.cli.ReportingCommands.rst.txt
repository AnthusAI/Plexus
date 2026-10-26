Report CLI commands
===================

The report CLI is implemented in the ``primus.cli.report`` package and exposed
through the top-level ``primus report`` command group.

Primary entry points:

- ``primus.cli.report.reports`` (group registration)
- ``primus.cli.report.report_commands`` (run/list/show/last/delete/purge)
- ``primus.cli.report.config_commands`` (configuration CRUD)
- ``primus.cli.report.action_items`` (action item extraction from reports)
- ``primus.cli.shared.report`` (``check-s3`` diagnostic command)

Common commands:

- ``primus report config list``
- ``primus report config show <id_or_name>``
- ``primus report config create --name "My Config" --file ./config.md``
- ``primus report config delete <id_or_name>``
- ``primus report run --config <id_or_name> [param=value ...]``
- ``primus report list``
- ``primus report show <id_or_name>``
- ``primus report last``
- ``primus report delete <id_or_name>``
- ``primus report purge --older-than <days> --limit <n>``
- ``primus report action-items [report_id]``
- ``primus report check-s3``

Notes:

- ``report run`` executes synchronously in the current process while still
  creating a Task record for progress and observability.
- Generated report content is split between ``Report.output`` (template
  markdown) and ``ReportBlock`` records (block outputs/logs/artifacts).
