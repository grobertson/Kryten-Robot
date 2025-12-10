## What's Changed

- chore: update VERSION file to 0.6.0 (7f15224)
- chore: bump version to 0.6.0 and simplify CI tests (0e60031)
- chore: bump version to 0.5.5 (c0b7415)
- ci: remove environment approval requirement for PyPI trusted publishing (cf5797f)
- fix: clear PYTHONPATH in all startup scripts to prevent import conflicts (c71f8d4)
- fix: update start scripts to use --config flag (2e541d8)
- feat: support default config paths for deployment (b67974c)
- fix: correctly extract last_event_time/type from stats dicts (052b71b)
- fix: use ApplicationState.shutdown_event consistently to enable system.shutdown (a618a1e)
- fix: improve delay_seconds validation in system.shutdown (7cf966b)
- feat: implement system.shutdown and system.reload handlers (4dc8902)
- fix: correct logging config attributes in system.config handler (c6fd31c)
- feat: implement system.stats, system.config, and system.ping handlers (3b37552)
- test: add Phase 1 instrumentation integration test (7ae3e5c)
- feat: add sophisticated state counting with configurable filtering (bfdb311)
- feat: add psutil dependency for memory stats (469058f)
- feat: create ApplicationState class for shared runtime state (08ffbbd)
- feat: add connection tracking to NatsClient (connected_since, reconnect_count, connected_url) (fdcb9ba)
- feat: add connection tracking to CytubeConnector (connected_since, reconnect_count, last_event_time) (166078e)
- feat: add StatsTracker and success counter to CommandSubscriber (5d3fab2)
- feat: add StatsTracker to EventPublisher for rate calculation (0ee07d3)
- feat: add StatsTracker class for rate calculation and time-windowed statistics (e786dd6)

**Full Changelog**: https://github.com/grobertson/Kryten-Robot/compare/v0.5.4...v0.6.0

