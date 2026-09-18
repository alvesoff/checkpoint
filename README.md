# checkpoint

A Hermes agent that reads your repos: where each project stopped, what you changed and never saved,
outdated or vulnerable dependencies. Reads your calendar and keeps your to-do list. Mornings it
texts the most important thing nobody is chasing you on; evenings, tomorrow's meeting and its
project.

All of it over iMessage, from your own machine. It answers when you ask, and it speaks first: three
routines only when something actually changed, and two on a fixed schedule, morning and evening.

[![Watch the install, uncut](https://img.youtube.com/vi/jXfH0weiukY/maxresdefault.jpg)](https://youtu.be/jXfH0weiukY)

## Install

**[Watch the full install, uncut (2:43)](https://youtu.be/jXfH0weiukY)** — one command, from an empty
terminal to the agent answering on the phone. Nothing sped up except the image build.

One command. It checks what you have, finds the folders holding your git repositories and shows the
count, asks before every step that changes anything, and speaks English or Portuguese depending on
your system.

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

That one finds the bash Git for Windows already ships, opens Docker Desktop and waits for it if it
is installed but stopped, and offers to install Docker, Git or Python with `winget` if any is
missing. Nothing to open or click first.

### What happens, in order

1. **It checks Docker, git and Python**, and offers to install whatever is missing — with your
   package manager on Linux (`pacman` on Arch, the official Docker script elsewhere) and `winget` on
   Windows. It asks first, every time.
2. **It offers to make Docker start with your machine.** Say yes and the agent survives a reboot on
   its own; say no and you open Docker yourself after each one.
3. **It downloads this repository** into `~/checkpoint`.
4. **It creates your Plow line and credential.** This is the only manual step: it prints an
   activation phrase and a phone number, and you text that phrase from your own phone. Whoever texts
   it back *is* the account binding, so it cannot be done for you in advance.
5. **It finds your code.** It looks where people keep projects, counts the git repositories in each
   folder, and shows you the list before mounting anything. You can say no, or type a path — a
   Windows path like `C:\Users\you\projects` works. The mount is **read-only**.
6. **It works out your timezone** and asks you to confirm it.
7. **It builds and starts the container.** First build takes a few minutes.

Then text the agent "what did I leave unfinished?" and it answers from your own machine.

### If something goes wrong

The installer says which step it stopped on. Two that come up:

- **It stops while updating the local copy** — you have an older `~/checkpoint` it cannot
  fast-forward. Delete the folder and run the command again.
- **The container says `Up` but the agent never answers** — the credential file is bad and the boot
  parked. See [Troubleshooting](#troubleshooting).

---

## What it reads, and what it does with it

| Source | What it produces |
|---|---|
| `git log`, `status`, `rev-list` in every mounted repository | Where you stopped: the commit you were on, files changed and never saved, commits nobody received, branches never pushed |
| File modification time | How long a project has been *actually* untouched. The commit date lies when a project never really made it into git |
| `package.json`, `requirements*.txt` and the npm and PyPI registries | Which dependency is behind or deprecated, ordered by **how many of your projects it hits** |
| That dependency's changelog, read in a real browser and cross-checked against your code | Whether the breaking change touches something you actually call |
| Your Dockerfiles, compared to each other | Where your own projects disagree: containers as root, missing healthchecks, `:latest`, five base images for one language |
| Files git is not tracking | A secret sitting in a file that was never committed, reported by path and kind, never by value |
| Your calendar, over its iCal address | What is realistic today, and a one-tap link for a block of work |
| The OSV vulnerability database, queried with your declared versions | Which package has a known vulnerability, and **in how many of your projects** — the question a per-project `npm audit` cannot ask |
| `git merge-base` against your main branch | Which leftover branches are already merged (clutter) and which are forgotten with commits that exist nowhere else (work) |
| Your `.md` files, checked against the code | Documentation that stopped being true: a `npm run` that no longer exists, a link to a deleted path, a required env var no document mentions |
| Everything not yet committed | A secret, a `.env`, a `console.log` about to enter the history — the last moment the damage is free |
| All of the above, plus your calendar, once in the morning and once at night | What fits today, and at night what is still loose plus the state of the project your first meeting tomorrow is about |

Seven scheduled routines register themselves on first boot, and they split into two kinds.

**Five watch for change and stay quiet otherwise.** Hourly: a project **crosses** an idle threshold
— two days with unsaved work, then four, then a week. Every four hours: a secret turns up in a file
git is not tracking. Every six hours: a dependency changes state, or a new vulnerability shows up in
one you declare. Every twelve hours: documentation stops matching the code. Once a day: this install
falls behind the public repository. Nothing changed means nothing sent and no tokens spent.

**Two speak on schedule**, 8am and 6pm on weekdays, and that is the point of them — the morning one
opens with the thing nobody is going to chase you about today, and the evening one crosses tomorrow's
first meeting with the state of the project it is about.

## What this agent cannot reach

- **Anything you did not mount.** It sees the folders the installer asked about and nothing else:
  not the rest of your disk, not another drive, not your home directory.
- **Write access to your projects.** The mount is `:ro`, enforced by Docker. It cannot commit, push,
  branch or edit, not by policy but by permission. That is what makes handing it a folder of source
  reasonable.
- **Your calendar, beyond reading.** It never writes an event. It sends a link you tap.
- **Your screen, your editor, your AI coding session.** It reads git. Nothing observes what you are
  doing right now.
- **Your machine, when it is off.** This runs in a container on your computer. Shut the computer
  down and the agent stops with it.
- **Anything behind a login**, unless a Mac with [Plow Latch](https://plow.co/latch) is connected. It
  probes for one before it offers, because the platform advertises that capability to every agent
  whether or not a Mac exists.

## What only the owner can do

**Texting the activation phrase.** Whoever texts it back *is* the account binding. The phrase and
the number both come back from activation, so neither can be handed over in advance. The installer
prints it and waits.

**Choosing which folders are watched.** The installer proposes what it found and takes `n` for an
answer. Nothing is mounted without a yes.

**Pointing it at a calendar.** Optional and read-only: the secret iCal address that Google,
Outlook/M365 and Apple all publish. Treat that address like a password, because anyone holding it
reads your calendar without logging in.

## Optional: let it open pull requests

**Off by default, and it does not change the read-only rule.** With this on, the agent clones the
repository **from the remote** into a workspace of its own, edits there, and opens a **draft pull
request** for you to review. Your folder stays mounted read-only and untouched — it writes to its
copy, never to yours.

**The installer asks.** If you are already logged into the [GitHub CLI](https://cli.github.com), it
offers to use that login, so there is no token to create — most developers already have it. If you
are not, it offers to take a token you paste. The default answer to both is **no**, and skipping
costs you nothing else.

Either way it then asks **which repositories** it may touch, and writes both to `.env`:

```
CONTRIB_REPOS=you/your-repo,you/another-repo
CHECKPOINT_GH_TOKEN=...
```

No repositories named means the capability stays off, even with a token present.

**Know what you are handing over.** A GitHub CLI login and a classic `repo` token both reach **every
repository on your account** — `CONTRIB_REPOS` is what this agent's scripts check, not a limit
GitHub enforces, and the agent can run shell commands. If you want the boundary enforced on
GitHub's side rather than ours, create a **fine-grained** token limited to those repositories, with
`Contents: read/write` and `Pull requests: read/write` and nothing else, and paste that instead.

On Linux and macOS the installer closes `.env` to your user only. On Windows it cannot — the file
inherits whatever the folder's ACL says.

`CONTRIB_REPOS` is the gate, and the script never reads it from the environment: boot copies it to a
root-owned file under `/opt`, because a turn of the agent can invoke a script with any environment
it likes — and a gate you can talk your way past is not a gate. Changing the list means editing
`.env` and restarting, which is something you do on your machine, not something a conversation does.

What it refuses, by construction: pushing to your default branch, pushing a diff that contains a
secret (the same scan the pre-commit review uses), more than 40 changed files, and `--force` in any
form. Every change becomes a PR, and every PR is a draft.

## Usage reporting

This image carries a reporter that publishes token usage to the
[Agent Index](https://aiworthusing.com/agent-index) once an hour: day by model counts and nothing
else. No prompts, no task titles, no file paths, no code.

**There is no switch.** It is in the image because it was built in, and that is the decision. A flag
would only re-ask a question the Dockerfile already answered, somewhere that can disagree with it.

For scale: a full day of development, testing and scheduled runs came to roughly 3.2 million tokens
and 3.36 dollars of Plow inference credit, which the Plow account provides.

### Installed before September 18, 2026? Rebuild.

Your image carries an Agent Index client pinned at `f900ff1`. That version **gives up on the index's
409** — the response the server sends to anyone running an agent they do not own — and it does so
before minting a report key. So an install by anyone other than the author runs fine, reports
nothing, and shows up nowhere. The pin is now `87901f8`, which joins the listing as an installer
instead.

The agent never updates itself. Pull and rebuild:

```bash
git pull
docker compose up --build -d
```

### Installed before September 14, 2026?

The installer used to write an empty `AGENT_ID`, and the reporter stands down without it: the agent
runs normally and simply never appears on the index. Add the line and restart:

```bash
grep -q '^AGENT_ID=' .env || echo 'AGENT_ID=checkpoint' >> .env
docker compose up -d
```

## Run locally

```bash
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/alvesoff/checkpoint.git && cd checkpoint

plow-agents login --new-line
plow-agents lines
plow-agents mint ln_xxx

printf 'CODE_DIR=/path/to/your/projects\nTZ=America/Sao_Paulo\nAGENT_ID=checkpoint\n' > .env
docker compose up --build -d
```

`CODE_DIR` points at the folder that **contains** your projects. Repositories are found up to two
levels down, so a folder of folders works. Extra folders go in `compose.override.yml`, the way the
installer writes it.

`TZ` matters: the container is UTC by default, and a calendar read in the wrong timezone tells you a
9am meeting is at noon.

`AGENT_ID` is what the hourly usage reporter reports **for**. Leave it out and the `agent-index`
service stands down on purpose: the install runs fine and simply never appears on the index.
The installer writes it for you — this line is here for the manual path.

### On Windows

Call the CLI through `python`, not directly: the `python3` in its shebang resolves to the Microsoft
Store alias. You do **not** need to touch `core.autocrlf` for this repository. The shipped
`.gitattributes` pins every file to LF, which is what keeps a shell script inside the image from
getting a stray carriage return in its shebang and parking the boot with an error about credentials.

## Layout

| Path | What lives there |
|---|---|
| `runtime/persona.md` | Who the agent is and how it writes. Composed into `SOUL.md` at every boot |
| `skills/where-i-left-off/` | Reading project state, and the hourly routine |
| `skills/dependency-radar/` | Package inventory, registry check, and the six-hourly routine |
| `skills/stack-audit/` | Cross-project consistency and the loose-secret sweep |
| `skills/agenda/` | Calendar over iCal, and block proposals |
| `skills/browsing/` | The browser, and deciding whether a Mac is actually there |
| `skills/doc-check/` | Documentation checked against the code, and the twice-daily routine |
| `skills/daily/` | The morning and evening summaries, and their two scheduled routines |
| `skills/delivery-text/` | Commit and PR text from the real diff, and the pre-commit review |
| `skills/todo/` | The demand list that grows from project state and closes itself |
| `image/s6-overlay/` | Boot services: the usage reporter, the Latch probe, the routine registration, the network watchdog |
| `install.sh` | The one-command install |
| `skills/contribute/` | Cloning to its own workspace, and the draft pull request |
| `install.ps1` | The same install from PowerShell: finds the bash Git for Windows ships, gets Docker running, and hands `install.sh` to it |

## Building the image

`docker compose up --build` builds from `plow-hermes-agent`, pinned by digest. The usage reporter is
fetched at build time from a pinned commit and checked against a sha256 beside it. A sha in a URL is
only as good as the host serving it, and this runs inside an agent holding a live credential.

## Troubleshooting

| What you see | What it is |
|---|---|
| The container says `Up` but the agent never answers | Measured on a clean install: with a bad or empty `plow-credentials`, the boot **parks** — `plow-init` logs *"does not contain only the documented keys ... parking; no gateway will start"* and the container stays `Up` with no gateway. `docker compose logs` shows it on the `plow-init` line. Re-run `plow-agents mint` and replace the file |
| "no git repository found in /projects" | `CODE_DIR` points at a folder with no repositories, or one level too high |
| "none of the N repositories could be read by git" | Ownership mismatch between host and container. The image ships `/etc/gitconfig` with `safe.directory = *` |
| Every file shows as unsaved | Repositories cloned with CRLF against an LF index. The agent normalizes for this; if you still see it, the image predates that fix |
| The agent offers to use your Mac | It should not, because it probes the relay first. If it happens, `PLOW_MCP_URL` survived without a device connected |
| The agent stops answering after a reboot | Docker did not start with the machine. The container itself has `restart: unless-stopped` and comes back on its own once Docker is up — turn on "Start Docker Desktop when you sign in" (the installer offers this) and it survives reboots |
| A message saying `⚠️ Cron 'checkpoint-manha' failed: ...` | Comes from the runtime, not from this agent, which is why it arrives in English and suggests `hermes cron edit <job_id>`. **Do not run that as root inside the container** — see the note below. Nothing is broken permanently: the next scheduled run tries again. If it repeats, `docker compose logs agent` has the reason |
| Nothing is ever sent | Expected for the five monitor routines while nothing crosses a threshold. The two daily summaries do speak on schedule (8am and 6pm on weekdays). `docker compose exec -u hermes agent hermes cron runs` shows every check happening. The `-u hermes` is not optional: the runtime hardens its home directory using the uid that invoked it, so running `hermes` as root inside the container locks the agent out of `/var/lib/hermes`, and it goes silent with nothing in the chat to say why. Restart the container if that happens |

## Adding a skill of your own

This is meant to be forked. A skill is a directory with a `SKILL.md` and a `scripts/` folder, and
the Dockerfile copies `skills/` wholesale — so a new directory is picked up by the next build with
no wiring. What follows is the part that is not obvious, learned by getting each one wrong first.

**A skill that is not in the persona is a skill the agent refuses to use.** `runtime/persona.md` is
what the agent reads to know what it is. A capability that works perfectly, with the script on disk
and the skill installed, will still get "that is not something I do" if no line in the persona
claims it. This is the single most expensive mistake in this repo: the calendar shipped working and
the agent denied having one, and nobody found out from a test — only from asking it.

**Every prohibition in the persona has to name what it does NOT cover.** "Never writes to your
projects" is true and it is what makes the mount safe. But without a carve-out it spreads to
everything with the word *write* in it, and the agent starts refusing to write a commit message, or
to note a task on its own to-do list. The failure is quiet and permanent: the person concludes the
product cannot do it and stops asking.

**The `description:` in a SKILL.md is cut to about 57 characters** before the model ever sees it. So
it cannot carry a list of trigger words. Routing vocabulary belongs in the persona, which arrives
whole.

**The persona on disk is not the prompt of a live conversation.** The runtime writes the system
prompt when a session is created and keeps it. Checking `SOUL.md` after a build proves the persona
was *published*, not that it *arrived* — `image/cont-init.d/06-refresh-persona` exists to release
that pin on every boot. If you remove it, persona edits stop reaching open conversations.

**Editing a bundled skill in the agent's home does not survive a restart.** A boot-time step
reimposes the skills of this agent from the image, because the runtime's skill sync skips any
directory whose copy in the home differs — which quietly freezes that skill against every future
fix. The trade is deliberate: customise these skills in the repo and rebuild, not in
`$HERMES_HOME/skills`.

**Anything that runs unattended lives outside the agent's home**, root-owned. What sits inside
`$HERMES_HOME` the agent can rewrite, and a rewritten script still runs on schedule holding the
credential.

## License

MIT. Required by the hackathon rules, and the right license for something meant to be forked.
