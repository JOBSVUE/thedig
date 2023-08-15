#!/bin/bash

# Help set-up the whole API keys

# you could modify this
APP_NAME="gemway"
SERVICE_ACCOUNT="${APP_NAME}-vision"

# fetch credential key path from .env
eval "$(grep GOOGLE_VISION_CREDENTIALS .env)"

# create project
gcloud projects create $APP_NAME

# enable Vision API
gcloud services enable vision.googleapis.com

# enable Custom Search
gcloud services enable customsearch.googleapis.com

# create service account for vision
gcloud iam service-accounts create $SERVICE_ACCOUNT \
  --display-name "${APP_NAME} vision"

# create the key as JSON file
gcloud iam service-accounts keys create "${GOOGLE_VISION_CREDENTIALS}" \
  --iam-account ${SERVICE_ACCOUNT}@${APP_NAME}.iam.gserviceaccount.com
