# Sandbox image

The container every AgentHub run is given. Today it holds no agent code: one
program, `probe.py`, reports what the container can and cannot do, and the
backend judges those answers into isolation checks before a run may continue.

```
docker build -t agenthub/sandbox:0.6.0 agents/sandbox
```

- **Account:** uid/gid 65532, with no login shell.
- **Entrypoint:** `python3 -I -B /opt/agenthub/probe.py` — isolated mode, no
  bytecode written, no shell interpreting arguments.
- **How it is started:** only by `backend/app/sandbox/spec.py`, which adds a
  read-only root, a `noexec` tmpfs, no capabilities, no network, resource
  limits, and nothing from the host. Starting it any other way gives none of
  those guarantees.

The probe prints one JSON object. It reports environment variable *names*,
never their values. What each answer means, and which answers fail a run, is
documented in [docs/BACKEND.md](../../docs/BACKEND.md) §7.

Changing the image means changing the tag in `SANDBOX_IMAGE`, in
`backend/app/core/config.py` and in the CI `sandbox` job together.
