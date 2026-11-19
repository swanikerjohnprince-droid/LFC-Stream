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
- A FastAPI control-plane API with health checks and single-admin sign-in.
- HttpOnly, 12-hour signed session cookies protecting dashboard and Drive endpoints.
- A React dashboard with sign-in, a paginated Google Drive browser, progressive video preview, destination management, and broadcast controls.
- A progressive Google Drive video proxy that forwards byte-range requests and streams response chunks without staging complete videos.
- Google OAuth authorization using the read-only Google Drive scope.
- Encrypted-at-rest storage for Google OAuth credentials and RTMP destination URLs (Fernet).
- PostgreSQL persistence for Drive connections, destinations, and broadcasts; Redis-backed OAuth state and broadcast queue.
- A cloud FFmpeg worker that reads Drive media progressively and pushes one-off H.264/AAC broadcasts to RTMP/RTMPS destinations.
- Nginx routing from the web container to the API container.

This is an early integration milestone, not a deployed or production-ready streaming service. The Drive browser, progressive video preview, encrypted RTMP destination management, one-off broadcast queue, and FFmpeg worker are implemented. Continuous folder channels, looping playlists, scheduled/recurring broadcasts, simultaneous multi-destination output, portrait profiles, and platform-specific YouTube/TikTok account APIs are still to be implemented.

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

For local development, the configured Google callback is http://localhost:8080/api/v1/auth/google/callback. Add that exact value to the OAuth client's Authorized redirect URIs. The frontend origin defaults to http://localhost:8080.

## Dashboard sign-in

The app uses a single administrator account. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and a long random `JWT_SECRET_KEY` in `.env`. The password hash format is PBKDF2-SHA256 with 310,000 iterations. Generate a hash locally with:

```bash
python - <<'PY'
import os, hashlib, base64, getpass
password = getpass.getpass('Admin password: ')
salt = os.urandom(16)
rounds = 310000
digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
encoded = base64.urlsafe_b64encode(digest).decode().rstrip('=')
print('pbkdf2_sha256

The browser receives a signed HttpOnly cookie that expires after 12 hours. Do not disable HTTPS or expose the service with default/empty authentication settings.

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

## Current broadcast limitations

- The worker currently runs one queued video broadcast at a time per worker container and outputs a landscape H.264/AAC RTMP stream.
- RTMP ingest details are entered manually. YouTube Live and TikTok LIVE eligibility, stream setup, and account-side configuration remain the account owner's responsibility.
- The current worker does not yet loop folders/playlists, schedule future starts, or fan one source out to multiple destinations.
- Stop requests are handled by the worker between incoming media chunks; a stalled upstream request can delay stop until its network timeout.

## Planned architecture

- apps/api: FastAPI control plane and authenticated Google Drive integration.
- apps/web: React + TypeScript dashboard.
- apps/worker: FFmpeg orchestration and broadcast lifecycle workers.
- packages/shared: shared API contracts and configuration where appropriate.
- PostgreSQL: persistent application state.
- Redis: job queue, locks, and worker coordination.

## Important operational notes

- Google Drive is the source library, not a guaranteed CDN. The API's video proxy forwards single byte-range requests and streams chunks with bounded memory; Google Drive throttling, transient errors, and seek limitations can still interrupt playback. The eventual FFmpeg worker must implement retries and bounded buffering rather than silently downloading entire assets.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- The current authentication model is single-admin, not multi-user. Use HTTPS in production (the session cookie is marked Secure when APP_ENV=production), keep the admin hash and JWT signing secret private, and add rate limiting before exposing the service publicly.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Security

Dashboard access is protected by a single-admin login and signed HttpOnly session cookie. Passwords are verified against a PBKDF2-SHA256 hash. OAuth tokens and RTMP ingest URLs are encrypted at rest using the configured Fernet key. OAuth state values are random, stored in Redis, expire after ten minutes, and are consumed on callback. The Google Drive integration uses read-only scope. For a public deployment, add user authentication, HTTPS, CSRF protections appropriate to the chosen auth model, audit logging, and rate limits before enabling account access.
 + str(rounds) + '

The browser receives a signed HttpOnly cookie that expires after 12 hours. Do not disable HTTPS or expose the service with default/empty authentication settings.

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

- Google Drive is the source library, not a guaranteed CDN. The API's video proxy forwards single byte-range requests and streams chunks with bounded memory; Google Drive throttling, transient errors, and seek limitations can still interrupt playback. The eventual FFmpeg worker must implement retries and bounded buffering rather than silently downloading entire assets.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- The current authentication model is single-admin, not multi-user. Use HTTPS in production (the session cookie is marked Secure when APP_ENV=production), keep the admin hash and JWT signing secret private, and add rate limiting before exposing the service publicly.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Security

Dashboard access is protected by a single-admin login and signed HttpOnly session cookie. Passwords are verified against a PBKDF2-SHA256 hash. OAuth tokens are encrypted at rest using the configured Fernet key. OAuth state values are random, stored in Redis, expire after ten minutes, and are consumed on callback. The Google Drive integration uses read-only scope. For a public deployment, add user authentication, HTTPS, CSRF protections appropriate to the chosen auth model, audit logging, and rate limits before enabling account access.
 + salt.hex() + '

The browser receives a signed HttpOnly cookie that expires after 12 hours. Do not disable HTTPS or expose the service with default/empty authentication settings.

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

- Google Drive is the source library, not a guaranteed CDN. The API's video proxy forwards single byte-range requests and streams chunks with bounded memory; Google Drive throttling, transient errors, and seek limitations can still interrupt playback. The eventual FFmpeg worker must implement retries and bounded buffering rather than silently downloading entire assets.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- The current authentication model is single-admin, not multi-user. Use HTTPS in production (the session cookie is marked Secure when APP_ENV=production), keep the admin hash and JWT signing secret private, and add rate limiting before exposing the service publicly.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Security

Dashboard access is protected by a single-admin login and signed HttpOnly session cookie. Passwords are verified against a PBKDF2-SHA256 hash. OAuth tokens are encrypted at rest using the configured Fernet key. OAuth state values are random, stored in Redis, expire after ten minutes, and are consumed on callback. The Google Drive integration uses read-only scope. For a public deployment, add user authentication, HTTPS, CSRF protections appropriate to the chosen auth model, audit logging, and rate limits before enabling account access.
 + encoded)
PY
```

The browser receives a signed HttpOnly cookie that expires after 12 hours. Do not disable HTTPS or expose the service with default/empty authentication settings.

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

- Google Drive is the source library, not a guaranteed CDN. The API's video proxy forwards single byte-range requests and streams chunks with bounded memory; Google Drive throttling, transient errors, and seek limitations can still interrupt playback. The eventual FFmpeg worker must implement retries and bounded buffering rather than silently downloading entire assets.
- YouTube and TikTok credentials and streaming permissions must be supplied by the account owner. TikTok LIVE access and external-streaming/RTMP availability depend on account eligibility and platform rules.
- “Free software” does not mean unlimited free hosting. 24/7 video encoding and outbound bandwidth require a cloud host with sufficient sustained CPU, network throughput, and storage/buffer capacity. Free tiers may throttle, reclaim, or restrict resources.
- The current authentication model is single-admin, not multi-user. Use HTTPS in production (the session cookie is marked Secure when APP_ENV=production), keep the admin hash and JWT signing secret private, and add rate limiting before exposing the service publicly.
- Never commit OAuth client secrets, refresh tokens, RTMP stream keys, or production environment files.

## Security

Dashboard access is protected by a single-admin login and signed HttpOnly session cookie. Passwords are verified against a PBKDF2-SHA256 hash. OAuth tokens are encrypted at rest using the configured Fernet key. OAuth state values are random, stored in Redis, expire after ten minutes, and are consumed on callback. The Google Drive integration uses read-only scope. For a public deployment, add user authentication, HTTPS, CSRF protections appropriate to the chosen auth model, audit logging, and rate limits before enabling account access.
