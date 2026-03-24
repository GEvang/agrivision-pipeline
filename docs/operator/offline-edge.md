# Offline and edge operation

Use `config/config.edge.yaml` as the starting point for constrained or intermittently connected environments.

Recommended practices:

- pre-stage imagery and dependencies locally;
- inject credentials through environment variables when network access is available;
- validate the environment with `python run.py --doctor` before field execution; and
- preserve generated metadata files alongside copied artifacts.
