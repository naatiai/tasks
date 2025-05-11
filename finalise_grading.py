import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from helpers import (
    get_user_mocks,
    get_mock_answers_by_user_mock_id,
    update_user_mock,
    fetch_user_from_clerk,
    send_test_result_email,
    get_mock_question_count,
    send_test_result_email_sendgrid
)

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
    total_score = sum(
        answer.score for answer in mock_answers if answer.score is not None)

    # Get total number of mock questions instead of using answers
    num_questions = get_mock_question_count(session, user_mock.mock_id)

    # Avoid division by zero
    if num_questions > 0:
        percentage = round((total_score / (5 * num_questions)) * 100)
        print(
            f"[+] User Mock ID: {user_mock.id}, Total Score: {total_score}, Percentage: {percentage}")
    else:
        print(f"[-] User Mock ID: {user_mock.id}, No questions found.")
        percentage = 0  # Default to 0 if no questions exist

    passed = percentage > 50  # Determine pass/fail based on 50% threshold
    print("[+] Passed:", passed)

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

            link = f"https://app.naatininja.com/mock-test/{user_mock.mock_id}"
            recipient_email = fetch_user_from_clerk(user_mock.user_id)
            to_email = recipient_email['email_addresses'][0]['email_address']
            # send_test_result_email(to_email, link, passed=passed) # Credits reset on 21 May 2025
            send_test_result_email_sendgrid(to_email, link, passed=passed)
        else:
            print("[-] Failed to update UserMocks.")
    except Exception as ex:
        print(f"[-] Error updating UserMock: {ex}")
