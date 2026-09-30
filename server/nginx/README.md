# Nginx server protection

This directory contains a complete reverse proxy for the Django server. It
listens on port 8080. Put it behind your HTTPS ingress/load balancer, or configure
TLS on Nginx before exposing authenticated traffic publicly. This does not
deploy anything or populate reputation feeds automatically.

## Policies

| File | Effect |
| --- | --- |
| `blocked-ips.conf` | Known malicious addresses receive HTTP 403 on every route. |
| `suspected-ips.conf` | Suspected addresses receive a 1 request/second limit, burst 3. |
| `allowed-ips.conf` | Operator allowlist grants access to admin/docs and bypasses the suspected limit. |
| `trusted-proxies.conf` | Exact proxy CIDRs permitted to supply the original client address. |
| `upstream.conf` | Django's private upstream address. |

IP lists accept IPv4, IPv6, or CIDRs, one entry per line:

```nginx
203.0.113.10/32 1;
2001:db8::10/128 1;
```

These are documentation addresses: replace them with real addresses. The shipped
lists are empty. Public shopping/API routes remain public; admin, Silk, and API
documentation are denied until an operator IP is added to `allowed-ips.conf`.
Allowlisting does not replace Django authentication. An explicit block always
wins, including for an allowlisted operator. Probe paths such as `.env`, `.git`
and WordPress login are blocked even for allowlisted clients. ACME paths are
permitted by the probe rule, but still need an upstream challenge handler.

All clients have a 10 requests/second limit (burst 30), 20 concurrent active
requests, and a 20 MB upload limit. Authentication and password reset routes
share a 5 requests/minute limit (burst 5). Rejected limits return JSON HTTP 429
with `Retry-After: 60`. Tune these values against normal usage, especially shared
office/mobile-network IPs. Limits are per Nginx instance; three replicas can
permit roughly three times the listed rate.

## Host deployment

1. Add operator public/VPN IPs and known blocked/suspected addresses to the lists.
2. Set `upstream.conf` to Gunicorn's private address (default `127.0.0.1:8000`).
3. Install these files in a dedicated configuration directory:

```sh
sudo install -d /etc/nginx/ecommerce
sudo install -m 0644 server/nginx/*.conf /etc/nginx/ecommerce/
sudo nginx -t -p /etc/nginx/ecommerce/ -c nginx.conf
```

Configure the Nginx service to start with
`nginx -p /etc/nginx/ecommerce/ -c nginx.conf -g 'daemon off;'`.
Do not start a second unmanaged Nginx alongside an existing service. This
configuration uses `/tmp/nginx.pid`; make the service PID setting match if it
expects a forking daemon. Test changes and reload the running instance with:

```sh
sudo nginx -t -p /etc/nginx/ecommerce/ -c nginx.conf && sudo nginx -p /etc/nginx/ecommerce/ -c nginx.conf -s reload
```

## Kubernetes deployment

Set `upstream.conf` to the actual Django Service DNS and port, for example
`server django-service:8000;`. The default loopback upstream is for host
installations and will not reach Django in a separate pod. Provision Django
separately and restrict its service with a NetworkPolicy so public traffic
cannot bypass Nginx.

```sh
kubectl kustomize server/nginx
kubectl apply -k server/nginx
kubectl rollout status deployment/nginx-deployment
```

Use `apply -k`, not `apply -f deployment.yaml`: Kustomize generates the mounted
ConfigMap and its versioned name, triggering a rollout when IP lists change.
The LoadBalancer uses `externalTrafficPolicy: Local` to preserve client source
addresses where supported. Verify the logged `client_ip` on your provider before
relying on IP rules. The existing demonstration CronJob is unchanged by this work.
Configure HTTPS at your ingress/load balancer before public use; the manifest
only defines the internal HTTP listener/service.

## Client identity and TLS

Forwarding headers are ignored by default. Behind a proxy, add only its exact
egress CIDRs to `trusted-proxies.conf` and enable the documented real-IP settings.
Never trust all addresses or entire shared private networks. Restrict access to
the Nginx listener to those proxies. If the load balancer uses PROXY protocol,
configure the listener and real-IP module accordingly before enabling it there.

Nginx overwrites `X-Forwarded-For` and `X-Real-IP` before passing to Django, so
client-supplied IPs cannot bypass the rules. It sets `X-Forwarded-Proto` to its own
connection scheme. If TLS terminates upstream, configure HTTPS handling explicitly
on a listener reachable only by that TLS terminator (including Django's trusted
proxy setting); do not blindly pass the incoming protocol header through. Set
Django production host/debug/security settings for your domain as well.

## Logging and verification

JSON access events go to stdout; 4xx/5xx security events and Nginx error messages
go to stderr. Events include client/peer IP, request ID, path, policy flags, status,
duration and rate-limit result. Access events omit query strings, credentials and
bodies. Nginx's own diagnostic error messages may include request URLs: restrict
log access/retention and avoid secrets in URLs. Configure collection/rotation in
the service or cluster log platform.

Use these events to investigate and promote addresses into the suspected/blocked
lists. This is static IP policy plus traffic limits, not automatic malware
detection or a WAF. No IP is banned merely because a normal request returns 404.

Run the real Nginx integration tests locally (Python standard library and an
installed Nginx binary required):

```sh
python3 server/nginx/test_security.py
```

Tests use temporary configuration files, ephemeral loopback ports and a stub
backend; they do not reload or modify the deployed Nginx service.
