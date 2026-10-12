ARG BUILD_FROM
FROM $BUILD_FROM

# OpenCV und NumPy aus den Alpine-Paketen (keine Kompilierung noetig)
RUN apk add --no-cache python3 py3-numpy py3-opencv py3-pillow py3-paho-mqtt py3-flask

COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD ["/run.sh"]
