# Tools and Utils CloudFunctions
    This is where all the standalone functional tools and utils, written as Google CloudFunctions, reside. These are meant to be self-contained and independent functions.

## How-to add a standalone tool/util cloud function
- Create a directory and name it same as the CloudFunction name
- Write **Google Cloud Function** - see **[Google How-to Guide on Writing Cloud Functions](https://cloud.google.com/functions/docs/how-to)**
- Modify the `deploy.sh` (the example is for a python CloudFunction)
- Update the **GitHub Actions YML** file `<git_hub_repo>/.github/workflows/tools.yml`

Assumes *<git_hub_repo>* is the root directory.

Example Directory Layout 
(for a CloudFunction written in Python. This could be anything)
```
tools
└── functions
    └── postSchoolCourseProgressToSlack    <--- camelCase function name
        ├── school_lessons.sql             <--- meaningful name for a sql query
        ├── config.py                      <--- config
        ├── deploy.sh                      <--- custom deploy and schedule script
        ├── main.py                        <--- main cloudfunction app
        └── requirements.txt               <--- python requirements.txt
```



### Create Directory

    > mkdir <camelCaseCloudFunctionName>
    > cd <camelCaseCloudFunctionName>

### Write Google Cloud Function
[Google How-to Guide on Writing Cloud Functions](https://cloud.google.com/functions/docs/how-to)

### Create a `deploy.sh` shell script
- All environment variables are set in the `<git_hub_repo>/.github/workflows/tools.yml`
- No need to change the references to the environment variables, and if you need to add new options, follow the existing convention of declaring environment variables in the github actions YML file.
- `--runtime` is the only option that needs to match the language of the function. See **[Cloud Functions Runtimes](https://cloud.google.com/functions/docs/concepts/exec)**
```
#!/usr/bin/env bash

set -e
set -o pipefail

echo "Deploying"
gcloud functions deploy "${MY_FUNCTION}" \ 
--entry-point main \
--project "${PROJECT_ID}" \
--runtime python39 \                          <--- match the runtime of the function
--trigger-resource "${MY_FUNCTION}" \
--trigger-event google.pubsub.topic.publish \
--timeout 540s
```
- If a Cloud Function is a triggered function then modify just the `--message-body`. Everything else is a variable reference set in the **GitHub Actions YML** file `<git_hub_repo>/.github/workflows/tools.yml`
```
echo "Scheduling"
job_name=$(gcloud scheduler jobs list --project "${PROJECT_ID}" --uri | grep "${PUBSUB_JOB_NAME}" | xargs basename)
if [ "$job_name" == "$PUBSUB_JOB_NAME" ]
then
    #trigger already exists
    echo "Updating a Job"
    (echo "gcloud scheduler jobs update pubsub "${PUBSUB_JOB_NAME}" \
    --schedule="${TRIGGER_SCHEDULE}" \
    --project="${PROJECT_ID}" \
    --topic="${MY_FUNCTION}" \
    --message-body='"<some message text>"'")
    (gcloud scheduler jobs update pubsub "${PUBSUB_JOB_NAME}" \
    --schedule="${TRIGGER_SCHEDULE}" \
    --project="${PROJECT_ID}" \
    --topic="${MY_FUNCTION}" \
    --message-body='"<some message text>"')
else
    echo "Creating a Job"
    (echo "gcloud scheduler jobs create pubsub "${PUBSUB_JOB_NAME}" \
    --schedule="${TRIGGER_SCHEDULE}" \
    --project="${PROJECT_ID}" \
    --topic="${MY_FUNCTION}" \
    --message-body="<some message text>"")
    (gcloud scheduler jobs create pubsub "${PUBSUB_JOB_NAME}" \
    --schedule="${TRIGGER_SCHEDULE}" \
    --project="${PROJECT_ID}" \
    --topic="${MY_FUNCTION}" \
    --message-body='"<some message text>"')
fi
```
### Update the **GitHub Actions YML** file `<git_hub_repo>/.github/workflows/tools.yml`
- The `YML` file uses `GitHub Actions Job` context to deploy to designated environment
- For each `job` in the `YML` file, right after the following line `FUNCTIONS_BASE_URL: https://us-central1-${{ env.PROJECT_ID }}.cloudfunctions.net` add the following section enclosed between `>>>>` and `<<<<`:

**Example**
```
  deployprodcanada:                                    
    if: contains(github.ref , '/production-canada-')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set env to Production CANADA
        uses: google-github-actions/setup-gcloud@master
        with:
          service_account_key: ${{ secrets.PROD_CAN_PRIV_KEY }}
          export_default_credentials: true
```
`>>>>>>>>>>>>>>>>>>>>>  START  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>`
```
      - name: Deploy the function on Production CANADA
        run: |
          echo "PROJECT_ID=prod-canada" >> $GITHUB_ENV
          chmod +x deploy.sh
          ./deploy.sh
        env:
          PROJECT_ID: prod-canada
          PROJECT_PATH: admin
          MY_FUNCTION: postSchoolCourseProgressToSlack              <--- Change this
          PUBSUB_JOB_NAME: post_school_course_progress_to_slack_job
          TRIGGER_SCHEDULE: ${{ '0 12 1-31 1-12 MON-FRI' }}         <--- Cron Frequency for a triggered Cloud Function
        working-directory: ./tools/functions/${{ env.MY_FUNCTION }}
        shell: bash
      - name: Post deploy items
        # uses: curlimages/curl
        run: |
          sleep 10 && curl ${FUNCTIONS_BASE_URL}/postDeployHooks
        env:
          FUNCTIONS_BASE_URL: https://us-central1-${{ env.PROJECT_ID }}.cloudfunctions.net
```
`<<<<<<<<<<<<<<<<<<<<<<  END  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<`
