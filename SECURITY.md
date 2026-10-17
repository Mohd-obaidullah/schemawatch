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

Thank you for helping keep `schemawatch` and its users secure!
