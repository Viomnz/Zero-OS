# Recursive Capability Runtime Protocol (RCRP)

RCRP executes applications as capability graphs instead of OS-specific binaries.

## Commands
- `python src/main.py "rcrp status"`
- `python src/main.py "rcrp device set [cpu=<c>] [gpu=<g>] [ram=<gb>] [network=<n>] [energy=<mode>]"`
- `python src/main.py "rcrp graph register app=<name> json=<graph_json>"`
- `python src/main.py "rcrp token set <token_name> <on|off>"`
- `python src/main.py "rcrp plan build app=<name>"`
- `python src/main.py "rcrp mesh node register name=<node> power=<tier>"`
- `python src/main.py "rcrp migrate app=<name> plan=<plan_id> target=<node_id>"`
- `python src/main.py "rcrp learning observe <observation>"`

## Model
- App capability graph (`nodes`, `edges`)
- Runtime capability engine builds an adaptive execution plan per device profile
- Mesh network supports node registration and migration metadata
- Capability tokens gate sensitive node execution
