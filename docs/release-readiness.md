# Release readiness

Current state of the release gates, as of 2026-11-02. Evidence lives in [test-report.md](test-report.md). This page is not a production-readiness claim: nothing has been deployed.

| Phase | Status | Open items |
|---|---|---|
| 1. Trusted baseline | Done | None |
| 2. Real-backend prediction workflow | Done | None |
| 3. Team forecast lifecycle | Done for API and UI at the fixture level | Not exercised through a browser against the real API, because the fixture season is below the 10-game minimum |
| 4. Accessibility, security, reliability | Automated work done | Manual screen-reader pass not performed. Hosted load test not run |
| 5. Deployment and operations | Prepared and rehearsed locally | Hosted deployment, NBA access from a host, off-host backups, durable bundle storage, alert delivery |

## Release blockers

1. **No hosted deployment.** No host has been chosen or authorized, so hosted smoke tests cannot run.
2. **NBA source access from a host is unknown.** Run `app.cli source-check` from the candidate host. If blocked, use the [remote worker arrangement](deployment.md#nba-source-access).
3. **Seven-day thresholds are pending.** Healthy request success of at least 99% and scheduled ingestion success of at least 95% need seven days of a running deployment.
4. **The worker is not supervised anywhere yet.** While it is stopped, nothing syncs and nothing is scored. Compose restarts it once deployed.
5. **The manual screen-reader pass has not been done.** See the [checklist](accessibility-report.md#manual-screen-reader-checklist).
6. **Model bundles have no durable home.** See [Model artifacts](deployment.md#model-artifacts).
7. **Forecasts are slow under load.** About 10 per second with seconds of latency at 20 concurrent clients on the development machine. Measure on the real host before setting final limits.

## Known limits

- Rate limit counts are per API process, so run one process or lower the limits.
- The per-client limit depends on the edge proxy overwriting `X-Forwarded-For`.
- The career backfill is partial and resumes when re-run; the source refuses long runs.
