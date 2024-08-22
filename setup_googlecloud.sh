#!/bin/bash

# Help set-up the whole API keys

# You can modify this
APP_NAME="thedig"
SERVICE_ACCOUNT="${APP_NAME}-ai" # Using a single service account for Vision and Vertex

# Fetch credential key path from .env
eval "$(grep GOOGLE_AI_CREDENTIALS .env)"

# Create project and switch to it
gcloud projects create $APP_NAME
gcloud config set project $APP_NAME

# --- Google Cloud Platform ---

# Enable Vision API
gcloud services enable vision.googleapis.com

# Enable Custom Search
gcloud services enable customsearch.googleapis.com

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable Datastore API
gcloud services enable datastore.googleapis.com

# Create service account for Vision and Vertex AI
gcloud iam service-accounts create $SERVICE_ACCOUNT \
  --display-name "${APP_NAME} AI"

# Create the key as JSON file 
gcloud iam service-accounts keys create "${GOOGLE_AI_CREDENTIALS}" \
  --iam-account "${SERVICE_ACCOUNT}@${APP_NAME}.iam.gserviceaccount.com"

echo "-------------------------"
echo "Remember to manually create and configure Azure Bing Search and Brave Search credentials."
echo "Configure only your Google Custom Search Engine, then copy/paste the cx value to your .env file"
echo "-------------------------"
echo "Copy/paste following lines to your .env"
echo "\$GOOGLE_CREDENTIALS=\"${GOOGLE_AI_CREDENTIALS}\""
echo "\$GOOGLE_VERTEX_DATASTORE=\"${DATASTORE_ID}\""
echo "\$GOOGLE_VERTEXAI_PROJECTID=\"$(gcloud config get-value project)\""
