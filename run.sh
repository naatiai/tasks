#!/bin/bash

echo "Starting grading process at $(date)"
echo "" 

cd /home/gojira/Desktop/oberoi.io/naati/code/tasks/

source venv/bin/activate

# Run grade_tests
echo "Running grade_tests" 
python3 grade_tests.py
echo "Finished grade_tests at $(date)" 

# Run finalise_grading
echo "Running finalise_grading..." 
python3 finalise_grading.py
echo "Finished finalise_grading at $(date)" 

deactivate

echo "Grading process completed at $(date)" 

echo "---------------------------------------------"
echo ""
