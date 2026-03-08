# Hardware Co-Designed Runtime Fabric

Advanced runtime layer for hardware co-design, autonomous app evolution, persistent runtime memory, and distributed execution.

## Commands
- `python src/main.py "hardware runtime status"`
- `python src/main.py "hardware runtime set [accelerator=on|off] [security=on|off] [memory=on|off] [network=on|off]"`
- `python src/main.py "hardware runtime maximize"`
- `python src/main.py "runtime evolve app <app_name>"`
- `python src/main.py "runtime memory learn app=<name> key=<k> value=<v>"`
- `python src/main.py "runtime memory get app=<name>"`
- `python src/main.py "runtime fabric node register name=<node> power=<tier>"`
- `python src/main.py "runtime fabric dispatch app=<name> task=<task> [nodes=<n>]"`
- `python src/main.py "runtime fabric status"`
