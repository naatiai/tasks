import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from helpers import get_user_mocks, get_mock_answers_by_user_mock_id, update_user_mock

# Load environment variables from .env file
load_dotenv()

# Validate Supabase and Database URLs
DATABASE_URL = os.getenv("POSTGRES_URL")

# Create a database session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Fetch the user mock answers with null score and passed
user_mocks = get_user_mocks(session)

# Process each user mock
for user_mock in user_mocks:
    mock_answers = get_mock_answers_by_user_mock_id(session, user_mock.id)

    # Calculate the total score for all answers in this user mock
    total_score = sum(
        answer.score for answer in mock_answers if answer.score is not None)
    num_answers = len(mock_answers)

    # Avoid division by zero
    if num_answers > 0:
        percentage = round((total_score / (5 * num_answers)) * 100)
        print(
            f"[+] User Mock ID: {user_mock.id}, Total Score: {total_score}, Percentage: {percentage}")
    else:
        print(f"[-] User Mock ID: {user_mock.id}, No answers available.")

    if percentage > 50:
        passed = True
    else:
        passed = False

    print("[+] Passed: ", passed)

    # Update UserMocks
    try:
        result = update_user_mock(
            session=session,
            user_mock_id=user_mock.id,
            user_id=user_mock.user_id,
            attempts_increment=1,
            total_score=percentage,
            passed=passed
        )

        if result:
            print("[+] UserMocks updated successfully.")
        else:
            print("[-] Failed to update UserMocks.")
    except Exception as ex:
        print(f"[-] Error updaring userMock: {ex}")
