# Ligjerata API deployment

The repository is prepared for a Docker-based Render web service. The image includes Python 3.13, FFmpeg and Deno so the existing media ingestion pipeline can run without changing application behavior.

## Required environment variables

Configure `DATABASE_URL`, `JWT_SECRET_KEY`, `ADMIN_EMAILS`, `CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `RESEND_API_KEY`, and `RESET_EMAIL_FROM` in the hosting dashboard. Never paste values into Git. Set `CORS_ORIGINS` to the exact production web origins; native apps do not rely on browser CORS.

Render uses `render.yaml`, builds `Dockerfile`, starts Uvicorn on `$PORT`, and checks `/health`. Database schema additions are idempotent at application startup. Supabase holds durable audio; local temporary conversion files are deleted after processing and must not be treated as persistent storage.

Media conversion is currently performed within the API request. For larger production volume, move ingestion into a durable worker/queue before increasing traffic, because a platform restart can interrupt a running conversion.

After deployment, verify `/health`, `/openapi.json`, authentication, a small media conversion, the resulting Supabase public URL, and password-reset email delivery. Point the mobile production environment at the resulting HTTPS base URL.
