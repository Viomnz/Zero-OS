# Store Production Operations

This document defines the production-level store control-plane commands added to Zero OS.

## Installer Pipeline
- `store install user=<id> app=<name> [os=<target_os>]`
- `store upgrade id=<install_id> version=<v>`
- `store uninstall id=<install_id>`

## Auth, Billing, Licensing, Entitlements
- `store account create email=<email> [tier=<free|pro|enterprise>]`
- `store billing charge user=<id> amount=<n> [currency=<code>]`
- `store license grant user=<id> app=<name>`

## Security Enforcement
- `store security enforce app=<name>`

## Storage/CDN + Replication/Rollback
- `store replicate app=<name> version=<v>`
- `store rollback app=<name> version=<v>`

## Discovery/Reviews/Analytics
- `store search <query>`
- `store review add app=<name> user=<id> rating=<1..5> [text=<msg>]`
- `store analytics status`

## Compliance
- `store policy ios external <on|off>`
- `store compliance status`

## Telemetry/SLO/Abuse
- `store telemetry status`
- `store slo set availability=<n> p95=<sec>`
- `store abuse block ip <ip>`
