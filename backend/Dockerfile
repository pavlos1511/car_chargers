# Χρησιμοποιούμε μια ελαφριά έκδοση της Python
FROM python:3.10-slim

# Θέτουμε τον φάκελο εργασίας μέσα στο container
WORKDIR /app

# Εγκαθιστούμε απαραίτητα εργαλεία συστήματος (για τη βάση δεδομένων)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Αντιγράφουμε τα requirements και τα εγκαθιστούμε
# (Το κάνουμε ΠΡΙΝ τον υπόλοιπο κώδικα για να είναι γρήγορο το rebuild)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Αντιγράφουμε τον υπόλοιπο κώδικα
COPY . .

# Η εντολή που τρέχει τον server (με --reload για να βλέπει τις αλλαγές live)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9876", "--reload"]