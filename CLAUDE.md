# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A minimal Python TUI chat app that connects to a local Ollama instance with tool-calling support. Single-file app (`chat.py`) using a readline-based `input()` loop — no TUI framework.

## Setup & Run

```bash
conda create -p ./.venv python=3.11 -y
conda activate ./.venv
pip install -r requirements.txt
python chat.py
```

Requires a running Ollama server with the `llama3.2` model pulled (`ollama pull llama3.2`).

## Architecture

`chat.py` is the entire application:

- **Tool system**: Tools are defined as Ollama JSON function specs in the `tools` list, with corresponding implementations in the `TOOL_FUNCTIONS` dict. To add a new tool, add an entry to both.
- **Chat loop**: Maintains a `messages` list as conversation history. After each `ollama.chat()` call, if the response contains tool calls, it executes them, appends results as `role: "tool"` messages, and re-calls the model in a loop until no more tool calls remain.
- **Model**: Uses `llama3.2` (mapped to `llama3.2:latest` in Ollama).
