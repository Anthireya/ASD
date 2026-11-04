"""PDF screening report (uses ReportLab, pure Python - nothing to configure)."""
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = ("This website is an academic research prototype for ASD-related pattern screening. "
              "It does not diagnose autism spectrum disorder. Results must not be used as a substitute "
              "for assessment by a qualified healthcare professional.")

BLUE = colors.HexColor("#1D6FB8")
LIGHT = colors.HexColor("#EAF4FD")


def _fmt_prob(p):
    return "-" if p is None else "%.1f %%" % (p * 100)


def _modality_rows(title, status, label, prob, conf, metrics_available):
    if status == "analysed":
        res = label
        out = _fmt_prob(conf)
    elif status == "demo":
        res = "DEMONSTRATION ONLY - no trained model connected; file was not analysed"
        out = "-"
    elif status == "not_provided":
        res, out = "No file provided", "-"
    else:
        res, out = "Analysis failed", "-"
    return [title, res, out]


def build_pdf(screening, user, conf_image, conf_audio, metrics):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="DEEPFACE-ASD Screening Report", author="DEEPFACE-ASD")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=BLUE, fontSize=22, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], alignment=TA_CENTER, textColor=colors.grey, fontSize=10)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=BLUE, spaceBefore=14)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, textColor=colors.HexColor("#444444"))

    s = []
    s.append(Paragraph("DEEPFACE-ASD", h1))
    s.append(Paragraph("ASD-related pattern screening report (academic research prototype)", sub))
    s.append(Spacer(1, 14))

    if screening["mode"] == "demo":
        warn = Table([[Paragraph("<b>DEMONSTRATION MODE.</b> No trained model was connected when this screening "
                                 "was run, so the uploaded files were <b>not</b> analysed. This report contains "
                                 "no real prediction.", body)]], colWidths=[17 * cm])
        warn.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4D6")),
                                  ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E0A800")),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        s.append(warn)
        s.append(Spacer(1, 8))

    s.append(Paragraph("Screening details", h2))
    info = [["Report number", "#%d" % screening["id"]],
            ["Date and time", screening["created_at"]],
            ["Account holder", user["full_name"]],
            ["Person screened", screening["subject_name"] or "Not entered"],
            ["Age of person screened", screening["subject_age"] or "Not entered"]]
    t = Table(info, colWidths=[5 * cm, 12 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    s.append(t)

    s.append(Paragraph("Results", h2))
    rows = [["Analysis", "Result", "Model output for predicted class*"],
            _modality_rows("Facial image analysis", screening["image_status"], screening["image_label"],
                           screening["image_prob"], conf_image, False),
            _modality_rows("Voice analysis", screening["audio_status"], screening["audio_label"],
                           screening["audio_prob"], conf_audio, False),
            ["Combined analysis", "Not yet available - no trained fusion model has been implemented", "-"]]
    rows = [[Paragraph(str(c), body) for c in r] for r in rows]
    t = Table(rows, colWidths=[4 * cm, 9 * cm, 4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)
    s.append(Spacer(1, 4))
    s.append(Paragraph("* The value is the probability produced by the neural network for the predicted class. "
                       "It is <b>not</b> an accuracy score and does not mean the result is correct.", small))

    s.append(Paragraph("Validated model performance", h2))
    mrows = [["Model", "Accuracy", "Precision", "Recall", "Specificity", "F1-score"]]
    for key, name in (("image", "Facial image (CNN)"), ("audio", "Voice (LSTM)")):
        m = metrics.get(key)
        if m:
            mrows.append([name] + [("%.1f %%" % (m[k] * 100)) if isinstance(m.get(k), (int, float)) else "Not yet evaluated"
                                   for k in ("accuracy", "precision", "recall", "specificity", "f1")])
        else:
            mrows.append([name] + ["Not yet evaluated"] * 5)
    mrows = [[Paragraph(str(c), small) for c in r] for r in mrows]
    t = Table(mrows, colWidths=[3.8 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 2.8 * cm, 2.6 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey)]))
    s.append(t)
    s.append(Paragraph("Metrics are shown only when they come from a real evaluation on a labelled test dataset.", small))

    s.append(Spacer(1, 18))
    box = Table([[Paragraph("<b>Disclaimer.</b> " + DISCLAIMER, body)]], colWidths=[17 * cm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8FC")),
                             ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    s.append(box)
    doc.build(s)
    buf.seek(0)
    return buf
