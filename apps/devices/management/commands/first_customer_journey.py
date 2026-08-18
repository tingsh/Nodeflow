import json

from django.core.management.base import BaseCommand, CommandError

from apps.devices.first_customer_journey import (
    CREATED_BY,
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_TIMEOUT_SECONDS,
    FirstCustomerJourneyError,
    FirstCustomerJourneyRunner,
    assert_safe_deployment_mode,
    cleanup_owned_runs,
    cleanup_test_run,
    generate_test_run_id,
    validate_test_run_id,
)


class Command(BaseCommand):
    help = "Run or safely clean up the automated first-customer journey canary."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["run", "cleanup"])
        parser.add_argument("--test-run-id", help="Exact fcj_<timestamp>_<random> identifier.")
        parser.add_argument(
            "--created-by",
            help=f"Cleanup selector; only the exact value {CREATED_BY!r} is accepted.",
        )
        parser.add_argument(
            "--include-unexpired",
            action="store_true",
            help="With --created-by, also clean unexpired FCJ runs. Exact-run cleanup is safer for active failures.",
        )
        parser.add_argument(
            "--ingestion-mode",
            choices=["mqtt", "service"],
            default="mqtt",
            help="mqtt exercises broker/consumer/Redis/Celery; service is a deterministic software-only fallback.",
        )
        parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
        parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
        parser.add_argument(
            "--cleanup-on-failure",
            action="store_true",
            help="Delete run-owned records on assertion/ingestion failure instead of retaining them for 24 hours.",
        )

    def handle(self, *args, **options):
        try:
            assert_safe_deployment_mode()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        if options["action"] == "cleanup":
            return self._cleanup(options)
        return self._run(options)

    def _run(self, options):
        if options["created_by"] or options["include_unexpired"]:
            raise CommandError("--created-by and --include-unexpired are cleanup-only options.")
        try:
            test_run_id = validate_test_run_id(options["test_run_id"] or generate_test_run_id())
            runner = FirstCustomerJourneyRunner(
                test_run_id=test_run_id,
                ingestion_mode=options["ingestion_mode"],
                sample_count=options["sample_count"],
                timeout_seconds=options["timeout_seconds"],
                cleanup_on_failure=options["cleanup_on_failure"],
                progress=self.stdout.write,
            )
            result = runner.run()
        except (ValueError, RuntimeError) as exc:
            if isinstance(exc, FirstCustomerJourneyError):
                failure = {
                    "status": "failed",
                    "test_run_id": exc.test_run_id,
                    "stage": exc.stage,
                    "preserved": exc.preserved,
                    "error": str(exc),
                }
                self.stderr.write(json.dumps(failure, sort_keys=True))
                if exc.preserved:
                    self.stderr.write(
                        f"Cleanup: python manage.py first_customer_journey cleanup --test-run-id {exc.test_run_id}"
                    )
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(result, sort_keys=True))
        return None

    def _cleanup(self, options):
        test_run_id = options["test_run_id"]
        created_by = options["created_by"]
        if bool(test_run_id) == bool(created_by):
            raise CommandError("Cleanup requires exactly one of --test-run-id or --created-by.")
        if test_run_id:
            try:
                result = {
                    "test_run_id": validate_test_run_id(test_run_id),
                    "cleanup": cleanup_test_run(test_run_id),
                }
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        else:
            try:
                result = cleanup_owned_runs(
                    created_by=created_by,
                    include_unexpired=options["include_unexpired"],
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
        return None
