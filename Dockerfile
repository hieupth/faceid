### Pip stage ###

FROM python:3.10-slim as compiler
ENV PYTHONUNBUFFERED 1

ADD . .

RUN python -m venv /venv

ENV PATH="/venv/bin:$PATH"

RUN pip install -r requirements.txt

FROM python:3.10-slim as runner

RUN apt update && apt install -y libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx

COPY --from=compiler /venv /venv
COPY faceserve /faceserve
COPY main.py /main.py


ENV PATH="/venv/bin:$PATH"

CMD fastapi run main.py --port 6999