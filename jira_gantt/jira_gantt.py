#!/usr/bin/env python3
"""Quick in dirty gantt/timeline builder for Atlassian Jira Epics
    across MULTIPLE projects within the same instance.

    Requires:
        1. Access to JIRA Cloud instance - currently this works with
            single domain only.
        2. JIRA Personal Access Token
        3. PostgreSQL database: create table, destroy table, write table
            access required (

    TODO:
        1. Compute Percentage completion based on status and started dates
        3. Prettify the layout, but keep it simple
        4. Add issue status to the bar
        5. Move to an in-memory SQLite3 DB instead of PostgreSQL
        6. Since relationship between projects and tasks is one-to-many
            and many-to-many, meaning that a project can have multiple
            tasks, and a task can be associated with multiple projects.
            To represent this relationship, use multiple tables.

    DONE:
        0. Split code into class and helpers etc
        2. Live links for issue numbers
"""

from atlassian import Jira
from requests.auth import HTTPBasicAuth
from time import strftime, localtime, time

import configparser
import logging
import pandas as pd  # pyspark dataframes are better
import pathlib
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import random
import requests

# suppress Pandas UserWarning about using SQLAlchemy only
import warnings
warnings.simplefilter(action="ignore", category=UserWarning)

class JiraGanttBuilder:
    """Jira Builder Class
    """

    def __init__(self, config_path="setup.config"):
        self.CONFIG = self.read_config(config_path)
        self.PROJECTS = ["SCRUM", "ACME"]
        self.JIRA = Jira(
                         url=self.CONFIG.get("jira", "url"),
                         username=self.CONFIG.get("jira", "token_user"),
                         password=self.CONFIG.get("jira", "access_token"),
                         cloud=True,
                        )
        self.EPOCH_TIME_INT = int(time())
        self.EPOCH_TIME_STR = str(self.EPOCH_TIME_INT)
        self.DATETIME_TIMESTAMP = strftime(
                                           "%Y-%m-%d %H:%M:%S", localtime(self.EPOCH_TIME_INT)
                                          )
        self.PSQL_TABLE_NAME = self.CONFIG.get("psqldb", "tablename")
        self.BROWSE_URL = self.CONFIG.get("jira","url") + "/browse/"

    def read_config(self, file_path):
        """Read setup config file
        """

        if pathlib.Path(file_path).exists():
            config_obj = configparser.RawConfigParser()
            config_obj.read(file_path)

            return config_obj
        else:
            raise FileNotFoundError(f"Config file {file_path} not found.")

    def psql_connection(self):
        """Connect to PostgreSQL server
        """

        db_config = {
                     "database": self.CONFIG.get("psqldb", "dbname"),
                     "host": self.CONFIG.get("psqldb", "host"),
                     "user": self.CONFIG.get("psqldb", "dbuser"),
                     "password": self.CONFIG.get("psqldb", "dbuserpass"),
                     "port": self.CONFIG.get("psqldb", "port"),
                    }

        try:
            psql_conn = psycopg2.connect(**db_config)
            psql_cur = psql_conn.cursor()

            return psql_conn, psql_cur
        except psycopg2.Error as e:
            logging.error(f"Error connecting to PostgreSQL: {e}")
            raise

    def db_write(self, table_name, dataobjects, psql_cursor):
        """TODO: use in-memory SQLite3 instead. PSQL will do for now though
            Requires: see "jira_gantt_table.sql"
            Stores Jira issue objects in a PostgreSQL table. Queries are
            executed against this data to derive the percent completion for epics.
        """

        cleanup_query = f"truncate table {table_name};"
        psql_cursor.execute(cleanup_query)

        for dataobject in dataobjects:
            cols = str(tuple(dataobject.keys())).replace("'", "")
            vals = str(tuple(dataobject.values()))
            query = f"INSERT INTO {table_name} {cols} VALUES {vals};"
            try:
                psql_cursor.execute(query)
                psql_cursor.connection.commit()
            except psycopg2.Error as e:
                logging.error(
                              f"Unable to execute query or commit for table {table_name} - {e}"
                             )
                raise

    def get_percent_completion_project(
                                       self, percent_complete_task_colname, psql_table
                                      ):
        """See "jira_gantt_table.sql" for column names and data types etc
            SQL queries that:
                1. Calculate percentage completed for an EPIC/Project
                2. While EPIC is the root of all considerations, an EPIC
                    is also treated as an ISSUE when grouping bar chart
                    by EPIC, therefore, an SQL query updates the percentage
                    completed columns for each "issue"(EPIC or otherwise)
                3. SQL query also separately updates percentage completed
                    column for EPICs that do not have any linked or child
                    issues.
        """

        sql = f"""
                 SELECT
                     project,
                     AVG({percent_complete_task_colname}) AS percentagecompletedproject
                 FROM {psql_table}
                 WHERE project = task
                 GROUP BY project;
               """

        update_sql_epics_with_issues = f"""
                                          WITH subquery AS (
                                              SELECT
                                                  project,
                                                  AVG({percent_complete_task_colname}) AS percentagecompletedproject
                                              FROM {psql_table}
                                              WHERE project != task
                                              GROUP BY project
                                          )
                                          UPDATE {psql_table}
                                          SET {percent_complete_task_colname} = subquery.percentagecompletedproject
                                          FROM subquery
                                          WHERE {psql_table}.task = subquery.project;
                                        """
        update_sql_epics_without_issues = f"""
                                             WITH subquery AS (
                                                 SELECT
                                                     project,
                                                     AVG({percent_complete_task_colname}) AS percentagecompletedproject
                                                 FROM {psql_table}
                                                 WHERE project = task AND percentagecompletedtask = 0
                                                 GROUP BY project
                                             )
                                             UPDATE {psql_table}
                                             SET {percent_complete_task_colname} = subquery.percentagecompletedproject
                                             FROM subquery
                                             WHERE {psql_table}.task = subquery.project;
                                           """

        conn, cur = self.psql_connection()

        try:
            cur.execute(update_sql_epics_with_issues)
            cur.connection.commit()
            cur.execute(update_sql_epics_without_issues)
            cur.connection.commit()
            cur.execute(sql)
            cur.connection.commit()
            percent_complete_proj_df = pd.DataFrame(
                                                    cur.fetchall(),
                                                    columns=[
                                                             "project",
                                                             "percentagecompletedproject"
                                                            ]
                                                   )
            cur.close()
            conn.close()

            return percent_complete_proj_df
        except:
            logging.error(f"Error executing query")
            raise

    def psql_to_df(self, table_name):
        """Uses Pandas to convert SQL query to a dataframe.
            LESSON LEARNED FOR ME:
            Since I wanted to avoid Apache Spark setup, I went with Pandas
            for dealing with dataframes. However, it turns out Pandas does
            not 'officially' support psycopg2, as stated in the warning
            message (which is suppressed at the beginning of this app),
            generated by the following code. Then I learned that while
            it's simple to create a Pandas dataframe from rows of data
            fetched via psycopg2, the resulting dataframe does NOT map
            column names. Hence, I am using this for now. Ideally, I should
            switch from psycopg2 to officially supported SQLAlchemy. Until
            then, psycopg2 it shall remain.
            Requires: PSQL_TABLE_NAME from setup.config
        """

        conn, _ = self.psql_connection()

        # epic should always be at the top of the group
        sql_query = f"""
                        SELECT *
                        FROM (
                            SELECT
                                *,
                                ROW_NUMBER() OVER
                                    (PARTITION BY project ORDER BY CASE WHEN project = task THEN 0 ELSE 1 END) AS row_num
                            FROM {table_name} p
                        ) AS subquery
                        ORDER BY project, row_num DESC;
                     """

        psql_to_df = pd.read_sql_query(sql_query, conn)
        conn.close()

        return psql_to_df

    def build_issue_object(self):
        """Create a list of dictionaries

            Sample Dictionary
                {
                 "project": "ACME-1",
                 "task": "ACME-2",
                 "projectstart": "2023-12-29",
                 "projectfinish": "2024-01-19",
                 "taskstart": "2023-12-29",
                 "taskfinish": "2024-01-02",
                 "percentagecompletedtask": 27,
                 "summary": "Task: Create Documentation"
                }
            TODO:
                Right now task_completed_percentage is a randomly assigned number,
                compute task_completed_percentage based on issue worklog
        """

        issue_objects = []

        # unique list of issues missing start or due date
        issues_missing_start_or_end_dates = set()

        epic_keys = self.get_all_epics(self.PROJECTS, self.JIRA)
        for epic_key in epic_keys:
            issue = self.JIRA.issue(epic_key)
            linked_issues = self.all_issues_per_epic(epic_key, self.JIRA, issue)
            linked_issues.append(epic_key)  # shows project timeline
            issue_start_date, issue_due_date = (
                                                self.get_issue_start_date(epic_key, self.JIRA),
                                                issue["fields"]["duedate"],
                                               )
            if linked_issues:
                for linked_issue in linked_issues:
                    browse_url = self.BROWSE_URL + linked_issue
                    start_date = self.get_issue_start_date(linked_issue, self.JIRA)
                    the_issue = self.JIRA.issue(linked_issue)
                    issue_summary = the_issue["fields"]["summary"]
                    due_date = the_issue["fields"]["duedate"]
                    issue_type = the_issue["fields"]["issuetype"]["name"]

                    # TODO: use later (fixme)
                    #the_issue_status = self.get_issue_status(linked_issue, self.JIRA)

                    # TODO: use issue worklog to compute
                    task_completed_percentage = random.randrange(20, 80)

                    if not start_date or not due_date:
                        issues_missing_start_or_end_dates.add(linked_issue)
                    else:
                        if epic_key == linked_issue:
                            task_completed_percentage = 0
                        issue_object = {
                                        "project": epic_key,
                                        "task": linked_issue,
                                        "projectstart": issue_start_date,
                                        "projectfinish": issue_due_date,
                                        "taskstart": start_date,
                                        "taskfinish": due_date,
                                        "percentagecompletedtask": task_completed_percentage,
                                        "summary": f'<a href="{browse_url}">{issue_type}: {issue_summary}'
                                       }
                        issue_objects.append(issue_object)

        if issues_missing_start_or_end_dates:
            logging.info(
                         f'Following tickets are missing start or due dates \
                           {issues_missing_start_or_end_dates}'
                        )

        return issue_objects

    def get_all_epics(self, project_keys, jira_obj):
        """Use JQL to query all epics for the list of PROJECTs supplied.
        """

        # covers project names with spaces
        project_key = ",".join(map("'{0}'".format, project_keys))

        jql = f"project in ({project_key}) and issuetype = Epic and status not in (Done)"

        return self.exec_jql(jql, jira_obj)

    def get_epic_children(self, epic_key, jira_obj):
        """JQL: get list of children for a given EPIC issue id.
        """

        jql = f"parent = {epic_key}"

        return self.exec_jql(jql, jira_obj)

    def get_issues_linked(self, an_issue):
        """Generate a list of issues linked to a given issue
        """

        list_of_issues = []
        issues_linked = an_issue["fields"]["issuelinks"]
        if issues_linked:
            for issue_linked in issues_linked:
                if "inwardIssue" in issue_linked:
                    list_of_issues.append(issue_linked["inwardIssue"]["key"])

        return list_of_issues

    def all_issues_per_epic(self, epic_key, jira_obj, an_issue):
        """Generate a list of linked and children associated with an issue.
            In this case issue type of Epic.
        """

        children = self.get_epic_children(epic_key, jira_obj)
        issues_linked = self.get_issues_linked(an_issue)

        return children + issues_linked if issues_linked or children else []

    def jira_get_start_date_custom_field(self):
        """Only supported by the JIRA Cloud REST API
            Start Date is a custom field in JIRA Cloud. Since the customfield id
            for Start Date field may change, always lookup using the name.
            Perhaps there's a better way?
        """

        end_point = '/rest/api/3/field/search?type=custom&maxResults=100'
        api_url = f"{self.CONFIG.get('jira', 'url')}{end_point}"
        auth = HTTPBasicAuth(
                             self.CONFIG.get("jira", "token_user"),
                             self.CONFIG.get("jira", "access_token")
                            )
        headers = {"Accept": "application/json"}

        try:
            response = requests.get(api_url, headers=headers, auth=auth, timeout=100)

            for custom_field in response.json().get("values", []):
                if custom_field["name"] == "Start date":
                    return custom_field["id"]
            return False
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logging.error(f"Error connecting to Jira Cloud \
            Instance STATUS_CODE: {status_code}")
            raise

    def get_issue_status(self, an_issue_key, jira_obj):
        """JIRA's native API. Get status of a given Jira Issue KEY
        """

        return jira_obj.get_issue_status(an_issue_key)

    def get_issue_start_date(self, an_issue_key, jira_obj):
        """Use JIRA Cloud REST API to get customfield id, then
            use JIRA's native API to get the start date
        """

        # customfield lookup
        issue_start_date_custom_field = self.jira_get_start_date_custom_field()
        issue_start_date = jira_obj.issue_field_value(
                                                      an_issue_key,
                                                      issue_start_date_custom_field
                                                     )
        return issue_start_date

    def exec_jql(self, jql, jira_obj):
        """Execute JQL, and return sorted list of issues
        """

        try:
            issues = jira_obj.jql(jql)
            issues_list = [an_issue["key"] for an_issue in issues.get("issues", [])]
            return sorted(issues_list) if issues_list else []
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logging.error(
                          f"Error connecting to Jira Cloud Instance STATUS_CODE: {status_code}"
                         )
            raise


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    jira_gantt_builder = JiraGanttBuilder()
    p_conn, p_cur = jira_gantt_builder.psql_connection()
    issue_objs = jira_gantt_builder.build_issue_object()

    jira_gantt_builder.db_write(jira_gantt_builder.PSQL_TABLE_NAME, issue_objs, p_cur)

    for an_epic in issue_objs:
        df2 = jira_gantt_builder.get_percent_completion_project(
                                                                "percentagecompletedtask",
                                                                jira_gantt_builder.PSQL_TABLE_NAME
                                                               )

    df = jira_gantt_builder.psql_to_df(jira_gantt_builder.PSQL_TABLE_NAME)
    df = pd.merge(df, df2, on="project", how="left")

    # convert columns to datatime
    df["Start"] = pd.to_datetime(df["projectstart"])
    df["Finish"] = pd.to_datetime(df["projectfinish"])
    df["Task Start"] = pd.to_datetime(df["taskstart"])
    df["Task Finish"] = pd.to_datetime(df["taskfinish"])

    # graph setup
    fig = px.timeline(
                      df,
                      x_start="Task Start",
                      x_end="Task Finish",
                      y="project",
                      color="task",
                      color_discrete_sequence=["goldenrod"],
                      text="summary",
                      title=f"JIRA Projects Gantt Chart<br>\
                      <i>{jira_gantt_builder.DATETIME_TIMESTAMP}</i>",
                      labels={"Percentage Completed": "Complete (%)"},
                      custom_data=[
                                  "percentagecompletedtask",
                                  "percentagecompletedproject",
                                  "taskstart",
                                  "taskfinish",
                                  "project",
                                  "summary",
                                  "task",
                                  ],
                    )

    # hover box with tons of data
    fig.update_traces(
                      hovertemplate="<b>%{text}</b><br>\
                                    <i>Project: %{customdata[4]}</i><br>\
                                    Task: %{customdata[6]}<br>\
                                    Start: %{customdata[2]}<br>\
                                    Finish: %{customdata[3]}<br>\
                                    Task Complete: %{customdata[0]:.2f}%<br>\
                                    Project Complete: %{customdata[1]:.2f}%"\
                     )

    # iterate over the dataframe
    for index, row in df.iterrows():

        # bar graph
        fig.add_trace(
                      go.Bar(
                             x=[row["Task Start"]],
                             y=[row["project"]],
                             orientation="h",
                             opacity=0,
                             textposition="auto",
                             showlegend=False,
                             name='gantt chart'
                            )
                     )

    # add vertical today's date marker to the graph
    fig.add_vline(x=jira_gantt_builder.DATETIME_TIMESTAMP, line_width=3, line_color="green")

    # add text to vertical line
    fig.add_annotation(
                       x=jira_gantt_builder.DATETIME_TIMESTAMP,
                       text="Today",
                       align="left",
                       showarrow=True,
                       arrowcolor="green",
                       arrowhead=2,
                       y=0,
                       yshift=10,
                      )

    # group bars by project, and show MM-DD on X axis
    fig.update_layout(
                      showlegend=False,
                      barmode="group",
                      autosize=True,
                      xaxis_tickformat="%m-%d",
                      bargap=0,
                      bargroupgap=0
                     )

    # update X n Y titles
    fig.update_yaxes(
                     title_text="Jira Epics",
                     type='category',
                     categoryarray=df['project'],
                     categoryorder='array',
                    )
    fig.update_xaxes(title_text="Timeline")

    fig.show()
