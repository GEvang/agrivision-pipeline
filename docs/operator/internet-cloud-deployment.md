# Internet Deployment For The AgriVision Dashboard

This manual explains how to make the AgriVision dashboard reachable over the internet from a Windows or Linux host.

The recommended deployment is:

```text
User browser
  -> Cloudflare Access login
  -> Cloudflare Tunnel
  -> AgriVision host
  -> http://localhost:8008
```

Do not expose port `8008` directly to the internet. AgriVision should sit behind Cloudflare Access, a VPN, or another external login layer.

## Prerequisites

For both Windows and Linux:

- Docker must be installed and running.
- AgriVision must already be installed. See `docs/operator/install.md`.
- AgriVision must work locally first at `http://127.0.0.1:8008` or `http://localhost:8008`.
- The host should stay powered on while users need access.
- OpenAgri Weather, Irrigation, and Pest & Disease services must be configured for complete field analysis.
- ODM workloads need enough CPU, RAM, and disk. Keep `Maximum active ODM runs` at `1`.

For permanent Cloudflare access:

- A Cloudflare account.
- A domain added to Cloudflare DNS, for example `example.com`.
- Cloudflare Zero Trust enabled.

Domain registration is separate from AgriVision. If no domain exists yet, buy one from any registrar, add it to Cloudflare, follow Cloudflare's nameserver instructions, and wait until Cloudflare shows the domain as active.

## 1. Confirm AgriVision Works Locally

Do this on the machine that runs AgriVision.

Confirm the dashboard opens locally:

| Host OS | Local dashboard URL |
| --- | --- |
| Windows | `http://127.0.0.1:8008` |
| Linux | `http://localhost:8008` |

If it does not open locally, fix that before setting up internet access.

## 2. Test A Temporary Tunnel

Use this for a short demo or first validation:

```bash
docker run --rm cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8008
```

On some Linux hosts, `host.docker.internal` is not available to this standalone tunnel container. If that happens, use this Linux alternative:

```bash
docker run --rm --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8008
```

Cloudflare prints a temporary URL similar to this:

```text
https://random-words.trycloudflare.com
```

Open that URL from another computer or phone. If the dashboard loads, internet routing works.

Important:

- Keep the terminal window open.
- The URL stops working when the command stops.
- The URL is public while it is running.
- This is not the production setup.

## 3. Create A Permanent Named Tunnel

In Cloudflare Zero Trust:

- Go to `Networks > Tunnels > Create tunnel`.
- Choose `Cloudflared`.
- Name the tunnel `agrivision-dashboard`.
- Choose the Docker connector.

Cloudflare shows a command like:

```text
docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TOKEN>
```

Use the OS-specific long-running connector command below.

### Windows Connector

```powershell
docker run -d --name agrivision-tunnel --restart unless-stopped cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TOKEN>
```

Check it:

```powershell
docker ps --filter "name=agrivision-tunnel"
docker logs agrivision-tunnel
```

### Linux Connector

On Linux, run the connector with host networking so it can reach `localhost:8008`:

```bash
docker run -d \
  --name agrivision-tunnel \
  --restart unless-stopped \
  --network host \
  cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TOKEN>
```

Check it:

```bash
docker ps --filter "name=agrivision-tunnel"
docker logs agrivision-tunnel
```

## 4. Add The Public Hostname

In the tunnel's public hostname settings, add:

| Field | Value |
| --- | --- |
| Subdomain | `agrivision` |
| Domain | `example.com` |
| Type | `HTTP` |
| URL on Windows | `host.docker.internal:8008` |
| URL on Linux | `localhost:8008` |

The public dashboard URL becomes:

```text
https://agrivision.example.com
```

## 5. Enable Cloudflare Access

In Cloudflare Zero Trust:

- Go to `Access > Applications > Add application > Self-hosted`.
- Use `https://agrivision.example.com`.

Create an allow policy for only the intended users, for example:

```text
farmer@example.com
advisor@example.com
```

Test from another device. Cloudflare should ask for login before AgriVision opens.

## 6. Update AgriVision Settings

In the AgriVision dashboard, go to `Settings > Remote Access Checklist`.

Set:

| Setting | Value |
| --- | --- |
| Access mode | `Self hosted` or `Cloud` |
| Public URL | `https://agrivision.example.com` |
| Minimum free disk | `50` |
| Maximum active ODM runs | `1` |
| External login protection is enabled | checked |

Use `Self hosted` when AgriVision runs on a farm-local workstation or server. Use `Cloud` when AgriVision runs directly on an internet cloud VM.

Only check external login protection after Cloudflare Access or an equivalent login layer is active.

## AgriVision Dashboard Settings

The deployment settings in AgriVision do not create the tunnel. They record and check the deployment.

Use them this way:

| Setting | Meaning |
| --- | --- |
| Access mode | `Local`, `Self hosted`, or `Cloud` label used by the deployment checklist |
| Public URL | The URL AgriVision checks at `/health` |
| Minimum free disk | Disk threshold checked before ODM jobs |
| Maximum active ODM runs | Concurrent ODM run limit; keep at `1` |
| External login protection is enabled | Confirmation that Cloudflare Access, VPN, or equivalent protection is active |

The dashboard can start without `.env`. Use the Settings page for normal operator configuration. Use `.env` only when preconfiguring credentials or deployment values outside the dashboard.

## Troubleshooting

If the quick tunnel prints a URL but the browser cannot load AgriVision:

- Confirm AgriVision works locally at `http://localhost:8008`.
- On Windows, use `http://host.docker.internal:8008` as the tunnel target.
- On Linux, try `--network host` and `http://localhost:8008`.
- Check the AgriVision container:

```bash
docker compose ps
docker compose logs --tail 100 agrivision
```

If Cloudflare shows a 404:

- Confirm the hostname is attached to the correct tunnel.
- Confirm the public hostname service is `HTTP`.
- Confirm the service URL is correct.
- Confirm the domain is active in Cloudflare DNS.

If AgriVision loads without a login prompt:

- Cloudflare Access is not protecting the hostname yet.
- Do not share the URL until Access or another login layer is active.

## Final Checklist

Before sharing the URL:

- AgriVision works locally.
- The tunnel connector is running.
- The public URL opens from another network.
- Cloudflare Access or another login layer appears before the dashboard.
- Only approved emails/users can log in.
- `Maximum active ODM runs` is set to `1`.
