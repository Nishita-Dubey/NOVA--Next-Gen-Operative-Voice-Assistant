"""
voice/listener.py — Continuous voice mode loop.

Used when running: python main.py --mode voice
Listens → transcribes → process_command → repeat until user says bye.
"""

from voice.speech_recognition_engine import get_speech_engine
from utils.logger import get_logger

logger = get_logger("listener")


def run_voice_mode(nova):
    """Main loop for hands-free voice interaction."""
    print("\n" + "="*50)
    print("  NOVA — Voice Mode Active")
    print("  Speak your command. Say 'bye' to exit.")
    print("="*50 + "\n")

    nova.greet()
    speech_engine = get_speech_engine(language=nova.language)

    while True:
        try:
            text = speech_engine.listen()
            if not text:
                continue
            print(f"You said: {text}")
            # Exit phrases handled here (not only via intent recognizer)
            if any(w in text.lower() for w in ["bye", "goodbye", "exit", "quit", "close nova"]):
                nova.say(nova.responses.goodbye())
                break
            result = nova.process_command(text)
            print(f"NOVA: {result['response']}\n")
        except KeyboardInterrupt:
            nova.say("Shutting down. Goodbye!")
            break
