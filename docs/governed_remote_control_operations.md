# Governed Remote Control — Security and Operations

## Safety boundary

Remote control is supervisory, not a safety instrumented system. Novena never replaces equipment-rated interlocks, emergency stops, overload protection, local Hand/Off/Auto selectors, or lockout/tagout. The customer appoints a qualified controls professional to define site-specific commissioned limits. Customer policy may narrow, but never widen, Novena's verified technical definition or the commissioned envelope.

Control is monitoring-only by default. Time in service does not activate it. Readiness requires representative monitoring evidence, exact identity, supported Gateway protocol, trusted time, durable journal storage, an acknowledged signed edge policy, commissioning evidence, MFA, and explicit exact-key activation by a customer administrator.

## Protocol and dispatch contract

State-changing dispatch requires schema version `1` and the Gateway-advertised capabilities `governed_commands_v1`, `local_writeback_v1`, `lifecycle_stages_v1`, and `idempotent_replay_v1`. The signed envelope carries one request ID, command ID, idempotency key, canonical Gateway serial, and—for field writes—one canonical device ID and command key. Gateways without that complete advertisement remain telemetry/diagnostic compatible but are command-ineligible.

The transactional outbox is recovered independently by Celery Beat every five seconds. Workers lease rows before publishing; expired leases are recoverable, pre-ack failures use bounded exponential backoff, exhausted work moves to dead letter, and an ambiguous broker acknowledgement is recorded as outcome-unknown instead of blindly retried. Configure the lease and retry bounds with the `REMOTE_CONTROL_OUTBOX_*` settings in the production environment example.

Lifecycle evidence keeps request acceptance, broker acknowledgement, Gateway receipt, execution start, field-protocol acceptance, verified field execution, and OTA initiation distinct. Only allowlisted Gateway stages advance execution state; OTA initiation is never recorded as verified execution.

## Threat model

| Threat | Required control |
| --- | --- |
| Stolen session | Dedicated permissions, site scope, recent authentication, MFA, separate approver |
| Unsafe value | Type/unit/enum/range/delta/cooldown checks at Hub and Gateway |
| Raw/misdirected write | Canonical device ID and exact commissioned key mapping |
| MQTT tampering | Ed25519 signature, key ID, target and immutable revision checksums |
| Replay/duplicate | Epoch, per-device sequence, idempotency ID and durable result replay |
| Crash during execution | Journal before connector call; uncertain execution never repeats |
| Stale restore/policy | Monotonic epoch, retained acknowledgement and recovery epoch increment |
| Compromised key | Active/next overlap, revocation, global kill and recommissioning |
| AI/automation bypass | AI templates remain unverified; automations create proposals only |
| Evidence loss/leak | Redaction, immutable actor snapshots, retention and legal holds |

## Key rotation and revocation

1. Generate Ed25519 keys in managed secrets; never store private material in the database/repository.
2. Deploy the new public key as `next` while the old key remains active.
3. Verify every commissioned Gateway reports the current policy revision and epoch.
4. Change `REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID` and `REMOTE_CONTROL_SIGNING_KEYS`.
5. Republish and verify policies, then retire the old key.
6. For compromise, add the old ID to Gateway `revoked_command_key_ids`, run the global reset, increment epochs and require re-acknowledgement.

## Restore and incident procedure

After any Hub restore, stop Celery/MQTT command dispatch and run `disaster_recovery_control_reset`. It cancels restored approvals/outbox work, suspends activations, locks teams and increments epochs. Republish policies and wait for Gateway acknowledgement. Never resend a pending or uncertain command.

For an incident:

1. Emergency-disable the narrowest safe scope; use global kill if scope is uncertain.
2. Confirm immediate Hub block, then Gateway epoch acknowledgement.
3. Preserve command, approval, event, transport, Gateway journal, broker and field evidence; apply legal holds.
4. Determine equipment state locally—not from MQTT publication.
5. Classify every result as verified, not applied or unresolved. Never repeat unresolved work.
6. Correct policy/template/interlock/key issues, recommission material changes, and reactivate exact keys.

## Per-command failure analysis

Record command/idempotency IDs, epoch/sequence, actor and approver snapshots, MFA/re-auth evidence, all revisions/checksums, requested/normalized/encoded/preflight/readback values and units, broker acknowledgement, Gateway receipt/journal/connector/protocol/verification evidence, local authority/interlocks, final outcome, containment, notification, corrective action and recommissioning decision.

## Customer responsibilities and production gate

Customers provide qualified commissioners/approvers and equipment documents; validate limits/interlocks; maintain local safety systems, time, network and storage; train operators; review audits; test emergency disable; report material changes; and recommission annually. Novena provides governance/evidence but does not certify machinery safety.

Production readiness must fail for placeholder signing keys, controlled teams without acknowledged current-epoch policy, unsafe defaults, unsupported Gateway versions, unhealthy clock/journal/storage, or untested recovery. Physical CM4 and representative VFD/pump/chiller acceptance is mandatory before ready-for-review.
