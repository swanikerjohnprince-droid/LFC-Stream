# LFC Stream

A cloud-hosted video broadcasting platform that uses Google Drive as its media library and FFmpeg-based workers to deliver scheduled and continuous live streams to supported destinations such as YouTube Live and TikTok LIVE.

## Project goals

- Run entirely in the cloud; no user's local machine is required during broadcasts.
- Browse and select videos from Google Drive using secure OAuth authorization.
- Stream media progressively from Google Drive through a bounded server-side buffer rather than requiring a full pre-download.
- Support scheduled broadcasts, playlists, looping, and continuous channels.
- Support multiple destinations, with independent output profiles where required.
- Provide broadcast status, logs, health monitoring, and recovery controls.

## Current development status

The repository now includes:
- A FastAPI control-plane API with health checks.
- A React dashboard with a Google Drive connection screen and media browser.
- Google OAuth authorization using the read-only Google Drive scope.
- Encrypted-at-rest storage for the Google OAuth credential bundle (Fernet).
- PostgreSQL persistence for the Drive connection and Redis-backed, expiring OAuth state.
- Nginx routing from the web container to the API container.

This is an early integration milestone, not a deployed or production-ready streaming service. Video selection, progressive media delivery, FFmpeg workers, destinations, schedules, and 24/7 channel execution are still to be implemented.

## Local setup

1. Install Docker Desktop (or Docker Engine with the Compose plugin).
2. Copy .env.example to .env.
3. Generate a Fernet key and place it in TOKEN_ENCRYPTION_KEY:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Create a Google OAuth client (instructions below) and fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI.
5. Set a strong, unique POSTGRES_PASSWORD in .env.
6. Start the stack:

   ```bash
   docker compose up --build
   ```

7. Open http://localhost:8080. The API health endpoint is http://localhost:8000/health.

For local development, the configured Google callback is http://localhost:8000/api/v1/auth/google/callback. Add that exact value to the OAuth client's Authorized redirect URIs. The frontend origin defaults to http://localhost:8080.

## Google Cloud OAuth setup

1. In Google Cloud Console, create or select a project.
2. Enable the Google Drive API.
3. Configure the OAuth consent screen. While the app is in Testing, add the Google account you will use as a test user.
4. Create an OAuth client ID with application type Web application.
5. Add the callback URI from GOOGLE_REDIRECT_URI to Authorized redirect URIs.
6. Copy the client ID and client secret into the server-side .env file. Never put these values in frontend code or commit .env.
7. Start LFC Stream and choose Media library → Connect Google Drive.

The app requests the drive.readonly scope. It can read and list Drive content but cannot edit or delete your files. Google may display an unverified-app warning until the OAuth consent configuration and verification requirements for your deployment are completed.

## Environment variables

- DATABASE_URL: PostgreSQL connection string.
- REDIS_URL: Redis connection string used for short-lived OAuth state.
- FRONTEND_ORIGIN: browser origin used after OAuth completes.
- GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET: server-side OAuth client credentials.
- GOOGLE_REDIRECT_URI: exact callback URI registered in Google Cloud.
- TOKEN_ENCRYPTION_KEY: Fernet key used to encrypt OAuth credentials before database storage.
- POSTGRES_PASSWORD: strong database password used by Docker Compose.

Back up the encryption key securely. If it is lost, stored Google credentials cannot be decrypted and the Drive account will need to be connected again. Rotating the key requires a planned credential re-encryption migration.

## Planned architecture

- apps/api: FastAPI control plane and authenticated Google Drive integration.
- apps/web: React + TypeScript dashboard.
- apps/worker: FFmpeg orchestration and broadcast lifecycle workers.
- packages/shared: shared API contracts and configuration where appropriate.
- PostgreSQL: persistent application state.
- Redis: job queue, locks, and worker coordination.

## Important operational notes

- Google Drive is the source library, not a guaranteed CDN. The worker must handle authenticated range requests, throttling, transient errors, and seek limitations. A bounded temporary buffer may be used for reliability; the system must not silently download an entire asset before playback.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- This initial dashboard does not yet authenticate individual LFC Stream users. Do not expose it publicly until application login, HTTPS, access controls, and deployment secrets management are added.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Security

OAuth tokens are encrypted at rest using the configured Fernet key. OAuth state values are random, stored in Redis, expire after ten minutes, and are consumed on callback. The Google Drive integration uses read-only scope. For a public deployment, add user authentication, HTTPS, CSRF protections appropriate to the chosen auth model, audit logging, and rate limits before enabling account access.
