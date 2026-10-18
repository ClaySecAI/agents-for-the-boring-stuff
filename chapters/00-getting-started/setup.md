# Chapter 0B: Setting up your computer

This chapter installs everything the book uses, one step at a time, and ends with a script that checks
the result. It assumes you have a Mac, Windows or Linux computer and have never used a terminal. Skip any
step you have already done. You do not need every section: you need Python, Claude Code, and at least one
of LM Studio, Ollama or Apple's on-device model.

## 0B.1 How much memory you have

Local models run in memory, so the amount of RAM decides which ones are practical. Find yours:

- **Mac:** Apple menu, then About This Mac. Look for "Memory".
- **Windows:** Settings, System, About. Look for "Installed RAM".
- **Linux:** run `free -h` in a terminal.

| RAM | Practical choice | Notes |
|---|---|---|
| 8 GB | `llama3.2:3b` (2 GB) | Fast, but it misfiled the most files in our test (section 1D.12). Expect to review more. |
| 16 GB | `google/gemma-4-e4b` (7 GB) or `granite4.1:8b` (5 GB) | Close the browser and other large apps while it runs. |
| 24 GB or more | `google/gemma-4-12b` (7.5 GB) | The book was written and tested on a 24 GB Mac. |

Models above about 16 GB on disk did not fit on that 24 GB machine, which is why none of the tests use one.

## 0B.2 The terminal

A terminal is a window where you type commands instead of clicking. Every command in this book goes
there.

- **Mac:** open Terminal (press Command-Space, type "Terminal", press Return).
- **Windows:** install [Windows Subsystem for Linux](https://learn.microsoft.com/windows/wsl/install), then open
  "Ubuntu" from the Start menu. The book's commands assume a Unix-style shell.
- **Linux:** open your distribution's terminal program.

Commands in this book look like this:

```bash
ls
```

Type the text (do not type any `$` that a shell prints before it), then press Return. Four commands are
enough to get around:

```bash
pwd                      # print the folder you are in
ls                       # list what is in it
cd Documents             # go into a folder called Documents
cd ..                    # go up one folder
```

A folder name that contains a space must be wrapped in quotes: `cd "My Files"`. Without the
quotes the shell sees two names. You can also drag a folder from Finder onto the terminal window to
paste its path.

## 0B.3 Python

The scripts need Python 3.9 or later and use nothing outside the standard library, so there is nothing
else to install. Check what you have:

```bash
python3 --version
```

If it prints `Python 3.9.x` or higher, move on. On a Mac with no Python, running `python3` offers to
install Apple's developer tools; accept. Otherwise, install it from [python.org](https://www.python.org/downloads/)
or with `brew install python` if you use Homebrew. On Ubuntu, `sudo apt install python3`.

## 0B.4 The book's files

Get a copy of the repository. With git installed:

```bash
git clone <repository-url> agents-for-the-boring-stuff
cd agents-for-the-boring-stuff
```

Replace `<repository-url>` with the address on the repository's GitHub page ("Code" button). Without git,
use the "Download ZIP" option on the same button and unzip it. All paths in the book are relative to
this folder.

## 0B.5 Claude Code

Claude Code is the agent program from Section 0.2. It needs an Anthropic account (a Claude subscription or
API access). Follow the installation instructions in the official documentation at
[docs.claude.com](https://docs.claude.com/en/docs/claude-code/overview), since the install command changes
over time. When it is installed:

```bash
claude --version         # prints a version number
claude                   # starts a session; sign in when asked, then type /exit to leave
```

Start sessions from inside the repository folder, so Claude Code finds the agents, skills and
permissions in `.claude/`.

## 0B.6 A local model, option 1: LM Studio

LM Studio is an app with a built-in model browser and a local server. It runs on Mac, Windows, and Linux.

1. Download it from [lmstudio.ai](https://lmstudio.ai), install it like any app and open it once.
2. Install its command-line tool. In the terminal:

   ```bash
   ~/.lmstudio/bin/lms bootstrap
   ```

   Close and reopen the terminal, then check:

   ```bash
   lms --version
   ```

3. Download a model. Pick one from the table in 0B.1. For a 24 GB machine:

   ```bash
   lms get google/gemma-4-12b
   ```

   If the command cannot find the name, open the app, click the magnifying glass (Discover), search for
   "gemma 4", and download from there. The download is several gigabytes. Check what you have with
   `lms ls`.

4. Start the server and load the model:

   ```bash
   lms server start
   lms load google/gemma-4-12b --identifier classifier --context-length 6144
   ```

   `--identifier classifier` is the name the scripts ask for. `--context-length 6144` limits the
   memory the model reserves for reading. Without it LM Studio may ask for far more than your machine
   has, and refuse to load.

5. Check that it answers:

   ```bash
   curl -s http://localhost:1234/v1/models
   lms ps
   ```

   The first prints a list that includes `classifier`. The second shows what is loaded and how much
   memory it uses.

When you finish, free the memory and stop the server:

```bash
lms unload --all
lms server stop
```

LM Studio keeps a log of the requests it receives, including the file text the scripts send. That text
stays on your machine, but if you worked on real files, delete the logs afterwards. They are under
`~/.lmstudio/server-logs/`.

## 0B.7 A local model, option 2: Ollama

Ollama has no window. It runs a server and you manage models from the terminal.

1. Install it from [ollama.com](https://ollama.com/download), or on a Mac with Homebrew:
   `brew install ollama`.
2. Start the server. The Mac app starts it for you. With the command-line version, run this in a
   terminal tab you leave open:

   ```bash
   ollama serve
   ```

3. In another terminal tab, download a model (several gigabytes) and list what you have:

   ```bash
   ollama pull granite4.1:8b
   ollama list
   ```

4. Check that the server answers:

   ```bash
   curl -s http://localhost:11434/v1/models
   ```

5. The scripts talk to Ollama by address and model name instead of LM Studio's identifier:

   ```bash
   python3 chapters/01-files-and-folders/1d-projects/assign_projects.py <folder> projects.json \
       --base-url http://localhost:11434/v1 --model granite4.1:8b
   ```

Stop the server with Control-C in the tab that runs it, or quit the app. Remove a model you no longer
want with `ollama rm <name>`.

## 0B.8 A local model, option 3: Apple's on-device model

On a Mac with Apple Intelligence there is nothing to download. You need macOS 26 or later and
Apple Intelligence turned on (System Settings, then Apple Intelligence & Siri). Apple's compilers build
the small helper programs the chapters use:

```bash
xcode-select --install       # one time; skip if swiftc --version already works
swiftc --version
```

Chapters 1C and 1D build the helpers with `swiftc`. If Apple Intelligence is off or unavailable, the
helper prints a message and stops, and nothing is sent anywhere.

## 0B.9 Optional tools for other platforms

Without a Mac there is no built-in PDF and image reader. Two open-source tools fill the gap. The scripts
use them if they are installed and skip them if not:

| System | Install |
|---|---|
| Ubuntu or Debian | `sudo apt install poppler-utils tesseract-ocr` |
| Mac with Homebrew | `brew install poppler tesseract` |

## 0B.10 Check everything

```bash
python3 chapters/00-getting-started/check_setup.py
```

It prints one line per item: `ok`, `MISSING` (needed), or `optional`. It changes nothing. When Python
and Claude Code show `ok`, and one local server shows a model, you are ready for [Chapter 1](../01-files-and-folders/README.md).

## 0B.11 If something fails

| Symptom | Likely cause and fix |
|---|---|
| `command not found: lms` | Run `~/.lmstudio/bin/lms bootstrap`, then open a new terminal. |
| `lms load` is refused for memory | Lower `--context-length`, or pick a smaller model. |
| `curl` says "connection refused" | The server is not running. Run `lms server start` or `ollama serve`. |
| A script says "failed" for every file | The model name is wrong. Compare it with `lms ps` or `ollama list`. |
| Answers come back empty | The model spent its answer budget thinking. The scripts turn thinking off where the server allows it. See section 1B.6. |
| `Operation not permitted` on Desktop, Documents, Downloads or iCloud Drive | macOS is protecting the folder. Give the application that runs your terminal access in System Settings, Privacy & Security. See section 1D.13. |
| Everything is slow | Another model is still loaded. `lms ps`, then `lms unload --all`. |

## Common tasks

| I want to... | Run | How often |
|---|---|---|
| Start LM Studio's server and load a model | `lms server start`, then `lms load google/gemma-4-12b --identifier classifier --context-length 6144` | Each work session |
| Stop it and free the memory | `lms unload --all`, then `lms server stop` | After each session |
| See what is loaded | `lms ps` | When unsure |
| Start Ollama | `ollama serve` | Each session |
| List downloaded models | `lms ls` or `ollama list` | When needed |
| Check that a server answers | `curl -s http://localhost:1234/v1/models` | When something fails |
| Check my whole setup | `python3 chapters/00-getting-started/check_setup.py` | After changes |
