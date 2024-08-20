FROM python:3.12-slim

# below is only required for PROD
# RUN apt-get update \
#    && apt-get upgrade -y \
#    && apt-get install -y --no-install-recommends curl git build-essential \
#    && apt-get autoremove -y \
#    && apt-get clean \
#    && rm -rf /var/apt/lists/* \
#    && rm -rf /var/cache/apt/*

# Create a non-root user
RUN useradd -m -s /bin/bash appuser

# Switch to non-root user
USER appuser

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONDONTWRITEBYTECODE=True \
    PYTHONUNBUFFERED=True \
    PYTHONIOENCODING=utf-8

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME

COPY ./requirements.txt $APP_HOME/requirements.txt
# Install dependencies.
RUN pip install --no-cache-dir --upgrade -r $APP_HOME/requirements.txt

#COPY tests/ tests/
COPY thedig/ thedig/
COPY .env ./

COPY . $APP_HOME/

EXPOSE 8080

# Add HEALTHCHECK instruction
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/docs || exit 1


# Run the web service on container startup. Here we use uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--proxy-headers", "--use-colors", "--port", "8080"]
