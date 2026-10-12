# Der Supervisor uebergibt BUILD_FROM nur, wenn ein build.yaml ein Basisimage nennt. Ohne Standardwert bricht der Bau
# mit "base name ($BUILD_FROM) should not be blank" ab (so in Supervisor 2026.x erlebt) - deshalb hier festgelegt.
ARG BUILD_FROM=python:3.12-slim
FROM $BUILD_FROM

# Fertige Wheels (amd64/aarch64): keine Kompilierung. headless = ohne GUI-Bibliotheken.
RUN pip install --no-cache-dir "numpy>=1.26,<3" "opencv-python-headless>=4.9,<5" "paho-mqtt>=1.6,<3"

COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD ["/run.sh"]
