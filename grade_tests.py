import os
from supabase import create_client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
# from pydub import AudioSegment
from helpers import fetch_mock_answers, grade_translation, ollama_grade_translation, openai_transcribe, transcribe, update_user_mock, update_mock_answer, delete_supabase_file, extract_score
import whisper

# Load environment variables from .env file
load_dotenv()


# Validate Supabase and Database URLs
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")
DATABASE_URL = os.getenv("POSTGRES_URL")
API_KEY = os.getenv("OPENAI_API_KEY")
download_folder = os.getenv("DOWNLOADS_FOLDER")
prefix = os.getenv("SUPABASE_PREFIX")


# if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_BUCKET or not DATABASE_URL or API_KEY:
#     raise ValueError(
#         "[-] Ensure SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET, API_KEY and POSTGRES_URL are set in the .env file.")


# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create a database session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Fetch the mock answers with null transcript and score
mock_answers = fetch_mock_answers(session)

# Ensure the download directory exists
os.makedirs(download_folder, exist_ok=True)

# # Process and download files
for i, qa in enumerate(mock_answers):
    # print("MOCK QA:", answer)
    try:
        file_name = qa[0].audio_file_url.strip().split(
            '/')[-1]  # Strip spaces and get file name from Answers

        # Save the file locally
        local_path = os.path.join(download_folder, os.path.basename(file_name))
        response = supabase.storage.from_(
            SUPABASE_BUCKET).download(f"{prefix}/{file_name}")

        with open(local_path, "wb") as f:
            f.write(response)
        print(f"[+] Downloaded: {local_path}")

    except Exception as e:
        print(f"[-] Error downloading file {file_name}: {e}, Loop {i}")
        continue

    # try:
    #     # Set the output file name to have a .wav extension
    #     output_file = f"{prefix}/{os.path.splitext(file_name)[0]}.wav"

    #     # Convert and export to .wav format
    #     AudioSegment.from_file(f"{download_folder}/{file_name}", format="webm").export(
    #         output_file, format="wav"
    #     )
    #     print(f"[+] Successfully converted {file_name} to {output_file}")

    #     # Delete the original .webm file
    #     os.remove(f"{download_folder}/{file_name}")
    #     print(f"[+] Deleted original file: {file_name}")
    # except Exception as ex:
    #     print(f"[-] Error converting file {file_name}: {ex}")

    try:
        # Get Ans Language from Questions
        ans_lang = str(qa[1].answer_language).title()

        # Transcribe
        # transcription = transcribe(
        # f"{download_folder}/{file_name}", language=ans_lang)

        transcription = openai_transcribe(
            f"{download_folder}/{file_name}", language=ans_lang, api_key=API_KEY)
        # transcription = transcription['text']

    except Exception as ex:
        print(f"[-] Error transcribing audio {file_name}: {ex}, Loop {i}")
        continue

    try:
        # Grading
        ref_answer = qa[1].transcript
        user_answer = transcription
        # score = ollama_grade_translation(ref_answer, user_answer, language=ans_lang)
        score = grade_translation(
            ref_answer, user_answer, API_KEY, language=ans_lang)
        print("[+] Score:", score)

    except Exception as ex:
        print(f"[-] Error Grading Transcription {file_name}: {ex}, Loop {i}")
        continue

    # Update Mock Answers
    is_it_correct = None
    # checked_score = extract_score(response)
    score = score.strip().replace('.', '')
    if not score.isdigit():
        checked_score = 0
    else:
        checked_score = int(score)
    print("Checked Score ", checked_score)

    try:
        if checked_score >= 3:
            is_it_correct = True
        else:
            is_it_correct = False
    except Exception:
        is_it_correct = False
    print("Correct ", is_it_correct)

# Update Mock Answers
    try:
        result = update_mock_answer(
            session=session,
            mock_question_id=qa[0].mock_question_id,
            user_mock_id=qa[0].user_mock_id,
            user_id=qa[0].user_id,
            transcript=transcription,
            score=checked_score,
            is_correct=is_it_correct,
            mock_id=qa[1].mock_id
        )

        if result:
            print("MockAnswers updated successfully.")
        else:
            print("Failed to update MockAnswers.")
            continue
    except Exception as ex:
        print(f"[-] Error updaring Answer: {ex}, Loop {i}")
        continue


# Delete Audio File from Supabase
    # try:
    #     # Delete the file
    #     success = delete_supabase_file(
    #         prefix, file_name, SUPABASE_BUCKET, SUPABASE_URL, SUPABASE_KEY)

    #     if success:
    #         print("File deleted successfully.")
    #     else:
    #         print("Failed to delete the file.")

    # except Exception as ex:
    #     print(f"[-] Error updaring userMock: {ex}, Loop {i}")

# Close the session
session.close()
