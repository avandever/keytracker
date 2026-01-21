FROM python:3.12-slim
WORKDIR /tracker
RUN apt-get update
RUN apt-get upgrade
RUN apt-get install -y git pkg-config build-essential libmariadb-dev
RUN git clone "https://github.com/avandever/keytracker.git" .
RUN pip install -r requirements.txt
RUN pip install .
EXPOSE 3001
CMD ["flask", "--app", "keytracker.server", "run"]
