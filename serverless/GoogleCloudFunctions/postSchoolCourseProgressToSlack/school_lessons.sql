WITH student_list AS (
  SELECT document_id AS student_id, 
  JSON_EXTRACT_SCALAR(data, '$.fullName') AS student_name, 
  JSON_EXTRACT_SCALAR(data, '$.orgId') AS school_id, 
  JSON_EXTRACT_SCALAR(data, '$schoolName') AS school_name,
  JSON_EXTRACT_SCALAR(data, '$.jobTitle') AS job_title,
  JSON_EXTRACT_SCALAR(data, '$.location') AS location,
  JSON_EXTRACT_SCALAR(data, '$.supervisor') AS.supervisor,
  TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.lastSignedIn._seconds') AS INT64)) AS last_signed_in,
    CASE
      WHEN TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.lastSignedIn._seconds') AS INT64)) IS NULL THEN 'Not Active'
      WHEN DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.deactivatedAt._seconds') AS INT64))) < DATETIME(CURRENT_DATE()) THEN 'Deactivated'
      ELSE 'Active'
    END AS student_status
  FROM `%%PROJECT-ID%%.firestore_export.students_raw_latest`
),
student_history AS (
  SELECT REGEXP_EXTRACT(document_name,r"/.*/(.*)/.*/") AS student_id,
  CASE 
    WHEN JSON_EXTRACT_SCALAR(data, '$.someField') LIKE '%unregistered%' THEN concat(JSON_EXTRACT_SCALAR(data, '$.label'),' UnRegistered')
    ELSE JSON_EXTRACT_SCALAR(data, '$.label')
  END AS course,
  JSON_EXTRACT_SCALAR(data, '$.someField') AS.someField,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.availableAt._seconds') AS INT64)),"America/Los_Angeles") AS time_available,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.startedAt._seconds') AS INT64)),"America/Los_Angeles") AS time_started,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.completedAt._seconds') AS INT64)),"America/Los_Angeles") AS time_completed,
  ROUND(CAST(JSON_EXTRACT_SCALAR(data, '$.collectedData.context.QUIZ_RESULTS.correct') AS INT64)/CAST(JSON_EXTRACT_SCALAR(data, '$.collectedData.context.QUIZ_RESULTS.total') AS INT64),2) AS score
  FROM `%%PROJECT-ID%%.firestore_export.student_history_raw_latest`
  WHERE JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%Feedback%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%classCheckIn%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%studentTeacherAgreement%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%onboarding%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%top%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%high%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%high%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%kudos%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%follow%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '.supervisor%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%passcode%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%Covid%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%never%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE 'demo%'
),
student_current_actions AS (
  SELECT REGEXP_EXTRACT(document_name,r"/.*/(.*)/.*/") AS student_id,
  CASE 
    WHEN JSON_EXTRACT_SCALAR(data, '$.someField') LIKE '%unregistered%' THEN concat(JSON_EXTRACT_SCALAR(data, '$.label'),' UnRegistered')
    ELSE JSON_EXTRACT_SCALAR(data, '$.label')
  END AS course,
  JSON_EXTRACT_SCALAR(data, '$.someField') AS.someField,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.availableAt._seconds') AS INT64)),"America/Los_Angeles") AS time_available,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.startedAt._seconds') AS INT64)),"America/Los_Angeles") AS time_started,
  DATETIME(TIMESTAMP_SECONDS(CAST(JSON_VALUE(data, '$.completedAt._seconds') AS INT64)),"America/Los_Angeles") AS time_completed,
  ROUND(CAST(JSON_EXTRACT_SCALAR(data, '$.collectedData.context.QUIZ_RESULTS.correct') AS INT64)/CAST(JSON_EXTRACT_SCALAR(data, '$.collectedData.context.QUIZ_RESULTS.total') AS INT64),2) AS score
  FROM `%%PROJECT-ID%%.firestore_export.student_actions_raw_latest`
  WHERE JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%Feedback%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%classCheckIn%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%studentTeacherAgreement%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%onboarding%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%top%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%high%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%high%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%kudos%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%follow%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '.supervisor%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%passcode%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%Covid%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%never%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE '%reports%'
  AND JSON_EXTRACT_SCALAR(data, '$.someField') NOT LIKE 'demo%'
),
active_students_by_school AS (
  SELECT school_id, school_name, COUNTIF(student_status = 'Active') AS active_students
  FROM student_list
  GROUP BY school_id, school_name
),
courses AS (
  SELECT 
  CASE
      WHEN document_id LIKE '%unregistered%' THEN concat(JSON_EXTRACT_SCALAR(data, '$.states.main.mobileAppFlow.label'),' UnRegistered')
      ELSE JSON_EXTRACT_SCALAR(data, '$.states.main.mobileAppFlow.label')
  END AS course, COUNT(*) AS number_of_lessons,
  FROM `%%PROJECT-ID%%.firestore_export.global_someField_raw_latest`
  WHERE document_id NOT LIKE '%Feedback%'
  AND document_id NOT LIKE '%classCheckIn%'
  AND document_id NOT LIKE '%studentTeacherAgreement%'
  AND document_id NOT LIKE '%onboarding%'
  AND document_id NOT LIKE '%top%'
  AND document_id NOT LIKE '%high%'
  AND document_id NOT LIKE '%kudos%'
  AND document_id NOT LIKE '%follow%'
  AND document_id NOT LIKE '.supervisor%'
  AND document_id NOT LIKE '%passcode%'
  AND document_id NOT LIKE '%Covid%'
  AND document_id NOT LIKE '%never%'
  AND document_id NOT LIKE '%reports%'
  AND document_id NOT LIKE 'demo%'
  GROUP BY course
  ORDER BY course
),
completed_courses_by_student AS (
  SELECT school_id, school_name, student_id, r.course, completed_lessons, number_of_lessons,
  CASE 
    WHEN completed_lessons/number_of_lessons >= 1 THEN 'complete'
    ELSE 'current_course'
  END AS course_status
  FROM (
    SELECT school_id, school_name, h.student_id, course, 
    #New course content was introduced on November 16, 2020 at 11 am PST (newLesson was added)
    CASE 
      WHEN course = "Some Course Name" THEN SUM(IF(time_completed<DATETIME(TIMESTAMP "2020-11-16 18:00:00+00", "America/Los_Angeles"),2,1))
      ELSE COUNT(DISTINCT CONCAT(school_id.someField))
    END AS completed_lessons,
    ROUND(AVG(score),2) AS avg_score
    FROM student_history AS h
    LEFT JOIN student_list AS l
    ON h.student_id = l.student_id
    WHERE student_status = 'Active'
    GROUP BY school_id, school_name, h.student_id, course
  ) AS r
  LEFT JOIN courses AS c 
  ON r.course = c.course
  ORDER BY school_name, student_id
),
current_courses_by_student AS (
    SELECT school_id, school_name, course, concat(school_id,course) AS id, COUNT(DISTINCT(l.student_id)) AS no_students_on_current_course
    FROM student_current_actions AS a
    LEFT JOIN student_list AS l
    ON a.student_id = l.student_id
    WHERE student_status = 'Active'
    GROUP BY school_id, school_name, course
)

SELECT c.school_name, course 
FROM (
  SELECT IFNULL(c.school_id,d.school_id) AS school_id, IFNULL(c.school_name,d.school_name) AS school_name, IFNULL(c.course,d.course) AS course, no_students_who_completed_course, no_students_on_current_course,
  FROM (
    SELECT school_id, school_name, course, concat(school_id,course) AS id,
    COUNTIF(course_status = 'complete') AS no_students_who_completed_course,
    FROM completed_courses_by_student 
    GROUP BY school_id, school_name, course
  ) AS c
  FULL OUTER JOIN current_courses_by_student AS d 
  ON c.id = d.id
) AS c
LEFT JOIN active_students_by_school AS t
ON c.school_id = t.school_id 
ORDER BY school_name, no_students_who_completed_course DESC, no_students_on_current_course DESC
