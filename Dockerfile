# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
ENV PORT 8000

WORKDIR $APP_HOME
COPY . ./

# setting up the environment and executing it on the server
# RUN pip install pipenv
# RUN pipenv install --deploy --system

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE $PORT

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 --worker-class uvicorn.workers.UvicornWorker main:app