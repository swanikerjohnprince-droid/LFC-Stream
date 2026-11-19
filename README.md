# LFC Stream

A cloud-hosted video broadcasting platform that uses Google Drive as its media library and FFmpeg-based workers to deliver scheduled and continuous live streams to supported destinations such as YouTube Live and TikTok LIVE.

## Project goals

- Run entirely in the cloud; no user's local machine is required during broadcasts.
- Browse and select videos from Google Drive using secure OAuth authorization.
- Stream media progressively from Google Drive through a bounded server-side buffer rather than requiring a full pre-download.
- Support scheduled broadcasts, playlists, looping, and continuous channels.
- Support multiple destinations, with independent output profiles where required.
- Provide broadcast status, logs, health monitoring, and recovery controls.

## Important operational notes

- Google Drive is the source library, not a guaranteed CDN. The worker must handle authenticated range requests, throttling, transient errors, and seek limitations. A bounded temporary buffer may be used for reliability; the system must not silently download an entire asset before playback.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Planned architecture

- `apps/api`: FastAPI control plane and authenticated Google Drive integration.
- `apps/web`: React + TypeScript dashboard.
- `apps/worker`: FFmpeg orchestration and broadcast lifecycle workers.
- `packages/shared`: shared API contracts and configuration where appropriate.
- PostgreSQL: persistent application state.
- Redis: job queue, locks, and worker coordination.

## Development status

Initial repository setup. The first milestone is a deployable control-plane skeleton with health checks and a dashboard shell. Google OAuth and actual broadcast workers will be added in subsequent milestones.

## Security

Use environment variables or a secrets manager for all credentials. OAuth tokens must be encrypted at rest. Stream keys must be write-only in the UI after creation and must never appear in logs. Restrict dashboard access and validate all destination URLs to prevent server-side request forgery.
