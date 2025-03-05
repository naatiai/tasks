import whisper
import torch

def transcribe(audio_file, language):
    """
    Transcribes the given audio data using the Whisper speech recognition model.

    Args:
        audio_np: The audio data to be transcribed.

    Returns:
        str: The transcribed text.
    """
    # Load Whisper Model
    model = whisper.load_model("small")  # or base
    torch.cuda.empty_cache()
    # stt = whisper.load_model("small")  # or base
    # Set fp16=True if using a GPU
    # audio = model.load_audio(audio_file)
    result = model.transcribe(audio_file, fp16=True, language=language)
    return result