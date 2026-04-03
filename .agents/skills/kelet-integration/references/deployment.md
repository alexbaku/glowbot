# Kelet Production Secret Setup by Platform

Set `KELET_API_KEY` (and `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY` / `VITE_KELET_PUBLISHABLE_KEY` if frontend) in each
platform's secret store. For each platform below, confirm completion with `AskUserQuestion` before proceeding — an
unconfirmed step is a silent failure (Kelet sees no production traces with no error).

## Platforms

- **Vercel**: Dashboard → your project → **Settings → Environment Variables**. Add `KELET_API_KEY` (all environments)
  and `NEXT_PUBLIC_KELET_PUBLISHABLE_KEY` (all environments). Confirm with `AskUserQuestion` before proceeding.

- **Railway**: `railway variables set KELET_API_KEY=<value>` (and publishable key if frontend), or dashboard →
  your service → **Variables**. Confirm with `AskUserQuestion` before proceeding.

- **Render**: Dashboard → your service → **Environment**, add each key. Or use `render.yaml` `envVars` with
  `sync: false` for secrets. Confirm with `AskUserQuestion` before proceeding.

- **Fly.io**: `fly secrets set KELET_API_KEY=<value>`. Secrets are encrypted and injected at runtime — no manifest
  change needed. Confirm with `AskUserQuestion` before proceeding.

- **Heroku**: `heroku config:set KELET_API_KEY=<value>` or Dashboard → **Settings → Config Vars**. Confirm with
  `AskUserQuestion` before proceeding.

- **GitHub Actions** (app deployed via workflow): Go to repo → **Settings → Secrets and variables → Actions → New
  repository secret**, add `KELET_API_KEY` (and publishable key). Then add `env:` entries to the deploy job —
  secret added but missing `env:` entry means it never reaches the container (**silent**):
  ```yaml
  env:
    KELET_API_KEY: ${{ secrets.KELET_API_KEY }}
    NEXT_PUBLIC_KELET_PUBLISHABLE_KEY: ${{ secrets.NEXT_PUBLIC_KELET_PUBLISHABLE_KEY }}
  ```
  Confirm both steps (secret added + workflow updated) with `AskUserQuestion`.

- **Helm / Kubernetes**: Create a K8s Secret (do NOT put values in `values.yaml` or ConfigMaps — never commit secret
  values). Reference it in the Deployment via `env[].valueFrom.secretKeyRef` or `envFrom`. Tell the developer to
  `kubectl apply` the secret and confirm it is not committed to the repo. Confirm with `AskUserQuestion` before
  proceeding.

- **Docker Compose**: Local `.env` is fine for `docker compose up`. For production container deployments, inject via
  the host's secret management (`docker run -e KELET_API_KEY=...`, Docker Swarm secrets, etc.) — not via the Compose
  file. Note this explicitly in the plan. Confirm with `AskUserQuestion` before proceeding.

- **Terraform / AWS CDK / CloudFormation / SAM**: Store the key in AWS Secrets Manager or SSM Parameter Store
  (SecureString). Reference it in the IaC resource definition. Ask the developer how secrets are currently managed
  in their IaC before proposing changes — patterns vary widely. Confirm with `AskUserQuestion` before proceeding.

- **Not listed**: Ask the developer how secrets are managed in that platform before writing any instructions.
