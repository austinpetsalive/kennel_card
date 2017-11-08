FROM ubuntu:17.10

RUN apt-get update
RUN apt-get install -y python-pip python3-pip python3-dev git
RUN pip3 install --upgrade pip
RUN pip3 install virtualenv
RUN virtualenv /kennel_card
RUN mkdir /app
COPY app /app
RUN /kennel_card/bin/pip3 install -r /app/requirements.txt

EXPOSE 80
EXPOSE 443

WORKDIR /app
CMD /kennel_card/bin/python app.py
