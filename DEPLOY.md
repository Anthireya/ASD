# Put DEEPFACE-ASD online (Render, free, no installs)

1. Create a free account at https://github.com and a new repository named deepface-asd.
   On the repo page: "Add file" > "Upload files", drag in everything inside this folder, click Commit.
2. Create a free account at https://render.com (sign in with GitHub).
3. Click New > Blueprint, choose your deepface-asd repository, click Apply.
   Render reads render.yaml, builds the site and creates a private SECRET_KEY for you.
4. After 3-5 minutes Render shows your link: https://deepface-asd-XXXX.onrender.com

Updating later: on GitHub open the file, click the pencil icon (or upload a new copy), Commit.
Render redeploys automatically.

Free-tier notes: the site sleeps after ~15 min idle (first visit then takes ~50 s), and the
free plan has NO persistent disk, so accounts/history reset on each redeploy or restart.
For permanent data use Render's paid plan with a disk mounted at /var/data and set DATA_DIR=/var/data.

Real model analysis: put asd_image_model.keras and asd_audio_model.keras in models/ and install
requirements-ml.txt. TensorFlow needs about 2 GB RAM, so it will not run on the free tier.
Until then the site stays in clearly labelled demonstration mode.
