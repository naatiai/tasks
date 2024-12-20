import re
import whisper
from supabase import create_client
# from supabase.storage import StorageException
from sqlalchemy.exc import NoResultFound
from ollama import Client
from openai import OpenAI
# import whisper
import torch
from langcodes import Language

from models.schema import MockAnswers, MockQuestions, UserMocks
from sqlalchemy.orm import Session
from sqlalchemy import and_
# from sqlalchemy.orm import joinedload

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


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
    Fetch all UserMocks with total_score as NULL and attempts as 0.

    Args:
        session (Session): SQLAlchemy database session object.

    Returns:
        List[UserMocks]: A list of UserMocks objects matching the criteria.
    """
    try:
        results = session.query(UserMocks).filter(
            and_(
                UserMocks.total_score.is_(None),  # total_score is NULL
                UserMocks.attempts == 0          # attempts is 0
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
    including the answer_language from the mock_questions table.

    Args:
        session (Session): SQLAlchemy database session object.

    Returns:
        List[tuple]: A list of tuples, each containing a MockAnswers object 
                     and the corresponding answer_language from mock_questions.
    """

    # results = session.query(MockAnswers).filter(
    #     and_(
    #         MockAnswers.transcript == None,
    #         MockAnswers.score == None
    #     )
    # ).all()

    results = session.query(MockAnswers, MockQuestions).join(
        MockQuestions, MockAnswers.mock_question_id == MockQuestions.id
    ).filter(
        and_(
            MockAnswers.transcript == None,
            MockAnswers.score == None
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

    prompt = f"""
    You need to evaluate a user's translation test. You will be provided with two texts in {language}: a reference answer and a student's answer. 

    Reference:
    {reference}

    Answer:
    {answer}

    Your task is to:
    1. Compare the two texts based on **accuracy** (matching details and content) and **correctness** (faithful interpretation of the reference).
    2. Ignore differences in punctuation, spaces, or minor grammatical errors unless they affect the correctness or interpretation of the text.
    3. Focus specifically on how well the student's response matches the intended meaning and correctness of the reference text.

    Provide a score out of 5, where:
    - 5 = Perfect match, fully accurate and correct interpretation.
    - 4 = Very minor errors that don't affect overall correctness.
    - 3 = Noticeable errors but the general meaning is retained.
    - 2 = Significant errors that distort meaning but show some understanding.
    - 1 = Poor understanding or largely incorrect.
    - 0 = No resemblance.

    Return only the numeric score (0-5). Do not include any explanations or other text in your response.
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
    lang = Language.get(language[:3]).is_valid()
    print(f"-> Language: {language[:3]} {lang}")
    if lang is True:
        iso_lang = Language.get(language[:3]).to_tag()
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
