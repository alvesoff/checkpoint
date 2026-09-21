# Install Checkpoint

Two ways in. They are not the same product, and the difference is the folder on your disk.

| | **Text it** | **Install it** |
|---|---|---|
| What you need | a phone | Docker + a free Plow line |
| Time | one message | a few minutes |
| Reads a **public** GitHub repo you send it | yes | yes |
| Reads **your own** code, on your machine | no | yes |
| Your calendar, your to-do list, the morning and evening routines | no | yes |

Text it to see what it finds. Install it to point it at your own work.

---

## 1. Text it — no Docker, nothing to download

Open the page and tap **Text this agent**:

**https://aiworthusing.com/agent-index/checkpoint**

Or text `Set this up for me: aiworthusing.com/agent-index/checkpoint` to **+1 628 246 3032**.

Then send it the URL of any **public** GitHub repository. It clones it anonymously — no token, no
account, no Docker — and answers what it found: where the code stopped, dependencies that are a
major behind or deprecated, packages with a known vulnerability in the OSV database, a Dockerfile
running as root, documentation that no longer matches the code.

**What this one cannot do:** it runs in the cloud, so there is no folder of yours for it to read.
No private repository, no calendar, no to-do list, and none of the scheduled routines that make it
speak first. For that, install it.

---

## 2. Install it — one command

**What you need first:** a Plow account with one free line (the installer walks you through it), and
Docker. Nothing else — no API key of your own, no OAuth, no Mac.

**macOS and Linux** — paste into a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.sh | sh
```

**Windows** — paste into PowerShell:

```powershell
irm https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.ps1 | iex
```

[**Watch the full install, uncut (2:43)**](https://youtu.be/jXfH0weiukY) — from an empty terminal to
the agent answering on the phone. Nothing sped up except the image build.

### What happens, in order

1. **It checks Docker, git and Python**, and offers to install whatever is missing — your package
   manager on Linux, `winget` on Windows. It asks first, every time.
2. **It offers to make Docker start with your machine.**
3. **It downloads this repository** into `~/checkpoint`.
4. **It creates your Plow line and credential.** The only manual step: it prints an activation
   phrase and a number, and you text that phrase from your own phone. Whoever texts it back *is* the
   account binding, so nobody can do it for you in advance.
5. **It finds your code.** It looks where people keep projects, counts the git repositories in each
   folder, and shows you the list before mounting anything. You can say no, or type a path — a
   Windows path like `C:\Users\you\projects` works. **The mount is read-only**, enforced by Docker:
   it cannot commit, push, branch or edit.
6. **It works out your timezone** and asks you to confirm it.
7. **It builds and starts the container.** First build takes a few minutes.

Then text it *"what did I leave unfinished?"* and it answers from your own machine.

### If something goes wrong

The installer says which step it stopped on. The two that come up:

- **It stops while updating the local copy** — you have an older `~/checkpoint` it cannot
  fast-forward. Delete the folder and run the command again.
- **The container says `Up` but the agent never answers** — the credential file is bad and the boot
  parked. `docker compose logs` shows it on the `plow-init` line; re-run `plow-agents mint` and
  replace the file.

The full list is in [Troubleshooting](../README.md#troubleshooting).

### Adding your projects later

Mount another folder read-only in `compose.yml` and restart. Any git repository under it is picked
up on the next scan — nothing to configure per project.

---

What it reads, what it cannot reach, and what runs on a schedule: [README](../README.md).
