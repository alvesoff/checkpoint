# checkpoint

Your projects have loose ends. This agent finds them, from your own machine, and tells you before
they cost you something.

It reads your repositories and answers over iMessage: where you stopped in each project, which
dependency is about to break *your* code, where your own projects contradict each other, and what
actually fits in your day. It also speaks first — but only when something changed.

```bash
curl -fsSL https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.sh | sh
```

On Windows, from PowerShell:

```powershell
irm https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.ps1 | iex
```

That one opens Docker Desktop and waits for it if it is installed but stopped, and offers to install
it if it is missing. Nothing else to open or click first.

One command. It checks what you have, finds the folders holding your git repositories and shows the
count, asks before every step that changes anything, and speaks English or Portuguese depending on
your system.

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

Two scheduled routines register themselves on first boot. The hourly one speaks only when a project
**crosses** a threshold: two days idle with unsaved work, then four, then a week. The six-hourly one
speaks only when a dependency changes state. Nothing changed means nothing sent and no tokens spent.

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

## Usage reporting

This image carries a reporter that publishes token usage to the
[Agent Index](https://aiworthusing.com/agent-index) once an hour: day by model counts and nothing
else. No prompts, no task titles, no file paths, no code.

**There is no switch.** It is in the image because it was built in, and that is the decision. A flag
would only re-ask a question the Dockerfile already answered, somewhere that can disagree with it.

For scale: a full day of development, testing and scheduled runs came to roughly 3.2 million tokens
and 3.36 dollars of Plow inference credit, which the Plow account provides.

## Run locally

```bash
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/alvesoff/checkpoint.git && cd checkpoint

plow-agents login --new-line
plow-agents lines
plow-agents mint ln_xxx

printf 'CODE_DIR=/path/to/your/projects\nTZ=America/Sao_Paulo\n' > .env
docker compose up --build -d
```

`CODE_DIR` points at the folder that **contains** your projects. Repositories are found up to two
levels down, so a folder of folders works. Extra folders go in `compose.override.yml`, the way the
installer writes it.

`TZ` matters: the container is UTC by default, and a calendar read in the wrong timezone tells you a
9am meeting is at noon.

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
| `image/s6-overlay/` | Boot services: the usage reporter, the Latch probe, the routine registration |
| `install.sh` | The one-command install |
| `install.ps1` | The same install from PowerShell: finds the bash Git for Windows ships, gets Docker running, and hands `install.sh` to it |

## Building the image

`docker compose up --build` builds from `plow-hermes-agent`, pinned by digest. The usage reporter is
fetched at build time from a pinned commit and checked against a sha256 beside it. A sha in a URL is
only as good as the host serving it, and this runs inside an agent holding a live credential.

## Troubleshooting

| What you see | What it is |
|---|---|
| "no git repository found in /projects" | `CODE_DIR` points at a folder with no repositories, or one level too high |
| "none of the N repositories could be read by git" | Ownership mismatch between host and container. The image ships `/etc/gitconfig` with `safe.directory = *` |
| Every file shows as unsaved | Repositories cloned with CRLF against an LF index. The agent normalizes for this; if you still see it, the image predates that fix |
| The agent offers to use your Mac | It should not, because it probes the relay first. If it happens, `PLOW_MCP_URL` survived without a device connected |
| Nothing is ever sent | Expected while nothing crosses a threshold. `hermes cron runs` inside the container shows the checks happening |

## License

Apache-2.0.
