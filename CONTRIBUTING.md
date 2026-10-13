# Contributing

Start with [architecture](docs/ARCHITECTURE.md). Changes should keep provider
adapters, departure decisions, HTTP validation and browser views separate.

```sh
make setup
make dev
make check
make browser
```

Python 3.10+ and Node 22+ are the verification targets. `make check` runs pytest,
Node tests, Ruff lint/format checks, Python compilation, JS syntax and shell syntax.
`make browser` runs isolated Chromium checks without live provider billing.
Use `make format` to apply Python formatting/import cleanup. Equivalent Python
commands are available in [setup](docs/SETUP.md) if Make is unavailable.

Add a regression for changes affecting forecast trust, provider failures,
configuration persistence, notifications or asynchronous browser state. Use mocks
at provider/network boundaries; keep the real parser/evaluator/HTTP pipeline in
the test. Demo data belongs only in `services/demo.py` and explicit demo mode.

`make live` is an opt-in integration check that uses configured provider quota.
It does not save a commute or send notifications. Live checks belong outside CI;
credentials, telemetry, notification state, logs and scratch experiments must
never be committed. See `.gitignore` and `config.json.example`.

Third-party Leaflet source is bundled under `web/vendor/leaflet`, with its license.
No repository-wide license has been chosen for the original code or scenery assets.
