"""
main.py — Entry point for NOVA.

Run modes:
  cli   — type commands in the terminal (default)
  voice — continuous microphone listening
  gui   — graphical chat window with text + mic input

Example:
  python main.py --mode gui --lang en-IN
"""

import argparse
from utils.logger import get_logger

logger = get_logger("main")


def main():
    """Parse CLI args, create Nova instance, and start the chosen interface."""
    parser = argparse.ArgumentParser(description="NOVA - Next-gen Operative Voice Assistant")
    parser.add_argument("--mode", choices=["gui", "voice", "cli"], default="cli")
    parser.add_argument("--lang", default="en-IN", help="Language code e.g. en-IN, hi-IN, fr-FR")
    args = parser.parse_args()

    logger.info(f"Starting NOVA | Mode: {args.mode} | Language: {args.lang}")

    from core.nova import get_nova
    nova = get_nova(language=args.lang)

    if args.mode == "gui":
        from gui.app import run_gui
        run_gui(nova)
    elif args.mode == "voice":
        from voice.listener import run_voice_mode
        run_voice_mode(nova)
    else:
        run_cli(nova)


def run_cli(nova):
    """Interactive text loop: read user input, process, speak response."""
    print("\n" + "="*50)
    print("  N O V A — Next-gen Operative Voice Assistant")
    print("  Type a command. Type 'bye' to exit.")
    print("="*50 + "\n")
    nova.greet()
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "bye"):
                nova.say(nova.responses.goodbye())
                break
            nova.process_command(user_input)
            print()
        except KeyboardInterrupt:
            nova.say("Shutting down. Goodbye!")
            break


if __name__ == "__main__":
    main()
