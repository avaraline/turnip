FROM python:alpine

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY turnip.py /usr/local/bin/turnip

USER nobody

EXPOSE 19555/udp

CMD ["turnip"]
