"""
Calculate REAL performance numbers for your trained models and save them to models/metrics.json.

Put your labelled TEST files (files the model never saw during training) in folders like this:

    test_data/
        image/autistic/        *.jpg *.png
        image/non_autistic/    *.jpg *.png
        audio/autistic/        *.wav *.mp3
        audio/non_autistic/    *.wav *.mp3

Run:   python evaluate_models.py
"""
import json
import os
import sys

import ml

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


def files(folder, exts):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith(exts)]


def metrics(tp, tn, fp, fn):
    div = lambda a, b: (a / b) if b else None
    prec, rec = div(tp, tp + fp), div(tp, tp + fn)
    f1 = div(2 * prec * rec, prec + rec) if prec is not None and rec is not None else None
    return {"accuracy": div(tp + tn, tp + tn + fp + fn), "precision": prec, "recall": rec,
            "specificity": div(tn, tn + fp), "f1": f1, "confusion_matrix": [[tn, fp], [fn, tp]],
            "test_samples": tp + tn + fp + fn}


def evaluate(kind):
    exts = (".jpg", ".jpeg", ".png") if kind == "image" else (".wav", ".mp3")
    fn_predict = ml.analyse_image if kind == "image" else ml.analyse_audio
    tp = tn = fp = fn = 0
    for label, positive in (("autistic", True), ("non_autistic", False)):
        for path in files(os.path.join(ROOT, kind, label), exts):
            with open(path, "rb") as fh:
                data = fh.read()
            res = fn_predict(data) if kind == "image" else fn_predict(data, os.path.splitext(path)[1])
            if res["status"] != "analysed":
                print("  skipped (%s): %s" % (res.get("error", res["status"]), path))
                continue
            predicted_pos = res["label"] == ml.POSITIVE
            if positive and predicted_pos: tp += 1
            elif positive: fn += 1
            elif predicted_pos: fp += 1
            else: tn += 1
    if tp + tn + fp + fn == 0:
        return None
    return metrics(tp, tn, fp, fn)


def main():
    ml.load_models()
    st = ml.status()
    out = {}
    for kind, ready in (("image", st["image_model"]), ("audio", st["audio_model"])):
        if not ready:
            print("%s model not loaded - skipped." % kind)
            continue
        print("Evaluating %s model ..." % kind)
        m = evaluate(kind)
        if m is None:
            print("  no test files found in test_data/%s/" % kind)
        else:
            out[kind] = m
            print("  %d samples, accuracy %.1f %%" % (m["test_samples"], m["accuracy"] * 100))
    if not out:
        print("Nothing evaluated, metrics.json not written.")
        sys.exit(1)
    with open(ml.METRICS_FILE, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("Saved", ml.METRICS_FILE)


if __name__ == "__main__":
    main()
