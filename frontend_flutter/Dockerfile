# frontend_flutter/Dockerfile

FROM debian:bookworm-slim

# 1. Εγκατάσταση απαραίτητων εργαλείων Linux
RUN apt-get update && apt-get install -y \
    curl git wget unzip libgconf-2-4 gdb libstdc++6 libglu1-mesa fonts-droid-fallback python3 \
    && apt-get clean

# 2. Λήψη του Flutter SDK (Stable version)
RUN git clone https://github.com/flutter/flutter.git /usr/local/flutter && \
    cd /usr/local/flutter && \
    git checkout stable

# 3. Ρύθμιση PATH για να βλέπουμε την εντολή 'flutter'
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# 4. Ενεργοποίηση Web support
RUN flutter config --enable-web

# 5. Ορίζουμε φάκελο εργασίας
WORKDIR /app

# 6. (Προσωρινό) Για να μην κρασάρει αν δεν υπάρχουν αρχεία, 
#    αφήνουμε την εντολή εκκίνησης δυναμική ή απλή.
CMD ["flutter", "doctor"]