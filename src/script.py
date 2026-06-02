import getpass
import json
import os
import shlex
from urllib import error, request

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant talking to a user in a terminal chat app. "
    "Keep answers clear and concise unless more detail is requested."
)


def get_default_temperature():
    raw_value = os.getenv("OPENAI_TEMPERATURE", "0.7")
    try:
        return float(raw_value)
    except ValueError:
        return 0.7


DEFAULT_TEMPERATURE = get_default_temperature()


def make_system_message(system_prompt):
    return {"role": "system", "content": system_prompt}


def reset_conversation(state):
    state["messages"] = [make_system_message(state["system_prompt"])]


def mask_api_key(api_key):
    if not api_key:
        return "(not set)"
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def get_active_api_key(state):
    return state.get("session_api_key") or os.getenv("OPENAI_API_KEY") or ""


def get_api_key_source(state):
    if state.get("session_api_key"):
        return "session"
    if os.getenv("OPENAI_API_KEY"):
        return "environment"
    return "none"


def prompt_for_api_key(prompt_text):
    try:
        return getpass.getpass(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.\n")
        return ""


def set_api_key(state, api_key):
    api_key = api_key.strip()
    if not api_key:
        raise RuntimeError("API key cannot be empty.")

    state["session_api_key"] = api_key


def clear_api_key(state):
    state["session_api_key"] = ""


def normalize_content(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        if parts:
            return "".join(parts)

    return str(content)


def call_openai(messages, *, api_key, model, temperature):
    if not api_key:
        raise RuntimeError(
            "No API key is set. Use /key to enter one, or set OPENAI_API_KEY."
        )

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    req = request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
        return normalize_content(content)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected API response: {body}") from exc


def print_history(state, limit=None):
    conversation = state["messages"][1:]
    if not conversation:
        print("No chat messages yet.\n")
        return

    if limit is not None:
        conversation = conversation[-limit:]

    print()
    for index, message in enumerate(conversation, start=1):
        role = message.get("role", "unknown").capitalize()
        content = normalize_content(message.get("content", ""))
        print(f"[{index}] {role}: {content}")
    print()


def print_last_reply(state):
    for message in reversed(state["messages"]):
        if message.get("role") == "assistant":
            print(f"Assistant: {normalize_content(message.get('content', ''))}\n")
            return
    print("No assistant reply yet.\n")


def print_stats(state):
    conversation = state["messages"][1:]
    user_count = sum(1 for message in conversation if message.get("role") == "user")
    assistant_count = sum(
        1 for message in conversation if message.get("role") == "assistant"
    )
    char_count = sum(
        len(normalize_content(message.get("content", ""))) for message in conversation
    )

    print(
        f"\nConversation stats:\n"
        f"  User messages: {user_count}\n"
        f"  Assistant messages: {assistant_count}\n"
        f"  Total messages: {len(conversation)}\n"
        f"  Characters: {char_count}\n"
    )


def pop_last_turn(state):
    removed = []

    if len(state["messages"]) <= 1:
        return removed

    if state["messages"][-1].get("role") == "assistant":
        removed.append(state["messages"].pop())

    if len(state["messages"]) > 1 and state["messages"][-1].get("role") == "user":
        removed.append(state["messages"].pop())

    if not removed and len(state["messages"]) > 1:
        removed.append(state["messages"].pop())

    return removed


def print_help():
    print(
        """
Available slash commands:
  /help                 Show this help message
  /status               Show current settings and chat status
  /stats                Show conversation stats
  /key                  Securely prompt for an API key for this run only
  /key show             Show masked active API key and where it came from
  /key set <key>        Set API key for this run only
  /key clear            Clear the in-memory session API key
  /clear                Clear the current conversation
  /history [n]          Show the full chat history or the last n messages
  /last                 Show the last assistant reply again
  /system               Show the current system prompt
  /system <text>        Set a new system prompt and reset the conversation
  /model                Show current model
  /model <name>         Set the model name
  /temp                 Show current temperature
  /temp <0-2>           Set the temperature
  /pop                  Remove the last user/assistant turn
  /retry                Regenerate the last assistant reply
  /exit                 Quit the program

Notes:
  - No external files are used.
  - API keys are only kept in memory for the current run unless you use OPENAI_API_KEY.

Compatibility shortcuts:
  exit, quit, clear
"""
    )


def print_status(state):
    message_count = max(len(state["messages"]) - 1, 0)
    print(
        f"\nModel: {state['model']}\n"
        f"Temperature: {state['temperature']}\n"
        f"Messages: {message_count}\n"
        f"API key: {mask_api_key(get_active_api_key(state))}\n"
        f"API key source: {get_api_key_source(state)}\n"
        f"Persistence: disabled (no external files)\n"
        f"System prompt: {state['system_prompt']}\n"
    )


def send_user_message(state, user_input):
    state["messages"].append({"role": "user", "content": user_input})

    try:
        reply = call_openai(
            state["messages"],
            api_key=get_active_api_key(state),
            model=state["model"],
            temperature=state["temperature"],
        )
    except RuntimeError:
        state["messages"].pop()
        raise

    state["messages"].append({"role": "assistant", "content": reply})
    return reply


def retry_last_reply(state):
    if len(state["messages"]) <= 1:
        raise RuntimeError("There is nothing to retry yet.")

    removed_assistant = None
    if state["messages"][-1].get("role") == "assistant":
        removed_assistant = state["messages"].pop()

    if state["messages"][-1].get("role") != "user":
        if removed_assistant is not None:
            state["messages"].append(removed_assistant)
        raise RuntimeError(
            "The last message is not a user message, so it cannot be retried."
        )

    try:
        reply = call_openai(
            state["messages"],
            api_key=get_active_api_key(state),
            model=state["model"],
            temperature=state["temperature"],
        )
    except RuntimeError:
        if removed_assistant is not None:
            state["messages"].append(removed_assistant)
        raise

    state["messages"].append({"role": "assistant", "content": reply})
    return reply


def handle_key_command(args, state):
    if not args:
        api_key = prompt_for_api_key("OpenAI API key (session only): ")
        if not api_key:
            return
        set_api_key(state, api_key)
        print("Session API key set.\n")
        return

    subcommand = args[0].lower()

    if subcommand == "show":
        print(
            f"Active API key: {mask_api_key(get_active_api_key(state))}\n"
            f"Source: {get_api_key_source(state)}\n"
        )
        return

    if subcommand == "clear":
        clear_api_key(state)
        print("Session API key cleared.\n")
        return

    if subcommand in {"session", "set"}:
        api_key = " ".join(args[1:]).strip()
        if not api_key:
            api_key = prompt_for_api_key("OpenAI API key (session only): ")
        if not api_key:
            return
        set_api_key(state, api_key)
        print("Session API key set.\n")
        return

    if subcommand in {"save", "load"}:
        raise RuntimeError(
            "External-file key storage is disabled. Use /key or /key set for this run only."
        )

    set_api_key(state, " ".join(args))
    print("Session API key set.\n")


def handle_command(command_text, state):
    try:
        parts = shlex.split(command_text)
    except ValueError as exc:
        print(f"Command parse error: {exc}\n")
        return True

    if not parts:
        return True

    command = parts[0].lower()
    args = parts[1:]

    try:
        if command in {"/help", "/?", "/commands"}:
            print_help()
            return True

        if command in {"/exit", "/quit"}:
            return False

        if command in {"/clear", "/new"}:
            reset_conversation(state)
            print("Conversation cleared.\n")
            return True

        if command == "/key":
            handle_key_command(args, state)
            return True

        if command == "/status":
            print_status(state)
            return True

        if command == "/stats":
            print_stats(state)
            return True

        if command == "/last":
            print_last_reply(state)
            return True

        if command == "/model":
            if not args:
                print(f"Current model: {state['model']}\n")
            else:
                state["model"] = " ".join(args).strip()
                print(f"Model set to: {state['model']}\n")
            return True

        if command == "/temp":
            if not args:
                print(f"Current temperature: {state['temperature']}\n")
                return True

            try:
                temperature = float(args[0])
            except ValueError as exc:
                raise RuntimeError(
                    "Temperature must be a number between 0 and 2."
                ) from exc

            if not 0 <= temperature <= 2:
                raise RuntimeError("Temperature must be between 0 and 2.")

            state["temperature"] = temperature
            print(f"Temperature set to: {state['temperature']}\n")
            return True

        if command == "/system":
            if not args:
                print(f"Current system prompt:\n{state['system_prompt']}\n")
            else:
                state["system_prompt"] = " ".join(args).strip()
                reset_conversation(state)
                print("System prompt updated. Conversation reset.\n")
            return True

        if command == "/history":
            limit = None
            if args:
                try:
                    limit = int(args[0])
                except ValueError as exc:
                    raise RuntimeError("Usage: /history [n]") from exc
                if limit <= 0:
                    raise RuntimeError("History count must be greater than 0.")
            print_history(state, limit)
            return True

        if command in {"/save", "/load"}:
            raise RuntimeError("External save/load features are disabled.")

        if command == "/pop":
            removed = pop_last_turn(state)
            if removed:
                print("Last turn removed.\n")
            else:
                print("Nothing to remove.\n")
            return True

        if command == "/retry":
            reply = retry_last_reply(state)
            print(f"Assistant: {reply}\n")
            return True

        print(f"Unknown command: {command}. Use /help to see available commands.\n")
        return True

    except RuntimeError as exc:
        print(f"Error: {exc}\n")
        return True


def main():
    state = {
        "session_api_key": "",
        "model": DEFAULT_MODEL,
        "temperature": DEFAULT_TEMPERATURE,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "messages": [],
    }
    reset_conversation(state)

    print("OpenAI Terminal Chat")
    print(f"Model: {state['model']}")
    print("Use /help to see slash commands.")
    print("Use /key to securely set your API key for this run.")

    if get_active_api_key(state):
        print(
            f"API key detected from {get_api_key_source(state)}: "
            f"{mask_api_key(get_active_api_key(state))}\n"
        )
    else:
        print("No API key set yet. Use /key before sending a message.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in {"exit", "quit"}:
            print("Goodbye!")
            break

        if lowered == "clear":
            reset_conversation(state)
            print("Conversation cleared.\n")
            continue

        if user_input.startswith("/"):
            should_continue = handle_command(user_input, state)
            if not should_continue:
                print("Goodbye!")
                break
            continue

        try:
            reply = send_user_message(state, user_input)
        except RuntimeError as exc:
            print(f"Error: {exc}\n")
            continue

        print(f"Assistant: {reply}\n")


if __name__ == "__main__":
    main()
