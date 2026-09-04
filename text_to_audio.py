#!/usr/bin/env python3
"""
Script to convert text into an audio file using text-to-speech.

Supports two engines:
- pyttsx3: offline synthesis (typically writes WAV reliably)
- gTTS: online synthesis via Google TTS (writes MP3)
"""

import argparse
import os
import subprocess
import sys


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Convert text to audio")
    parser.add_argument("--text", default=None,
                        help="Text to convert to speech")
    parser.add_argument("--input-file", "-i", default=None,
                        help="Path to a UTF-8 text file")
    parser.add_argument("--output", "-o", default="output.wav",
                        help="Output audio file path (e.g., output.wav or output.mp3)")
    parser.add_argument("--engine", choices=["pyttsx3", "gtts", "termux"], default="pyttsx3",
                        help="TTS engine to use")
    parser.add_argument("--rate", type=int, default=180,
                        help="Speech rate for pyttsx3")
    parser.add_argument("--volume", type=float, default=1.0,
                        help="Volume for pyttsx3 (0.0 to 1.0)")
    parser.add_argument("--lang", default="en",
                        help="Language code for gTTS (for example: en, es, fr)")
    parser.add_argument("--auto-audio", action=argparse.BooleanOptionalAction, default=True,
                        help="Play audio automatically after synthesis. Default: enabled")
    args = parser.parse_args()

    output_file = args.output
    if args.engine == "gtts" and output_file == "output.wav":
        output_file = "output.mp3"

    text = load_text(direct_text=args.text, input_file=args.input_file)
    if text is None:
        sys.exit(1)

    if args.engine == "pyttsx3":
        success = synthesize_with_pyttsx3(
            text=text,
            output_file=output_file,
            rate=args.rate,
            volume=max(0.0, min(args.volume, 1.0)),
            auto_audio=args.auto_audio,
        )
    elif args.engine == "gtts":
        success = synthesize_with_gtts(
            text=text,
            output_file=output_file,
            lang=args.lang,
        )
        if success and args.auto_audio:
            play_audio_file(output_file)
    else:
        success = termux_speak(
            text=text,
            output_file=output_file,
            rate=args.rate,
            lang=args.lang,
        )

    if not success:
        sys.exit(1)

    if args.auto_audio:
        if args.engine == "pyttsx3":
            print("Audio played through speakers.")
        elif args.engine == "termux":
            print("Audio played through Termux.")
        else:
            print(f"Audio saved to {output_file} and opened for playback.")
    else:
        print(f"Audio saved to {output_file}")


def load_text(direct_text=None, input_file=None):
    """Load text from --text or --input-file."""
    if direct_text and input_file:
        print("Error: Provide either --text or --input-file, not both.")
        return None

    if direct_text:
        text = direct_text.strip()
        if not text:
            print("Error: --text cannot be empty.")
            return None
        return text

    if input_file:
        if not os.path.exists(input_file):
            print(f"Error: Input file not found: {input_file}")
            return None
        try:
            with open(input_file, "r", encoding="utf-8") as file:
                text = file.read().strip()
            if not text:
                print(f"Error: Input file is empty: {input_file}")
                return None
            return text
        except OSError as err:
            print(f"Error reading input file: {err}")
            return None

    print("Error: You must provide --text or --input-file.")
    return None


def synthesize_with_pyttsx3(text, output_file, rate=180, volume=1.0, auto_audio=False):
    """Convert text to speech using pyttsx3 (offline)."""
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 is not installed. Install with: pip install pyttsx3")
        return False

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.setProperty("volume", volume)
        if auto_audio:
            engine.say(text)
        else:
            engine.save_to_file(text, output_file)
        engine.runAndWait()
        return True
    except Exception as err:
        print(f"pyttsx3 error: {err}")
        return False


def synthesize_with_gtts(text, output_file, lang="en"):
    """Convert text to speech using gTTS (online)."""
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS is not installed. Install with: pip install gTTS")
        return False

    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(output_file)
        return True
    except Exception as err:
        print(f"gTTS error: {err}")
        return False


def play_audio_file(output_file):
    """Play an audio file with the system default player."""
    try:
        os.startfile(output_file)
        return True
    except OSError as err:
        print(f"Could not auto-play file: {err}")
        return False


def termux_speak(text, output_file, rate=180, lang="en"):
    """Speak text using Termux TTS (termux-tts-speak)."""
    try:
        # termux-tts-speak is available in Termux on Android.
        command = ["termux-tts-speak"]

        if lang:
            command.extend(["-l", str(lang)])

        # Convert pyttsx3-like rate to a termux-compatible float range.
        if rate is not None:
            normalized_rate = max(0.1, min(float(rate) / 180.0, 2.0))
            command.extend(["-r", f"{normalized_rate:.2f}"])

        if output_file and os.path.exists(output_file):
            command.append(output_file)
        else:
            command.append(text)
        subprocess.run(command, check=True)
        return True
    except FileNotFoundError:
        print("termux-tts-speak not found. This engine requires Termux on Android.")
        return False
    except subprocess.CalledProcessError as err:
        print(f"termux-tts-speak failed: {err}")
        return False
    except ValueError:
        print("Invalid rate value for termux engine.")
        return False


if __name__ == "__main__":
    main()
