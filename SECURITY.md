# Security Policy

## Supported Versions

Only the latest release of `schemawatch` receives security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

The `schemawatch` team takes the security of API drift monitoring and data privacy seriously.
Under **Hard Rule 1** of our project principles:
> **Privacy first.** Raw payload values must never be stored, logged, queued externally, or put in an alert. Only schemas (types, field paths) may persist.

If you discover a security vulnerability, privacy leak, or authentication flaw in `schemawatch`, **please do not open a public issue.**

Instead, report it privately using one of the following methods:

1. **GitHub Private Vulnerability Reporting:**  
   Navigate to the [Security Advisories](https://github.com/Mohd-obaidullah/schemawatch/security/advisories) tab of the repository and click **"Report a vulnerability"**.

2. **Security Contact:**  
   Send an email with the subject `[SECURITY] schemawatch Vulnerability Report` to:  
   `security@schemawatch.io` (or directly contact repository maintainers via GitHub).

### What to Include in Your Report

To help us triage and resolve the issue quickly, please provide:
- A clear description of the vulnerability and its potential impact.
- Step-by-step reproduction instructions or a minimal proof of concept (PoC).
- Any affected components (`packages/core`, `apps/api`, `apps/web`, integrations).
- Suggested remediation or patch, if available.

### Response & Handling Timeline

- **Initial Response:** We will acknowledge receipt of your report within 48 hours.
- **Triage & Assessment:** We will assess severity and confirm impact within 5 business days.
- **Resolution & Release:** A fix will be developed, tested, and released as a patch release accompanied by an advisory acknowledging your contribution (unless you prefer anonymity).

## Authentication & Secure Defaults

`schemawatch` is **secure by default**. In production mode (`SCHEMAWATCH_DEV_MODE=false`), the server strictly requires a valid, non-placeholder API bearer token and will refuse to start if it is missing or insecure.

### 1. Generating a Secure Token

Generate a cryptographically secure 256-bit token using Python's standard `secrets` library:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set this token in your environment or `.env` file:

```bash
SCHEMAWATCH_API_TOKEN="<generated-token>"
SCHEMAWATCH_DEV_MODE="false"
```

> **Warning**: The server explicitly rejects empty tokens and the default placeholder `your-random-secure-token-here`.

### 2. Token Verification & Constant-Time Comparison

All protected routes (`/api/*`, including `/api/ingest`, `/api/endpoints`, `/api/events`, and `/api/events/stream`) require:

```http
Authorization: Bearer <SCHEMAWATCH_API_TOKEN>
```

Tokens are verified in constant time using `hmac.compare_digest` to prevent timing attacks. Public health probes (`/healthz`) and static dashboard assets do not require authentication.

### 3. Token Rotation Procedure

To rotate your API token without dropping telemetry traffic:

1. Generate a new secondary secret using `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Update clients / ingestion workers to use the new token.
3. Update `SCHEMAWATCH_API_TOKEN` in the server environment / `.env`.
4. Perform a rolling restart of the `schemawatch` containers or processes.
5. In the React web dashboard, enter the new token on the `/token` page (tokens are held strictly in browser `sessionStorage` and cleared automatically on 401 responses).

### 4. Running Behind HTTPS & Reverse Proxies

Never expose the `schemawatch` server directly to the public internet without TLS:

- **TLS Termination:** Terminate SSL/TLS at a reverse proxy (e.g., Nginx, Caddy, Cloudflare, Traefik, AWS ALB).
- **Header Forwarding:** Ensure your proxy forwards `Authorization`, `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers.
- **Example Caddy Configuration:**
  ```caddy
  drift.example.com {
      reverse_proxy localhost:8000
  }
  ```
- **Example Nginx Configuration:**
  ```nginx
  server {
      listen 443 ssl http2;
      server_name drift.example.com;

      ssl_certificate /path/to/fullchain.pem;
      ssl_certificate_key /path/to/privkey.pem;

      location / {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          
          # SSE streaming support
          proxy_set_header Connection '';
          proxy_http_version 1.1;
          chunked_transfer_encoding off;
          proxy_buffering off;
          proxy_cache off;
      }
  }
  ```

### 5. CORS Origins

By default, cross-origin resource sharing (CORS) is disabled. If your frontend or API clients are hosted on a different domain, explicitly whitelist trusted origins in `SCHEMAWATCH_CORS_ORIGINS`:

```bash
SCHEMAWATCH_CORS_ORIGINS='["https://dashboard.example.com", "https://app.example.com"]'
```

Never use wildcard `*` origins in production with authenticated APIs.

Thank you for helping keep `schemawatch` and its users secure!
