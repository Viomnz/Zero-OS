# Self-Evolving Runtime Protocol Network (SERP)

SERP adds a feedback-driven evolution layer to runtime execution.

## Commands
- `python src/main.py "serp status"`
- `python src/main.py "serp telemetry submit node=<n> region=<r> cpu=<p> memory=<p> gpu=<p> latency=<ms> energy=<p>"`
- `python src/main.py "serp analyze"`
- `python src/main.py "serp mutation propose component=<scheduler|memory|translator|gpu> strategy=<name> signer=<id>"`
- `python src/main.py "serp deploy staged mutation=<id> percent=<1..100>"`
- `python src/main.py "serp rollback"`
- `python src/main.py "serp state export app=<name> json=<state_json>"`
- `python src/main.py "serp state import id=<state_id> target=<node>"`

## Safety Controls
- Mutation signer validation
- Sandbox validation state in mutation record
- Staged rollout percentages
- Explicit rollback operation
