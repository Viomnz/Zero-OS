# Driver Framework

## Objective
Provide a stable driver API with strict lifecycle and isolation.

## Required Driver Groups
- storage
- network
- display
- input

## Lifecycle
1. probe
2. init
3. run
4. suspend/resume
5. shutdown

## Next
- driver manifest schema
- capability permissions per driver
- fault containment and auto-disable policy
