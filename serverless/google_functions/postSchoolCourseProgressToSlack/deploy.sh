#!/usr/bin/env bash

set -eu
#deploy ONLY to Production by default.
#for other envs, you'll have to manually update
#the line below
if [[ "${PROJECT_ID}" == "<gcp project name>" ]]
then
    echo "Deploying to ${PROJECT_ID}"
    (gcloud functions deploy "${MY_FUNCTION}" \
    --entry-point main \
    --project "${PROJECT_ID}" \
    --runtime python39 \
    --set-env-vars=GCP_PROJECT="${PROJECT_ID}" \
    --trigger-resource "${MY_FUNCTION}" \
    --trigger-event google.pubsub.topic.publish \
    --timeout 540s)

    echo "Scheduling ${MY_FUNCTION} function on ${PROJECT_ID}"
    #instead of set -o pipefail, which exists
    job_name=$(gcloud scheduler jobs list --project "${PROJECT_ID}" --uri \
                | grep "${PUBSUB_JOB_NAME}" \
                | xargs basename ; echo "${PIPESTATUS[@]}")

    if [[ "$job_name" =~ "$PUBSUB_JOB_NAME" ]]
    then
        #trigger already exists
        echo "Updating PUBSUB $PUBSUB_JOB_NAME Job on ${PROJECT_ID}"
        (gcloud scheduler jobs update pubsub "${PUBSUB_JOB_NAME}" \
        --schedule="${TRIGGER_SCHEDULE}" \
        --project="${PROJECT_ID}" \
        --topic="${MY_FUNCTION}" \
        --message-body='"<some message text>"')
    else
        echo "Creating PUBSUB $PUBSUB_JOB_NAME Job ${PROJECT_ID}"
        (gcloud scheduler jobs create pubsub "${PUBSUB_JOB_NAME}" \
        --schedule="${TRIGGER_SCHEDULE}" \
        --project="${PROJECT_ID}" \
        --topic="${MY_FUNCTION}" \
        --message-body='"<some message text>"')
    fi
else
    echo "This function is automatically deployed ONLY on Production"
fi
