"""
Deep-learning part of DEEPFACE-ASD.

IMPORTANT - honesty rules built into this file
----------------------------------------------
* If a trained model file is missing, NO prediction is made. The website then
  shows a clearly labelled demonstration card. Nothing is ever random or faked.
* Pre-processing is exactly the pre-processing used in the project code:
      image : RGB, resize to 128 x 128, divide by 255          -> (1, 128, 128, 3)
      audio : 16 kHz, 40 MFCC, transpose, trim/zero-pad to 100 -> (1, 100, 40)
      decision threshold : 0.5   (sigmoid output = probability of ASD class)
* Performance numbers (accuracy, precision, ...) are only shown if you place a
  real evaluation file called  models/metrics.json  (see models/README.txt).
"""
import io
import json
import os
import tempfile

import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
IMAGE_MODEL_FILE = os.path.join(MODEL_DIR, "asd_image_model.keras")
AUDIO_MODEL_FILE = os.path.join(MODEL_DIR, "asd_audio_model.keras")
FUSION_MODEL_FILE = os.path.join(MODEL_DIR, "asd_fusion_model.keras")  # not used in Phase I
METRICS_FILE = os.path.join(MODEL_DIR, "metrics.json")

IMG_SIZE = (128, 128)
SAMPLE_RATE = 16000
N_MFCC = 40
MAX_FRAMES = 100
THRESHOLD = 0.5

# The project code reads images with PIL/RGB in the Flask app (app.py) but with
# OpenCV/BGR in the stand-alone script. Use the same order your model was TRAINED
# with. Change with the environment variable  IMAGE_COLOR_ORDER=BGR  if needed.
IMAGE_COLOR_ORDER = os.environ.get("IMAGE_COLOR_ORDER", "RGB").upper()

POSITIVE = "ASD-related pattern detected"
NEGATIVE = "No ASD-related pattern detected"

_state = {"image_model": None, "audio_model": None, "tf_error": None, "loaded": False}


def load_models():
    """Load the trained models once, when the website starts."""
    if _state["loaded"]:
        return
    _state["loaded"] = True
    if not (os.path.exists(IMAGE_MODEL_FILE) or os.path.exists(AUDIO_MODEL_FILE)):
        return  # nothing to load -> demonstration mode
    try:
        from tensorflow.keras.models import load_model  # imported late: slow import
    except Exception as exc:  # TensorFlow not installed
        _state["tf_error"] = "TensorFlow could not be imported: %s" % exc
        return
    for key, path in (("image_model", IMAGE_MODEL_FILE), ("audio_model", AUDIO_MODEL_FILE)):
        if os.path.exists(path):
            try:
                _state[key] = load_model(path)
            except Exception as exc:
                _state["tf_error"] = "Could not load %s: %s" % (os.path.basename(path), exc)


def status():
    """What the website shows in the 'system status' box."""
    img = _state["image_model"] is not None
    aud = _state["audio_model"] is not None
    return {
        "image_model": img,
        "audio_model": aud,
        "fusion_model": False,
        "demo_mode": not (img or aud),
        "error": _state["tf_error"],
    }


# ----------------------------------------------------------------- pre-processing
def preprocess_image(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data)).convert("RGB").resize(IMG_SIZE)
    arr = np.asarray(img, dtype="float32") / 255.0
    if IMAGE_COLOR_ORDER == "BGR":
        arr = arr[..., ::-1]
    return np.expand_dims(arr, axis=0)


def preprocess_audio(data: bytes, suffix: str = ".wav") -> np.ndarray:
    import librosa  # imported late so the site still starts without it

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        y, sr = librosa.load(path, sr=SAMPLE_RATE)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
        mfcc = mfcc.T[:MAX_FRAMES]                      # (time, 40), trimmed
        if mfcc.shape[0] < MAX_FRAMES:                  # zero padded
            mfcc = np.pad(mfcc, ((0, MAX_FRAMES - mfcc.shape[0]), (0, 0)), mode="constant")
        return np.expand_dims(mfcc.astype("float32"), axis=0)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ----------------------------------------------------------------- prediction
def _decide(prob: float):
    prob = float(prob)
    return (POSITIVE if prob > THRESHOLD else NEGATIVE), prob


def analyse_image(data: bytes):
    """Returns dict(status, label, prob). status: analysed | demo | error."""
    if _state["image_model"] is None:
        return {"status": "demo", "label": None, "prob": None}
    try:
        x = preprocess_image(data)
        prob = _state["image_model"].predict(x, verbose=0)[0][0]
        label, prob = _decide(prob)
        return {"status": "analysed", "label": label, "prob": prob}
    except Exception as exc:
        return {"status": "error", "label": None, "prob": None, "error": str(exc)}


def analyse_audio(data: bytes, suffix: str = ".wav"):
    if _state["audio_model"] is None:
        return {"status": "demo", "label": None, "prob": None}
    try:
        x = preprocess_audio(data, suffix)
        prob = _state["audio_model"].predict(x, verbose=0)[0][0]
        label, prob = _decide(prob)
        return {"status": "analysed", "label": label, "prob": prob}
    except Exception as exc:
        return {"status": "error", "label": None, "prob": None, "error": str(exc)}


def confidence_of_prediction(label, prob):
    """Model output for the *predicted* class (a probability, NOT an accuracy)."""
    if prob is None or label is None:
        return None
    return prob if label == POSITIVE else 1.0 - prob


# ----------------------------------------------------------------- real metrics
def load_metrics():
    """
    Returns {"image": {...} or None, "audio": {...} or None}.
    Values come only from models/metrics.json that YOU create from a real test set.
    """
    out = {"image": None, "audio": None}
    if not os.path.exists(METRICS_FILE):
        return out
    try:
        with open(METRICS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return out
    for key in out:
        m = data.get(key)
        if isinstance(m, dict) and m:
            out[key] = m
    return out
