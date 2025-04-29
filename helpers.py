import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import re
import requests
from dotenv import load_dotenv

import whisper
from supabase import create_client
# from supabase.storage import StorageException
from sqlalchemy.exc import NoResultFound
from ollama import Client
from openai import OpenAI
# import whisper
import torch
from langcodes import Language

from models.schema import MockAnswers, MockQuestions, UserMocks, Subscriptions
from sqlalchemy.orm import Session
from sqlalchemy import and_
# from sqlalchemy.orm import joinedload

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


def get_mock_question_count(session, mock_id):
    """Fetch the total number of questions for a given mock test."""
    return session.query(MockQuestions).filter(MockQuestions.mock_id == mock_id).count()


def extract_score(ai_response) -> int:
    """
    Extracts a numeric score (0-5) from an AI response. Returns 0 if parsing fails.

    Args:
        ai_response (str or bytes): The response from the AI, which may contain just a number 
                                    or additional text alongside the score.

    Returns:
        int: The extracted score between 0 and 5, or 0 if invalid or parsing fails.
    """
    try:
        # Ensure the input is a string
        if isinstance(ai_response, bytes):
            ai_response = ai_response.decode("utf-8", errors="ignore")
        elif not isinstance(ai_response, str):
            print("-> Invalid input type, converting to empty string.")
            ai_response = ""

        # Try to parse the response as a standalone number
        stripped_response = ai_response.strip()
        if stripped_response.isdigit():
            score = int(stripped_response)
            return score if 0 <= score <= 5 else 0

        # If not a standalone number, look for a "score: x" pattern
        match = re.search(r"score\s*:\s*(\d+)", ai_response, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            return score if 0 <= score <= 5 else 0

        # If no valid score found, return 0
        return 0
    except Exception as e:
        print(f"-> Error extracting score: {e}")
        return 0


def get_user_mocks(session: Session):
    """
    Fetch all UserMocks with total_score as NULL and attempts as 0,
    only for users whose subscription has payment_required = False.

    Args:
        session (Session): SQLAlchemy database session object.

    Returns:
        List[UserMocks]: A list of UserMocks objects matching the criteria.
    """
    try:
        results = session.query(UserMocks).join(
            Subscriptions, UserMocks.user_id == Subscriptions.user_id
        ).filter(
            and_(
                UserMocks.total_score.is_(None),
                UserMocks.attempts == 0,
                Subscriptions.payment_required == False
            )
        ).all()
        return results
    except Exception as e:
        print(f"-> Error fetching UserMocks: {e}")
        return []


def get_mock_answers_by_user_mock_id(session: Session, user_mock_id: str):
    """
    Fetch all MockAnswers associated with a given user_mock_id.

    Args:
        session (Session): SQLAlchemy database session object.
        user_mock_id (str): The ID of the UserMock.

    Returns:
        List[MockAnswers]: A list of MockAnswers objects linked to the given user_mock_id.
    """
    try:
        results = session.query(MockAnswers).filter(
            MockAnswers.user_mock_id == user_mock_id
        ).all()
        return results
    except Exception as e:
        print(
            f"-> Error fetching MockAnswers for user_mock_id {user_mock_id}: {e}")
        return []


def fetch_mock_answers(session: Session):
    """
    Fetch all mock_answers where transcript and score are NULL,
    and only for users whose subscription has payment_required = False.
    Includes the answer_language from the mock_questions table.

    Args:
        session (Session): SQLAlchemy database session object.

    Returns:
        List[tuple]: A list of tuples, each containing a MockAnswers object 
                     and the corresponding MockQuestions object.
    """

    results = session.query(MockAnswers, MockQuestions).join(
        MockQuestions, MockAnswers.mock_question_id == MockQuestions.id
    ).join(
        Subscriptions, MockAnswers.user_id == Subscriptions.user_id
    ).filter(
        and_(
            MockAnswers.transcript == None,
            MockAnswers.score == None,
            Subscriptions.payment_required == False
        )
    ).all()

    return results


def update_user_mock(session: Session, user_mock_id: str, user_id: str, attempts_increment: int, total_score: int, passed: bool):
    """
    Update the UserMocks record with the given parameters.

    Args:
        session (Session): SQLAlchemy session.
        user_mock_id (str): The ID of the UserMocks record to update.
        user_id (str): The ID of the user associated with the UserMocks record.
        attempts_increment (int): Value to increment the attempts by.
        total_score (int): New total score.
        passed (bool): New passed status.

    Returns:
        bool: True if update is successful, False otherwise.
    """
    try:
        # Fetch the UserMocks record
        user_mock = session.query(UserMocks).filter_by(
            id=user_mock_id, user_id=user_id).one()

        # Update the fields
        user_mock.attempts += attempts_increment
        user_mock.total_score = total_score
        user_mock.passed = passed

        # Commit the changes
        session.commit()
        return True
    except NoResultFound:
        print(
            f"-> No UserMocks record found for id: {user_mock_id} and user_id: {user_id}")
        return False
    except Exception as e:
        session.rollback()
        print(f"-> Error updating UserMocks: {e}")
        return False


def update_mock_answer(session: Session, mock_question_id: str, user_mock_id: str, user_id: str, transcript: str, score: int, is_correct: bool, mock_id: str):
    """
    Update the MockAnswers record with the given parameters.

    Args:
        session (Session): SQLAlchemy session.
        mock_question_id (str): The ID of the mock question associated with the answer.
        user_mock_id (str): The ID of the UserMocks record.
        user_id (str): The ID of the user associated with the record.
        transcript (str): The transcript to update.
        score (int): The score to update.
        is_correct (bool): Whether the answer is correct.
        mock_id (str): The ID of the mock associated with the answer.

    Returns:
        bool: True if the update is successful, False otherwise.
    """
    try:
        # Fetch the MockAnswers record
        mock_answer = session.query(MockAnswers).filter_by(
            mock_question_id=mock_question_id,
            user_mock_id=user_mock_id,
            user_id=user_id,
            # mock_id=mock_id
        ).one()

        # Update the fields
        mock_answer.transcript = transcript
        mock_answer.score = score
        mock_answer.is_correct = is_correct
        mock_answer.mock_id = mock_id

        # Commit the changes
        session.commit()
        return True
    except NoResultFound:
        print(
            f"-> No MockAnswers record found for mock_question_id: {mock_question_id} user_mock_id: {user_mock_id} and user_id: {user_id}")
        return False
    except Exception as e:
        session.rollback()
        print(f"-> Error updating MockAnswers: {e}")
        return False


def delete_supabase_file(path_prefix: str, file_name: str, bucket_name: str, supabase_url: str, supabase_key: str) -> bool:
    """
    Delete a file from a Supabase storage bucket.

    Args:
        path_prefix (str): The folder path within the bucket (prefix).
        file_name (str): The name of the file to delete.
        bucket_name (str): The name of the Supabase storage bucket.
        supabase_url (str): The Supabase project URL.
        supabase_key (str): The Supabase project API key.

    Returns:
        bool: True if the file is deleted successfully, False otherwise.
    """
    try:
        # I-> nitialize Supabase client
        supabase = create_client(supabase_url, supabase_key)

        # Construct the full file path
        file_path = f"{path_prefix}/{file_name}".lstrip("/")

        # Delete the file
        response = supabase.storage.from_(bucket_name).remove([file_path])

        # Check the response for successful deletion
        if response:
            print(f"-> File '{file_path}' successfully deleted.")
            return True
        else:
            print(
                f"-> Failed to delete file '{file_path}'. Response: {response}")
            return False
    except Exception as e:
        print(f"-> Supabase Storage Exception: {e}")
        return False
    except Exception as e:
        print(f"-> Error deleting file: {e}")
        return False


def grade_translation(reference, answer, api_key, language):

    # prompt = f"""
    # You need to evaluate a user's translation test. You will be provided with two texts in {language}: a reference answer and a student's answer.

    # Reference:
    # {reference}

    # Answer:
    # {answer}

    # Your task is to:
    # 1. Compare the two texts based on **accuracy** (matching details and content) and **correctness** (faithful interpretation of the reference).
    # 2. Ignore differences in punctuation, spaces, or minor grammatical errors unless they affect the correctness or interpretation of the text.
    # 3. Focus specifically on how well the student's response matches the intended meaning and correctness of the reference text.

    # Provide a score out of 5, where:
    # - 5 = Perfect match, fully accurate and correct interpretation.
    # - 4 = Very minor errors that don't affect overall correctness.
    # - 3 = Noticeable errors but the general meaning is retained.
    # - 2 = Significant errors that distort meaning but show some understanding.
    # - 1 = Poor understanding or largely incorrect.
    # - 0 = No resemblance.

    # Return only the numeric score (0-5). Do not include any explanations or other text in your response.
    # """

    prompt = f"""
    Evaluate this {language} translation test comparing reference and student answer:
    Reference:
    {reference}
    Answer:
    {answer}

    Compare based on:
    1. Accuracy: Exact match of details, numbers, names
    2. Correctness: Precise meaning preservation
    3. Completeness: All essential information included

    Mark down for:
    - Omissions/additions
    - Tone/emphasis changes
    - Meaning-altering word choices
    - Word count mismatch (-1 point if different) 

    Ignore only:
    - Spacing, formatting
    - Capitalization (except proper nouns)
    - Minor article usage if meaning intact

    Score (0-5):
    5: Perfect match
    4: 1-2 minor word variations
    3: 3-4 minor or 1 moderate error
    2: Multiple moderate or 1-2 major errors
    1: Significant meaning alterations
    0: Incomprehensible/incorrect

    Return only numeric score (0-5).
    """
    client = OpenAI(
        api_key=api_key
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model="gpt-4o-mini",
    )
    return chat_completion.choices[0].message.content


def ollama_grade_translation(reference, answer, language):

    prompt = f"""
    You need to evaluate a user's translation test. You will be provided with two texts in {language}: a reference answer and a student's answer. 

    Reference:
    {reference}

    Answer:
    {answer}

    Your task is to:
    1. Compare the two texts based on **accuracy** (matching details and content), **correctness** (faithful interpretation of the reference), **grammar** and **consistency** in the language written (no mixing of languages).
    2. Ignore differences in punctuation, spaces, spelling errors unless they affect the grammar, correctness or interpretation of the text.
    3. Focus on how well the student's response matches the intended meaning and correctness of the reference text and how clear it is to someone who only speaks that language.
    4. Only return the score, no explanation.
    
    Provide a score out of 5, where:
    - 5 = Perfect match, fully accurate and correct interpretation.
    - 4 = Very minor errors that don't affect overall correctness.
    - 3 = Noticeable errors but the general meaning is retained.
    - 2 = Significant errors that distort meaning but show some understanding.
    - 1 = Poor understanding or largely incorrect.
    - 0 = No resemblance.

    Return only the numeric score (0-5). DO NOT include any explanations or other text in your response. If you encounter an error just return a score of 0.
    """
    client = Client(
        #    host='http://192.168.1.216:7000',
        host='http://localhost:11434'
    )
    response = client.chat(model='llama3.2', messages=[
        {
            'role': 'user',
            'content': prompt
        },
    ])
    # or access fields directly from the response object
    return response.message.content


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


def openai_transcribe(audio_file, language, api_key):
    """
    Transcribes the given audio data using the Whisper speech recognition model.

    Args:
        audio_np: The audio data to be transcribed.

    Returns:
        str: The transcribed text.
    """
    client = OpenAI(api_key=api_key)

    if language.lower() == "english":
        iso_lang = "en"
    elif language.lower() == "hindi":
        iso_lang = "hi"
    elif language.lower() == "mandarin":
        iso_lang = "zh"
    elif language.lower() == "tamil":
        iso_lang = "ta"
    if language.lower() == "punjabi":
        iso_lang = "pa"
    else:
        iso_lang = "en"
    lang = Language.get(iso_lang).is_valid()
    # lang = Language.get(language[:3]).is_valid()
    print(f"-> Language: {language} {iso_lang} {lang}")
    if lang is True:
        # lang = Language.get(iso_lang).to_tag()
        # iso_lang = Language.get(language[:3]).to_tag()
        audio_file = open(audio_file, "rb")
        translation = client.audio.transcriptions.create(
            model="whisper-1",
            language=iso_lang,
            file=audio_file,
        )
    else:
        audio_file = open(audio_file, "rb")
        translation = client.audio.transcriptions.create(
            model="whisper-1",
            # language=iso_lang,
            file=audio_file,
            # response_format="text"
        )
    print("-> Translation ", translation.text)
    return translation.text


def send_test_result_email(recipient_email: str, link: str, passed: bool):
    """
    Sends an email to notify the user of their test result via Postmark.

    Args:
        recipient_email (str): The recipient's email address.
        link (str): The link to view detailed results.
        passed (bool): True if the user passed, False otherwise.
    """
    # Load environment variables
    load_dotenv()

    POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")
    EMAIL_USER = os.getenv("EMAIL_USER", "support@naatininja.com")

    if not POSTMARK_API_TOKEN:
        raise ValueError(
            "[-] POSTMARK_API_TOKEN must be set in the environment variables.")

    # Email content templates
    # Email content templates
    passed_template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #ddd;">
            <div style="text-align: center; padding: 20px 0; color: black;">
                <img src='https://app.naatininja.com/logo.png' alt='NAATI Ninja' style='width: 150px; margin-bottom: 20px;'>
                <h1 style="color: #333;">Fantastic News, You Passed! 🎉</h1>
            </div>
            <div style="padding: 20px; font-size: 16px; color: #333;">
                <p>Great job! Your test has been graded, and we're excited to let you know that you've <b>passed</b>! All your effort and dedication have paid off. 🎊</p>
                <p>Click below to view your detailed results:</p>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{link}" style="padding: 12px 24px; background-color: #f7941e; color: white; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">View Results</a>
                </div>
                <p style="margin-top: 20px;">Keep up the great work, and best of luck with your journey ahead!</p>
            </div>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <p style="font-size: 12px; text-align: center; color: #777;">This is an automated email. Please do not reply. If you need assistance, contact us at <a href="mailto:support@naatininja.com" style="color: #099f9e; text-decoration: none;">support@naatininja.com</a>.</p>
        </div>
    </body>
    </html>
    """

    failed_template = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #ddd;">
            <div style="text-align: center; padding: 20px 0; color: black;">
                <img src='https://app.naatininja.com/logo.png' alt='NAATI Ninja' style='width: 150px; margin-bottom: 20px;'>
                <h1 style="color: #333;">Don't Give Up – Keep Going! 💪</h1>
            </div>
            <div style="padding: 20px; font-size: 16px; color: #333;">
                <p>Your test has been graded, and unfortunately, you didn't pass this time. But don't be discouraged—this is just one step in your journey.</p>
                <p>Use this as an opportunity to improve and come back stronger! Click below to review your results and see where you can improve:</p>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{link}" style="padding: 12px 24px; background-color: #099f9e; color: white; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">View Results</a>
                </div>
                <p style="margin-top: 20px;">Remember, progress takes time, and every challenge is a learning experience. Keep pushing forward—we believe in you! 🚀</p>
            </div>
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <p style="font-size: 12px; text-align: center; color: #777;">This is an automated email. Please do not reply. If you need assistance, contact us at <a href="mailto:support@naatininja.com" style="color: #099f9e; text-decoration: none;">support@naatininja.com</a>.</p>
        </div>
    </body>
    </html>
    """

    subject = "🎉 Congratulations! You Passed Your NAATI Ninja Test" if passed else "📊 Keep Going! Your NAATI Ninja Test Results Are In"
    body = passed_template if passed else failed_template

    # Postmark API request
    postmark_url = "https://api.postmarkapp.com/email"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": POSTMARK_API_TOKEN
    }

    payload = {
        "From": EMAIL_USER,
        "To": recipient_email,
        "Subject": subject,
        "HtmlBody": body,
        "MessageStream": "outbound"
    }

    try:
        response = requests.post(postmark_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an error if request fails
        print(f"Email successfully sent to {recipient_email}")
    except requests.exceptions.RequestException as e:
        print(f"[-] Error sending email: {e}")


def fetch_user_from_clerk(user_id):
    """
    Fetches user data from Clerk API using the provided user ID.

    Args:
        user_id (str): The ID of the user to fetch.

    Returns:
        dict: User data if found, otherwise None.
    """
    # Load environment variables
    load_dotenv()

    # Get the Clerk secret key from environment variables
    CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
    if not CLERK_SECRET_KEY:
        raise ValueError("CLERK_SECRET_KEY environment variable is not set.")

    # Define the Clerk API URL
    clerk_api_url = f"https://api.clerk.dev/v1/users/{user_id}"

    try:
        # Make a GET request to fetch user data
        response = requests.get(clerk_api_url, headers={
                                "Authorization": f"Bearer {CLERK_SECRET_KEY}"})

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(
                f"Failed to fetch user data. Status code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching user data from Clerk: {e}")
        return None

# Example usage
