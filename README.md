# DEEPFACE-ASD – ASD Screening Website (academic research prototype)

> This website is an academic research prototype for ASD-related pattern screening. It does not diagnose autism spectrum disorder. Results must not be used as a substitute for assessment by a qualified healthcare professional.

A Flask + SQLite website where a user registers, logs in, uploads a face photo and/or a voice recording (or records with the microphone), clicks **ANALYSE ASD**, sees results, and downloads a PDF report.

## 1. Install Python (once)
Install Python 3.10 or 3.11 from https://www.python.org/downloads/ (on Windows tick **"Add Python to PATH"**).
TensorFlow works best with these versions.

## 2. Start the website (one command)
- **Windows:** double-click `run.bat`
- **Mac / Linux:** open a terminal in this folder and run `bash run.sh`

The first run creates a virtual environment and installs everything in `requirements.txt` (a few minutes; TensorFlow is large).
Later runs start in seconds.

Manual alternative:
```
python -m venv venv
venv\Scripts\activate        (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```

## 3. Open the site
Go to **http://127.0.0.1:5000** in your browser. Register, log in, and try **New screening**.

## 4. Connect your trained models
Copy your **trained** files into the `models/` folder with these exact names:
```
models/asd_image_model.keras
models/asd_audio_model.keras
```
Restart the website. The yellow "Demonstration mode" banner disappears.

Important:
- Until both files exist, the site runs in **demonstration mode**: it analyses nothing, makes no predictions, and clearly says so. Nothing is faked.
- The files must be **trained** models. Code that only builds and saves a network produces an untrained model, whose output is meaningless.
- Image preprocessing: RGB, resized to 128×128, divided by 255. If you trained with OpenCV (BGR colour order), start with `IMAGE_COLOR_ORDER=BGR` (Windows: `set IMAGE_COLOR_ORDER=BGR`). The preprocessing must match training.
- Audio preprocessing: 16 kHz, 40 MFCC, 100 frames (padded/trimmed), input shape (1, 100, 40).
- The percentage shown is the model's output probability for the predicted class ("confidence"), not accuracy.

## 5. Performance numbers (optional, real only)
The site shows accuracy, precision, recall, specificity, F1 and the confusion matrix **only** if you evaluate on real labelled test files the model never saw in training:
```
test_data/image/autistic/        test_data/image/non_autistic/
test_data/audio/autistic/        test_data/audio/non_autistic/
```
Then run `python evaluate_models.py`. It writes `models/metrics.json`. Until then the site shows **"Not yet evaluated"**.

## 6. Combined (face + voice) analysis
Shown as **"Not yet available"**, because it needs a genuine trained fusion model. The two results are shown separately and are never merged.

## Pages
Home · Register · Login (email or mobile, forgot password) · Dashboard · Screening · Results · History (view, PDF, delete)

## Files
```
app.py            routes and server
db.py             SQLite tables (users, screenings)
ml.py             model loading and preprocessing
reports.py        PDF report
evaluate_models.py real metrics
templates/ static/ models/ requirements.txt run.bat run.sh
```

## Notes and limitations
- Uploaded files are analysed in memory and are not stored.
- Forgot password: there is no email server, so a reset requires the registered email **and** mobile number together.
- Microphone recording needs `http://127.0.0.1` or HTTPS; otherwise upload a file.
- Set `PORT` to change the port. Data is in `instance/deepface_asd.sqlite3`.
- Built for a student project; before any real-world use it would need clinical validation, a larger dataset and proper security hardening.
