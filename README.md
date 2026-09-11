# Checkpoint

**You didn't forget what to do. You forgot where you stopped.**

An assistant that lives in your phone, knows your machine, and looks after what you left behind.

It reads. It never writes to your projects.

---

## Why

Developers make [12-15 major context switches a day, each costing about 23 minutes to recover
from](https://speakwiseapp.com/blog/context-switching-statistics). Most of those minutes go to
rebuilding a state that is already written down — the branch you were on, the commit message you
wrote, the files still dirty in your tree.

Building with AI agents made this worse, not better. You start four in parallel, walk into a
meeting, and come back not knowing which one stalled. The ecosystem answered with **more agents that
write code** — Cline, OpenHands, Aider, Goose. None of them look after the debris they leave.

## What it does

**Where you stopped.** Branch, last commit, files changed and never saved, commits nobody has seen,
and how long since the project was *actually touched* — file mtime, not commit date, because a repo
that never really made it into git has an old commit and recent work.

> The one that matters is `erp-cutover` — last commit "initial local snapshot" 88 days ago, but
> you touched it 14 days ago and 28 files were never versioned at all. That repo has one commit and
> everything else untracked — it never really made it into git.

**It tells you before you ask.** Quietly, only when a project *crosses* a threshold — two days idle
with unsaved work, then four, then a week. Nothing changes, nothing is sent. No daily digest, and it
will not tell you the same thing twice.

**What is about to break.** It maps every package in every project and checks the registries — then,
unlike a bot that opens pull requests nobody reads, it opens the changelog in a real browser and
greps *your* code to see whether the removed API is one you actually call.

> Express 5 removes `req.param()`. You call it in 3 files, in `service-desk` and
> `staff-portal`. Upgrading without touching those breaks login in both.

**Where your own projects contradict each other.** Not a linter — a linter compares your code to
someone else's rule. This compares your projects to *each other*: containers running as root,
missing healthchecks, five different base images for the same language, a secret sitting in a file
git isn't tracking.

**Your day, honestly.** It reads your calendar over its iCal address — Google, Outlook/M365 or Apple,
no OAuth — and uses it to say what is realistic, not to manage it. When a block makes sense it sends
a one-tap link; you confirm. It never writes to your calendar either.

**Your Mac, when you have one.** If a Mac with Plow Latch is connected, it uses *your* browser with
*your* logged-in sessions. If not, it uses the browser inside the container and says what it can and
cannot reach. It checks before it promises.

## Where you talk to it

**iMessage**, and a **local web panel** at `127.0.0.1:9119` behind a login, bound to loopback only.
You are not locked to one channel, and nothing goes through a third party.

## What it does not do

- **It never writes to your projects.** The folder is mounted read-only at the Docker level. It
  cannot commit, push, branch, or edit — not by policy, by permission.
- It does not manage your calendar or plan your day. It reads the calendar to tell you what fits.
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
endings, a shell script inside the image gets a `
` in its shebang, and the container parks with an
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

Once, in the chat: *"start nudging me about stale work"* and *"watch my dependencies"*. Each
registers a single scheduled check and will not create a second one if you ask again.

### Optional: your calendar

Give it the secret iCal address of your calendar (Google: *Calendar settings > Secret address in
iCal format*; Outlook: *Calendar > Share > Publish > ICS*). Read-only, no OAuth, no account.

### Optional: the web panel

Set `PANEL_USER` and `PANEL_PASS` in `.env` and open `http://127.0.0.1:9119`.

### Set your timezone

`TZ=America/Sao_Paulo` in `.env`. The container is UTC by default, and a calendar read in the wrong
timezone tells you a 9am meeting is at noon.

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
