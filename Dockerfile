FROM apify/actor-python:3.13

COPY requirements.txt /actor/requirements.txt
RUN pip install --no-cache-dir -r /actor/requirements.txt

COPY . /actor
WORKDIR /actor

CMD ["python3", "-m", "src.main"]
