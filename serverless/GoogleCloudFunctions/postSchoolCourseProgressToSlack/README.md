# Summary 
Meant for School District Management, this function publishes course progress, such as current course, next course, and number of days left to finish, to Slack Channel.

## Psuedo flow of the function

This tool does the following:
- runs Google BigQuery against pre-exported data from Firestore
- filters courses per school
- for quick lookups and structured queries, stores filtered list in in-memory SQLite3 database
- collates data, and posts it to a Slack Channel

## Sample Output
```
[Environment: Production]
    [First Middle School]
        Current course  : <course name>
        Next Course     : <course name>
        Num courses left: 11
        Num days left   : 7
    [Second Middle School]
        Current course  : <course name>
        Next Course     : <course name>
        Num courses left: 9
        Num days left   : 11
```
