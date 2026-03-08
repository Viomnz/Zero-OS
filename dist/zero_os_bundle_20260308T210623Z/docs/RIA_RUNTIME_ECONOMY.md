# Runtime Instruction Architecture (RIA) and Runtime Economy

## RIA Commands
- `python src/main.py "ria status"`
- `python src/main.py "ria program register app=<name> json=<instruction_json>"`
- `python src/main.py "ria program validate id=<program_id>"`
- `python src/main.py "ria execute id=<program_id> [caps=<json>]"`

## Runtime Economy Commands
- `python src/main.py "runtime economy status"`
- `python src/main.py "runtime economy actor register role=<developer|runtime_node_operator|storage_node|optimization_node> name=<name>"`
- `python src/main.py "runtime economy contribution actor=<id> kind=<compute|bandwidth|optimization> units=<n>"`
- `python src/main.py "runtime economy payout actor=<id> amount=<n>"`

## Purpose
- RIA defines a portable instruction language executed by runtime nodes.
- Runtime Economy provides incentives and accounting for ecosystem operators.
