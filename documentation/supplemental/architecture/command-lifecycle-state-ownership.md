# Command lifecycle and dashboard state ownership

## Decision

Plexus command execution has one authoritative lifecycle model and one
dashboard-facing task view. They are separate logical models. A deployment may
store them in the same database, but a dashboard task is not the authority for
lease ownership, idempotency, retry, or cancellation.

The command lifecycle is portable Plexus domain state. The dashboard task is a
projection for user-facing stages, output, subscriptions, and navigation.

## Why this decision is needed

Long-running commands are delivered at least once. A worker can be stopped,
its broker delivery can be retried, and a cancellation can race with execution.
The authoritative record must therefore support all of the following together:

- a request-scoped idempotency key;
- an immutable request digest;
- an expiring owner lease;
- a monotonically increasing fencing token;
- fenced progress and terminal mutations;
- cooperative cancellation; and
- a terminal result that survives worker or broker failure.

The current dashboard `Task` record is a UI model. Its AWS dispatcher does use
a conditional `PENDING -> DISPATCHING` update, which prevents a simple
double-dispatch race. It does not provide the complete lifecycle contract
above. In particular, it has no durable fencing token or renewable execution
lease, and its local dispatcher does not perform the same conditional claim.

Adding those worker concerns directly to the dashboard schema would make
execution safety depend on the dashboard API and its storage implementation.
That would couple the command engine to Amplify in AWS and make a Kubernetes
implementation carry dashboard-specific behavior.

## Alternatives considered

### 1. Make dashboard `Task` authoritative

This is the fewest-record option. It would require extending the task schema
and every task-store implementation with the complete lifecycle contract.

It is rejected for the command platform because it conflates UI evolution with
worker correctness and makes the command engine depend on the dashboard
control-plane provider. The conditional AWS dispatch claim alone is not a
substitute for leases and fencing.

### 2. Dedicated command state plus dashboard projection

This keeps the execution model provider-neutral. A deployment implements the
command repository, delivery adapter, and a reliable state-change feed; the
dashboard consumes the resulting state as a view.

This is the selected logical design. Its cost is explicit: dashboard status is
eventually consistent and a projection consumer must be operated and observed.
That cost is justified only because it prevents duplicate execution and stale
workers from mutating terminal state while leaving the dashboard free to evolve
as a UI model.

### 3. One physical database, separate logical schemas

This is a deployment form of option 2, not a different domain design. For
example, a Kubernetes deployment can place `command_state` and dashboard task
tables in one transactional database and use a transactional outbox for the
projection feed. It preserves the same ownership boundary without requiring
two managed database products.

## Deployment mapping

| Concern | AWS implementation | Kubernetes implementation |
| --- | --- | --- |
| Authoritative lifecycle | Command-state table | Command-state schema/table |
| Delivery | Celery with an AWS broker adapter | Celery with the selected broker adapter |
| State-change feed | Table stream | Transactional outbox or database change feed |
| Dashboard projection | Independent projection consumer | Independent projection consumer |
| Dashboard task view | Amplify task model | Local/dashboard task model |

The command-worker core must depend only on its lifecycle, delivery, and
projection contracts. It must not import an AWS stream, an Amplify task model,
or a Kubernetes client.

## Projection rules

- A projector consumes only durable state transitions; a worker never marks a
  dashboard task terminal before the authoritative transition succeeds.
- Projection delivery is idempotent and retryable.
- Dashboard projection failure does not retry command execution.
- Progress and terminal state expose the command identifier so operators can
  reconcile a UI task with its authoritative record.
- The dashboard must clearly tolerate the brief period between a durable
  command update and its projected UI update.

## Reconsideration criteria

Revisit this decision only if all supported deployment targets can provide the
full lifecycle contract atomically through the dashboard task store without
binding the command engine to dashboard-specific APIs. Until then, removing the
boundary would trade a visible projection component for hidden correctness
coupling.

## Required validation before adoption

1. Submit the same command concurrently and verify one execution.
2. Kill a worker during execution and verify a replacement cannot write stale
   progress or terminal state.
3. Request cancellation during execution and verify the durable result is
   cancelled before the dashboard reflects it.
4. Force projection delivery failure and verify it retries without rerunning
   the command.
5. Run the same contract tests against the AWS and Kubernetes adapters.
