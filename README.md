# Checkpoint

**You didn't forget what to do. You forgot where you stopped.**

Text it "where did I leave off?" and it answers from your repositories — the commit you were on,
the files you changed and never saved anywhere, the branch nobody else has seen. It also texts you,
unprompted, when something has been sitting too long.

It reads. It never writes.

---

## Why

Developers make [12–15 major context switches a day, and each one costs about 23 minutes to recover
from](https://speakwiseapp.com/blog/context-switching-statistics). Most of those 23 minutes go to
rebuilding a mental state that is already written down — in the branch you were on, the last commit
message you wrote, the files still sitting dirty in your working tree.

Checkpoint reads that, so you don't have to rebuild it.

This gets worse the more you build with AI agents: more parallel work, less of it held in your own
head.

## What it does

**Ask it.**

> **you:** where did I leave off?
>
> **Checkpoint:** The one that matters is `erp-cutover` — 88 days idle, last commit "initial
> local snapshot", 28 files changed and never saved anywhere: `_audit.py`, `_reconcile.py`,
> `_find_vendors.py` and 25 more. That repo has one commit and everything else untracked — it never
> really made it into git.
>
> Also dirty: `people-portal` (52 days), `qrcode-plates` (11 days). The other 22 projects are clean.

**Or let it tell you.** It watches quietly and messages you when a project *crosses* a threshold —
two days idle with unsaved work, then four, then a week. Nothing changes, nothing is sent. It does
not send a daily digest, and it will not tell you twice about the same thing.

## What it does not do

- **It never writes to your projects.** The folder is mounted read-only at the Docker level. It
  cannot commit, push, branch, or edit — not by policy, by permission.
- It does not manage your calendar, triage your email, or plan your day.
- It cannot see your editor, your terminal, or your AI coding session. It reads git, nothing else.
- It does not read your code to a server. Your files stay on your machine; only what it needs to
  answer you reaches the model.

## Install

You need [Docker](https://docs.docker.com/get-docker/), git, Python 3, and an iPhone or a Mac with
Messages (to activate the line). Works on **Windows, Linux and macOS**.

```bash
# 1. Get the credential CLI
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

# 2. Get this agent
git clone <this-repo> checkpoint
cd checkpoint

# 3. Log in — it prints a phrase; text that whole phrase from your phone
plow-agents login --new-line
plow-agents lines            # copy the uid of a line marked "free"
plow-agents mint ln_xxx      # writes ./plow-credentials

# 4. Point it at your code and start it
echo "CODE_DIR=/absolute/path/to/your/projects" > .env
docker compose up --build -d
```

Then text the line's number: *"where did I leave off?"*

### Windows

Everything above works in Git Bash, with one thing to know:

```bash
# The shebang says python3, which Windows hijacks with a Microsoft Store alias.
# Call the CLI through python instead.
python plow-agents/bin/plow-agents login --new-line
```

You do **not** need to touch `core.autocrlf` for this repo — the shipped `.gitattributes` pins
every file to LF, so a default Git-for-Windows clone still produces an image that boots. (Verified
by cloning both ways.) That matters because the failure it prevents is nasty: Git converts the line
endings, a shell script inside the image gets a `` in its shebang, and the container parks with an
error message about *credentials* rather than line endings.

### Pointing `CODE_DIR` at the right thing

Point it at the folder that **contains** your projects:

```
~/code/            <- CODE_DIR goes here
  api/.git
  frontend/.git
  infra/.git
```

It looks one level deep, on purpose: a recursive walk would find every `node_modules` with a `.git`
in it and take long enough to time out.

Pointing it straight at a single project works too — it just watches that one.

### Turning on the nudges

Once, in the chat: *"start nudging me about stale work."* It registers a single scheduled check and
will not create a second one if you ask again.

## Verifying the read-only claim

Don't take our word for it — the whole claim rests on two lines you can read yourself:

- `compose.yml` mounts your folder with `:ro`. Docker enforces it; a write fails at the kernel.
- `skills/where-i-left-off/scripts/scan_projects.py` is the only thing that touches your projects.
  Every `git` call in it is `log`, `status`, `rev-list`, `rev-parse` or `remote`. No fetch, no
  write, no network.

## Troubleshooting

| What you see | What it is |
|---|---|
| "no git repository found in /projects" | `CODE_DIR` points at a folder with no repositories in it, or one level too high |
| "none of the N repositories could be read by git" | Ownership mismatch between host and container. The image ships `/etc/gitconfig` with `safe.directory = *`; if you rebuilt from a modified Dockerfile, check it is still there |
| Every file shows as unsaved | Your repos were cloned with CRLF and the index holds LF. The agent already normalizes for this — if you still see it, you are running an image built before that fix |
| The agent offers to use your Mac | The platform injects that capability into every agent's description. This one does not do it; the persona says so explicitly |

## How it is built

A [Hermes agent](https://github.com/NousResearch/hermes-agent) on the
[Plow base image](https://github.com/plow-pbc/plow-hermes-agent), reachable over iMessage. The
scheduled check uses the runtime's `--monitor-script` mode: a cheap script prints a **stable
signature** of what is stuck — bucketed by age, with no timestamps in it — and the agent is only
woken when that signature changes. Idle state costs zero tokens.

Usage is reported to the [Agent Index](https://aiworthusing.com/agent-index): day-by-model token
counts, and nothing else. No prompts, no file paths, no code.

## License

Apache-2.0.
