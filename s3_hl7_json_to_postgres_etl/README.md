## Script that processes HL7 data from JSON files stored in S3 buckets and stores the transformed/processed data in PostgreSQL schema.

## Requires:
        1. Apache Spark Standalone or Cluster (3.4.1 or later)
            I set up a Standalone Spark Master with 5 worker nodes
            https://spark.apache.org/downloads.html
        2. Have following JARS downloaded - in my case for Spark v3.4.1:
            /var/tmp/sparkjars/postgresql-42.6.0.jar
            /var/tmp/sparkjars/aws-java-sdk-bundle-1.12.262.jar
            /var/tmp/sparkjars/hadoop-aws-3.3.4.jar
        3. Postgres JDBC driver (postgresql-42.6.0.jar or later)
        4. S3 Bucket name (<s3_bucket_name>) (Mirth connect is storing
                                            RAW HL7 messages as JSON file
                                            in a S3 bucket)
        5. S3 Bucket Prefix (yyyy/m/d)
        6. S3 Bucket contains, single, or a set of JSON files that are
            formated like the Sample JSON file.
        7. etl.config file to store configuration details etc:
            [reportdb]
            host=
            port=5432
            dbname=
            dbuser=
            dbuserpass=

            [spark]
            master=
            masterport=7077

            [redis]
            host=
            port=6379

            [aws]
            access.key=
            secret.key=
        8. List of fields to ignore stored in "hl7_field_names_to_ignore.txt" file
            Sample:
                al1_1_set_id_al1_si_none_1
                evn_1_event_type_code_id_none
                evn_5_operator_id_xcn_2_family_name_2
                evn_5_operator_id_xcn_3_given_name_2
                evn_5_operator_id_xcn_9_assigning_authority_1
                gt1_10_guarantor_type_is_none_1
                gt1_11_guarantor_relationship_ce_1_identifier_1
                gt1_12_guarantor_ssn_st_none_1
                gt1_16_guarantor_employer_name_xpn_1_family_name_1
                gt1_17_guarantor_employer_address_xad_1_street_address_1
                gt1_17_guarantor_employer_address_xad_3_city_1
                gt1_17_guarantor_employer_address_xad_4_state_or_province_1
                gt1_17_guarantor_employer_address_xad_5_zip_or_postal_code_1
                gt1_17_guarantor_employer_address_xad_6_country_1
                gt1_18_guarantor_employer_phone_number_xtn_1_telephone_number_1
                gt1_20_guarantor_employment_status_is_none_1
                gt1_23_guarantor_credit_rating_code_ce_1_identifier_1
                gt1_2_guarantor_number_cx_1_id_number_1
                gt1_3_guarantor_name_xpn_4_suffix_e_g_jr_or_iii_1
                gt1_3_guarantor_name_xpn_5_prefix_e_g_dr_1
                gt1_3_guarantor_name_xpn_7_name_type_code_1
                gt1_4_guarantor_spouse_name_xpn_1_family_name_1
                gt1_4_guarantor_spouse_name_xpn_2_given_name_1
                gt1_5_guarantor_address_xad_1_street_address_1
        9. Field mapping file "field_map.txt", 
            see field_name = f'{ac_name}_{ac_long_name}_{fc_name}_{fc_long_name}':
            Sample:
                ('pid_2_patient_id_cx_1_id_number','pt_id_4')
                ('pid_30_patient_death_indicator_id_none','pt_death_indicator')
                ('pid_3_patient_identifier_list_cx_1_id_number_2','pt_id_2')
                ('pid_3_patient_identifier_list_cx_1_id_number_3','pt_id_5')
                ('pid_4_alternate_patient_id_pid_cx_1_id_number','pt_id_3')
                ('pid_5_patient_name_xpn_1_family_name','pt_last_name')


## How-to Run:
        > ./s3_json_to_psql_etl.py --adt-feed-name "acme,roadrunner"

            23/09/01 13:31:21 WARN NativeCodeLoader: Unable to load native-hadoop library for your platform... using builtin-java classes where applicable
            Setting default log level to "WARN".
            To adjust logging level use sc.setLogLevel(newLevel). For SparkR, use setLogLevel(newLevel).

            **** Starting for acme

            23/09/01 13:31:23 WARN MetricsConfig: Cannot locate configuration: tried hadoop-metrics2-s3a-file-system.properties,hadoop-metrics2.properties
            23/09/01 13:32:01 WARN package: Truncated the string representation of a plan since it was too large. This behavior can be adjusted by setting 'spark.sql.debug.maxToStringFields'.

            **** Stored data in table v4_acme
            **** Completed for acme
            **** Starting for roadrunner
            **** Stored data in table v4_roadrunner
            **** Completed for roadrunner

## Example table names:
         public | v4_acme       | table |
         public | v4_roadrunner | table |

## Sample JSON file:
        {
          "patientId": "123456789",
          "tenantId": "<tenant id>",
          "dob": "1990-01-01",
          "id": 123456788,
          "updatedAt": "2023-09-01 00:59:22",
          "createdAt": "2023-09-01 00:59:22",
          "visitNumber": "987654321",
          "MSH": "MSH|^~&|EPICCARE|WB^WBVC|||20230901095922|S327628|ADT^A08^ADT_A01|777777777|P|2.3",
          "EVN": "EVN|A08|20230901095922||REG_UPDATE_VISIT_CHANGE|S327628^RNLASTNAME^RNFIRSTNAME^^^^^^WB^^^^^WBVC||WBVC^1740348929^SOMETEXT",
          "PID": "PID|1||12345678^^^^EPI~123456789^^^^SOMEMRN||FIRSTNAME^LASTNAME||19900101|M|||123 SOME ST^^A CITY^CA^12345^USA^P^^SC",
          "PV1": "PV1|||WBVCERDA^ED07^07^WBVC^^^WBVC^^WBVC EMERGENCY||||||||||||||||128988888"
        }

## Sample PostgreSQL table - (Note: JDBC writer does not insert if data already exists):
                      Column              | Type | Collation | Nullable | Default | Storage  |
        ----------------------------------+------+-----------+----------+---------+----------+
         dob                              | text |           |          |         | extended |
         pt_event_recorded_date_time_1    | text |           |          |         | extended |
         pt_event_reason_code             | text |           |          |         | extended |
         pt_opr_assigning_facility_1      | text |           |          |         | extended |
         pt_event_operator_id_num_1       | text |           |          |         | extended |
         pt_event_operator_last_name      | text |           |          |         | extended |
         pt_event_operator_first_name     | text |           |          |         | extended |
         pt_opr_assigning_auth_1          | text |           |          |         | extended |
         pt_event_facil_namespace_id      | text |           |          |         | extended |
         pt_event_facil_universal_id      | text |           |          |         | extended |
         pt_event_facil_universal_id_type | text |           |          |         | extended |
         patientid                        | text |           |          |         | extended |
         pt_address_st_1                  | text |           |          |         | extended |
         pt_address_city                  | text |           |          |         | extended |
         pt_address_state_prov            | text |           |          |         | extended |
         pt_address_zip_postal            | text |           |          |         | extended |
         pt_address_country               | text |           |          |         | extended |
         pt_address_type                  | text |           |          |         | extended |
         pt_county_parish                 | text |           |          |         | extended |
         pt_last_name                     | text |           |          |         | extended |
         pt_first_name                    | text |           |          |         | extended |
         pt_dob                           | text |           |          |         | extended |
         pt_gender                        | text |           |          |         | extended |
         pt_visit_number                  | text |           |          |         | extended |
         pt_loc_poc_1                     | text |           |          |         | extended |
         pt_loc_room_1                    | text |           |          |         | extended |
         pt_loc_bed_1                     | text |           |          |         | extended |
         pt_loc_facility_1                | text |           |          |         | extended |
         pt_loc_description               | text |           |          |         | extended |
         pt_event_occur_date_time         | text |           |          |         | extended |
