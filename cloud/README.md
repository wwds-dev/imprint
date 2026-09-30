# Reading Compass cloud companion

Current account setup and blockers are tracked in
[DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md). The dedicated Google Cloud
project is `imprint-audiobooks`; the existing Netlify site is
`reading-compass-private`.

This is the hosted web version of Imprint's audiobook agent. It serves a
mobile-friendly Convert and Listen app at `/cloud/app`; the Reading Compass
dashboard links to it. The web service handles
Google sign-in, queues one Cloud Run Job per ebook, lists and streams MP3s, and
stores progress in the same Drive sidecar format used by Imprint. The worker
imports Imprint's existing `services.narrator.converter` module. The Mac can be
off after the service is deployed.

## Required Google Cloud resources

1. A Google Cloud project with billing, Drive API, Firestore Native mode, Cloud
   Run API, Cloud Build and Artifact Registry enabled.
2. An OAuth web client. Add
   `https://reading-compass-private.netlify.app/cloud/auth/callback` as an
   authorized redirect URI. Restrict the OAuth app to the owner's Google
   account. This app currently requests the full Drive scope because it must
   read books already in `My Drive/ebooks` and write into an existing
   `My Drive/audiobooks - gdrive` folder. Review Google's OAuth consent and
   verification requirements before production use. Google says OAuth test-user
   authorizations expire after seven days, including offline refresh tokens;
   a durable setup must address the app's production publishing requirements.
3. A Cloud Run web service and a Cloud Run Job built from `cloud/Dockerfile`.
   Configure the job command as
   `python -m cloud.reading_compass worker`. Give it enough CPU, memory, and
   timeout for full-length audiobooks. Set job retries to zero so a failed
   conversion cannot repeat paid TTS calls without a new request. Both
   resources need Firestore access;
   the web service also needs permission to execute the job with overrides.
   Set the web service request timeout high enough for MP3 streaming and allow
   unauthenticated invocation at the Cloud Run layer; the app checks the
   signed-in owner's session on every data route.
4. Give the web service these environment variables, preferably from Secret
   Manager: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`,
   `TOKEN_ENCRYPTION_KEY` (a Fernet key), `ALLOWED_EMAIL`,
   `OAUTH_REDIRECT_URI`, `DASHBOARD_URL`, and `CLOUD_RUN_JOB` (the full
   `projects/PROJECT/locations/REGION/jobs/JOB` resource name). The job needs
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`, and
   `OPENAI_API_KEY`. It gets `RC_JOB_ID` from the web service's job override.
5. Package the Reading Compass dashboard with
   `READING_COMPASS_API_URL=https://YOUR-CLOUD-RUN-ORIGIN` in the environment.
   The packager writes a same-origin Netlify proxy rule for `/cloud/*` and
   includes `cloud_dashboard.js`. Deploy `deploy/netlify/` to the existing
   private Netlify site. Its **Open Imprint web agent** link points to
   `https://reading-compass-private.netlify.app/cloud/app`.

Use a long random `SESSION_SECRET`, and generate the Fernet key with
`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.
Keep both values stable across deployments. Never commit them.

The Google refresh token is encrypted before it is stored in Firestore. The
web app checks the verified Google email against `ALLOWED_EMAIL`. Its routes
limit ebook reads and audiobook writes to the two named Drive folders, while
the underlying OAuth permission covers the full Drive account. The Cloud Run
service must be reachable through Netlify's proxy for the browser sign-in and
audio player; its own routes still require the owner's signed session.

Relevant vendor references: [Cloud Run job execution and overrides](https://docs.cloud.google.com/run/docs/execute/jobs),
[Drive scope choices](https://developers.google.com/workspace/drive/api/guides/api-specific-auth),
and [OAuth testing expiry](https://support.google.com/cloud/answer/15549945?hl=en).

## Before exposing the service

Confirm the callback, Netlify proxy, Drive folder access, Firestore permissions,
Cloud Run job execution, OpenAI API key, and an end-to-end short ebook conversion
in the deployed environment. The source alone does not connect the accounts.
