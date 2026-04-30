# Kelet Production Secret Setup by Platform

Set `KELET_API_KEY` (and `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY` / `VITE_KELET_PUBLISHABLE_KEY` if frontend) in the platform's secret store. An unset key is a silent failure — no production traces, no error.

## Before writing `.env`

Read first. If `KELET_*` is non-empty, show old vs new and confirm — a stale `KELET_PROJECT` silently routes traces to the wrong project.

## Platforms

- **Vercel**: Dashboard → project → **Settings → Environment Variables**. Add `KELET_API_KEY` (all environments) and publishable key if frontend.

- **Railway**: `railway variables set KELET_API_KEY=<value>`, or dashboard → service → **Variables**.

- **Render**: Dashboard → service → **Environment**. Or `render.yaml` `envVars` with `sync: false`.

- **Fly.io**: `fly secrets set KELET_API_KEY=<value>`. Encrypted and injected at runtime — no manifest change needed.

- **Heroku**: `heroku config:set KELET_API_KEY=<value>` or Dashboard → **Settings → Config Vars**.

- **GitHub Actions** (deploy via workflow): Repo → **Settings → Secrets → Actions → New repository secret**. Then add `env:` entries to the deploy job — secret added but missing `env:` entry means it never reaches the container (**silent**):
  ```yaml
  env:
    KELET_API_KEY: ${{ secrets.KELET_API_KEY }}
    NEXT_PUBLIC_KELET_PUBLISHABLE_KEY: ${{ secrets.NEXT_PUBLIC_KELET_PUBLISHABLE_KEY }}
  ```

- **Helm / Kubernetes**: Create a K8s Secret — do NOT put values in `values.yaml` or ConfigMaps.

  **Env-var wiring (default):** unconditional `secretKeyRef` with `optional: true`. SDK no-ops cleanly if Secret is missing; declared env var keeps "Secret missing" debuggable.
  ```yaml
  - name: KELET_API_KEY
    valueFrom:
      secretKeyRef:
        name: {{ .Values.secrets.keletSecretName }}
        key: KELET_API_KEY
        optional: true
  ```
  **Forkable charts only** (users may deploy without Kelet): wrap the block in `{{- if .Values.secrets.keletSecretName }}`.

  **Chart-level `keletProject` default:** set a real value (e.g. `"myapp"`, comment: override per env). Never `""` — empty project + valid key = orphaned traces, not a silent no-op.

  Tell developer to `kubectl apply` and confirm it's not committed.

- **Docker Compose**: `.env` is fine for `docker compose up`. For production: inject via host secret management (`docker run -e`, Docker Swarm secrets) — not the Compose file.

- **Terraform / AWS CDK / CloudFormation / SAM**: Store in AWS Secrets Manager or SSM Parameter Store (SecureString). Ask how secrets are currently managed in their IaC before proposing changes — patterns vary.

- **Not listed**: Ask the developer how secrets are managed before writing any instructions.
