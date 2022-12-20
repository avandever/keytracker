FROM python:3-slim
WORKDIR .
COPY . .
RUN apt-get update
RUN apt-get install python3-dev default-libmysqlclient-dev gcc  -y
RUN pip install -r requirements.txt
ENTRYPOINT exec gunicorn -b :$PORT -w 2 keytracker.server:app --log-level debug --log-file -
