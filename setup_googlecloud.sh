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

echo "$GOOGLE_VERTEXAI_PROJECTID=\"$(gcloud config get-value project)\""

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
iam service-accounts keys create "${GOOGLE_AI_CREDENTIALS}" \
  --iam-account "${SERVICE_ACCOUNT}@${APP_NAME}.iam.gserviceaccount.com"

echo "$GOOGLE_CREDENTIALS=\"${GOOGLE_AI_CREDENTIALS}\""

# --- Vertex AI Search Setup ---

# Datastore Index
DATASTORE_ID="linkedin-index-$(date +%s)" # Example: Generate a unique ID
gcloud datastore indexes create index.yaml --index-id="$DATASTORE_ID"

echo "$GOOGLE_VERTEX_DATASTOREID=\"${DATASTORE_ID}\""

# Vertex AI Search Schema
cat << EOF > schema.json
{
  "displayName": "LinkedIn Profile Schema",
  "schemaMetadata": {
    "createTime": "2023-12-18T20:12:14.045Z"
  },
  "type": "PROTOCOL_BUFFER",
  "definition": "message Schema {\n  // The person's name.\n  string name = 1;\n\n  // The person's LinkedIn profile URL.\n  string linkedin_profile_url = 2;\n\n  // The person's job title.\n  string job_title = 3;\n\n  // The person's company.\n  string company = 4;\n\n  // The person's location.\n  string location = 5;\n\n  // The person's connections count.\n  int32 connections_count = 6;\n\n  // The person's about section.\n  string about = 7;\n\n  // The person's experience.\n  repeated Experience experience = 8;\n\n  // The person's education.\n  repeated Education education = 9;\n\n  // The person's skills.\n  repeated string skills = 10;\n}\n\nmessage Experience {\n  // The company name.\n  string company = 1;\n\n  // The job title.\n  string job_title = 2;\n\n  // The start date.\n  string start_date = 3;\n\n  // The end date.\n  string end_date = 4;\n\n  // The description.\n  string description = 5;\n}\n\nmessage Education {\n  // The school name.\n  string school = 1;\n\n  // The degree.\n  string degree = 2;\n\n  // The field of study.\n  string field_of_study = 3;\n\n  // The start date.\n  string start_date = 4;\n\n  // The end date.\n  string end_date = 5;\n}\n"
}
EOF

curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @schema.json \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/${APP_NAME}/locations/us-central1/schemas" | jq -r '.name' | cut -d'/' -f6

# Vertex AI Search Index
cat << EOF > index.json
{
  "displayName": "LinkedIn Profile Index",
  "metadataSchemaUri": "gs://google-cloud-aiplatform/schema/search/metadata_1.0.0.yaml",
  "dataSource": {
    "dataStoreId": "$DATASTORE_ID",
    "crawlConfig": {
      "crawlSchedule": {
        "cron": "0 0 * * *" // Crawl daily at midnight UTC
      },
      "requiredSchemaMarker": "CUSTOM_EXTRACTED_REQUIRED_FIELDS",
      "urlWhitelistPatterns": [
        "*.linkedin.com/in/*"
      ]
    }
  }
}
EOF

curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @index.json \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/${APP_NAME}/locations/us-central1/indexes" | jq -r '.name' | cut -d'/' -f6


# --- Azure Bing and Brave Search ---

echo "Remember to manually create and configure Azure Bing Search and Brave Search credentials."
