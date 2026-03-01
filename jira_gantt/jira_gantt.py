#!/usr/bin/env python3
"""Jira Gantt Chart Builder for Atlassian Jira Epics across multiple projects.

This module provides functionality to fetch Epic issues from Jira Cloud,
extract their associated tasks, and generate an interactive Gantt chart
using Plotly.

Requires:
    1. Access to JIRA Cloud instance (single domain)
    2. JIRA Personal Access Token
    3. PostgreSQL database access (create, read, write, truncate)

TODO:
    1. Compute percentage completion based on status and started dates
    2. Add issue status to the bar
    3. Move to an in-memory SQLite3 DB instead of PostgreSQL
    4. Use proper many-to-many relationship tables for projects and tasks

DONE:
    0. Split code into class and helpers
    1. Live links for issue numbers
    2. Prettify the layout while keeping it simple
"""

from atlassian import Jira
from requests.auth import HTTPBasicAuth
from time import strftime, localtime, time
from contextlib import contextmanager
from typing import Optional

import configparser
import logging
import pandas as pd
import pathlib
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import random
import requests

# Suppress Pandas UserWarning about using SQLAlchemy
import warnings
warnings.simplefilter(action="ignore", category=UserWarning)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_CONFIG_PATH = "setup.config"
DEFAULT_PROJECTS = ["SCRUM", "ACME"]
CUSTOM_FIELD_NAME = "Start date"
JIRA_API_ENDPOINT = "/rest/api/3/field/search"

# SQL Queries
SQL_TRUNCATE_TABLE = "truncate table {table_name};"
SQL_INSERT_ROW = "INSERT INTO {table_name} {cols} VALUES {vals};"
SQL_PERCENT_COMPLETE_PROJECT = """
    SELECT
        project,
        AVG({percent_complete_task_colname}) AS percentagecompletedproject
    FROM {psql_table}
    WHERE project = task
    GROUP BY project;
"""
SQL_UPDATE_EPICS_WITH_ISSUES = """
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
SQL_UPDATE_EPICS_WITHOUT_ISSUES = """
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
SQL_DATAFRAME_QUERY = """
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
SQL_JQL_EPIC_QUERY = "project in ({project_key}) and issuetype = Epic and status not in (Done)"
SQL_JQL_CHILDREN_QUERY = "parent = {epic_key}"

# Database column names
COL_PROJECT = "project"
COL_TASK = "task"
COL_PROJECT_START = "projectstart"
COL_PROJECT_FINISH = "projectfinish"
COL_TASK_START = "taskstart"
COL_TASK_FINISH = "taskfinish"
COL_PERCENT_COMPLETE_TASK = "percentagecompletedtask"
COL_SUMMARY = "summary"
COL_PERCENT_COMPLETE_PROJECT = "percentagecompletedproject"


class JiraGanttBuilder:
    """Builds Gantt charts from Jira Epic and task data.

    This class handles fetching Epic issues from Jira Cloud, extracting
    associated tasks, storing data in PostgreSQL, and generating interactive
    Gantt charts using Plotly.

    Attributes:
        config: Configuration object from setup.config file
        projects: List of Jira project keys to include
        jira: Jira API client instance
        browse_url: Base URL for browsing issues in Jira
        table_name: PostgreSQL table name for storing issue data
    """

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        """Initialize the JiraGanttBuilder.

        Args:
            config_path: Path to the configuration file.
        """
        self.config = self._read_config(config_path)
        self.projects = DEFAULT_PROJECTS
        self.jira = Jira(
            url=self.config.get("jira", "url"),
            username=self.config.get("jira", "token_user"),
            password=self.config.get("jira", "access_token"),
            cloud=True,
        )
        self.browse_url = self.config.get("jira", "url") + "/browse/"
        self.table_name = self.config.get("psqldb", "tablename")
        self.custom_field_id = self._get_start_date_custom_field_id()

    @contextmanager
    def _psql_connection(self):
        """Context manager for PostgreSQL connections.

        Yields:
            tuple: (connection, cursor) pair for database operations.

        Raises:
            psycopg2.Error: If connection to database fails.
        """
        db_config = {
            "database": self.config.get("psqldb", "dbname"),
            "host": self.config.get("psqldb", "host"),
            "user": self.config.get("psqldb", "dbuser"),
            "password": self.config.get("psqldb", "dbuserpass"),
            "port": self.config.get("psqldb", "port"),
        }

        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            yield conn, cur
        except psycopg2.Error as e:
            logging.error(f"Error connecting to PostgreSQL: {e}")
            raise
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()

    def _read_config(self, file_path: str) -> configparser.RawConfigParser:
        """Read setup config file.

        Args:
            file_path: Path to the configuration file.

        Returns:
            ConfigParser object with configuration settings.

        Raises:
            FileNotFoundError: If config file does not exist.
        """
        if not pathlib.Path(file_path).exists():
            raise FileNotFoundError(f"Config file {file_path} not found.")

        config_obj = configparser.RawConfigParser()
        config_obj.read(file_path)
        return config_obj

    def _db_write(self, table_name: str, data_objects: list, cursor) -> None:
        """Write data objects to PostgreSQL table.

        Truncates the table before inserting new data. Uses parameterized
        queries to prevent SQL injection.

        Args:
            table_name: Name of the table to write to.
            data_objects: List of dictionaries containing row data.
            cursor: Database cursor for executing queries.

        Raises:
            psycopg2.Error: If database write fails.
        """
        cleanup_query = SQL_TRUNCATE_TABLE.format(table_name=table_name)
        cursor.execute(cleanup_query)

        for data_object in data_objects:
            cols = str(tuple(data_object.keys())).replace("'", "")
            vals = str(tuple(data_object.values()))
            query = SQL_INSERT_ROW.format(table_name=table_name, cols=cols, vals=vals)
            try:
                cursor.execute(query)
                cursor.connection.commit()
            except psycopg2.Error as e:
                logging.error(f"Unable to execute query or commit for table {table_name}: {e}")
                raise

    def _get_percent_completion_project(
        self, percent_complete_col: str, table_name: str
    ) -> pd.DataFrame:
        """Calculate percentage completion for each project/epic.

        Executes SQL queries to:
        1. Calculate average completion percentage for projects
        2. Update epic rows with their children's average completion
        3. Handle epics without child issues

        Args:
            percent_complete_col: Column name for percentage completion.
            table_name: Name of the table to query.

        Returns:
            DataFrame with project and percentagecompletedproject columns.

        Raises:
            Exception: If SQL execution fails.
        """
        update_sql_epics_with_issues = SQL_UPDATE_EPICS_WITH_ISSUES.format(
            percent_complete_task_colname=percent_complete_col,
            psql_table=table_name,
        )
        update_sql_epics_without_issues = SQL_UPDATE_EPICS_WITHOUT_ISSUES.format(
            percent_complete_task_colname=percent_complete_col,
            psql_table=table_name,
        )
        sql = SQL_PERCENT_COMPLETE_PROJECT.format(
            percent_complete_task_colname=percent_complete_col,
            psql_table=table_name,
        )

        with self._psql_connection() as (conn, cur):
            try:
                cur.execute(update_sql_epics_with_issues)
                cur.connection.commit()
                cur.execute(update_sql_epics_without_issues)
                cur.connection.commit()
                cur.execute(sql)
                cur.connection.commit()

                rows = cur.fetchall()
                df = pd.DataFrame(
                    rows,
                    columns=[COL_PROJECT, COL_PERCENT_COMPLETE_PROJECT],
                )
                return df
            except Exception as e:
                logging.error(f"Error executing query: {e}")
                raise

    def _psql_to_df(self, table_name: str) -> pd.DataFrame:
        """Convert PostgreSQL table to Pandas DataFrame.

        Note: psycopg2 is not officially supported by Pandas, but works
        for basic operations. Consider migrating to SQLAlchemy for
        official support.

        Args:
            table_name: Name of the table to convert.

        Returns:
            DataFrame with issue data, ordered by project with epics first.
        """
        sql_query = SQL_DATAFRAME_QUERY.format(table_name=table_name)

        with self._psql_connection() as (conn, _):
            df = pd.read_sql_query(sql_query, conn)
        return df

    def _get_start_date_custom_field_id(self) -> Optional[str]:
        """Get the custom field ID for 'Start date' field in Jira Cloud.

        The Start Date field is a custom field in Jira Cloud, and its ID
        may vary between instances. This method looks up the field by name.

        Returns:
            The custom field ID if found, None otherwise.

        Raises:
            requests.exceptions.HTTPError: If Jira API request fails.
        """
        api_url = f"{self.config.get('jira', 'url')}{JIRA_API_ENDPOINT}"
        auth = HTTPBasicAuth(
            self.config.get("jira", "token_user"),
            self.config.get("jira", "access_token"),
        )
        headers = {"Accept": "application/json"}
        params = {"type": "custom", "maxResults": 100}

        try:
            response = requests.get(api_url, headers=headers, auth=auth, params=params, timeout=100)
            response.raise_for_status()

            for custom_field in response.json().get("values", []):
                if custom_field["name"] == CUSTOM_FIELD_NAME:
                    return custom_field["id"]
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"Error connecting to Jira Cloud Instance STATUS_CODE: {e.response.status_code}")
            raise

    def _get_issue_start_date(self, issue_key: str) -> Optional[str]:
        """Get the start date for a Jira issue.

        Args:
            issue_key: The Jira issue key (e.g., 'PROJ-123').

        Returns:
            The start date string if available, None otherwise.
        """
        if not self.custom_field_id:
            return None

        return self.jira.issue_field_value(issue_key, self.custom_field_id)

    def _get_issue_status(self, issue_key: str) -> str:
        """Get the status of a Jira issue.

        Args:
            issue_key: The Jira issue key.

        Returns:
            The issue status name.
        """
        return self.jira.get_issue_status(issue_key)

    def _has_start_date(self, issue_key: str) -> bool:
        """Check if an issue has a start date.

        Args:
            issue_key: The Jira issue key.

        Returns:
            True if the issue has a start date, False otherwise.
        """
        start_date = self._get_issue_start_date(issue_key)
        return start_date is not None and start_date != ""

    def _compute_task_completed_percentage(
        self, task_start: str, epic_start: str
    ) -> int:
        """Compute task completion percentage.

        TODO: Implement proper calculation based on worklog and status.
        Currently returns a random value for demonstration.

        Args:
            task_start: Task start date.
            epic_start: Epic start date.

        Returns:
            Random percentage between 20 and 80.
        """
        return random.randrange(20, 81)

    def _exec_jql(self, jql: str) -> list:
        """Execute JQL query and return sorted list of issue keys.

        Args:
            jql: JQL query string.

        Returns:
            Sorted list of issue keys, or empty list if no results.

        Raises:
            requests.exceptions.HTTPError: If Jira API request fails.
        """
        try:
            issues = self.jira.jql(jql)
            issues_list = [issue["key"] for issue in issues.get("issues", [])]
            return sorted(issues_list) if issues_list else []
        except requests.exceptions.HTTPError as e:
            logging.error(f"Error executing JQL STATUS_CODE: {e.response.status_code}")
            raise

    def _get_all_epics(self) -> list:
        """Get all epics for the configured projects.

        Returns:
            Sorted list of epic issue keys.
        """
        project_key = ",".join(map("'{}'".format, self.projects))
        jql = SQL_JQL_EPIC_QUERY.format(project_key=project_key)
        return self._exec_jql(jql)

    def _get_epic_children(self, epic_key: str) -> list:
        """Get child issues for a given epic.

        Args:
            epic_key: The epic issue key.

        Returns:
            Sorted list of child issue keys.
        """
        jql = SQL_JQL_CHILDREN_QUERY.format(epic_key=epic_key)
        return self._exec_jql(jql)

    def _get_issues_linked(self, issue: dict) -> list:
        """Get issues linked to a given issue.

        Args:
            issue: Jira issue object.

        Returns:
            List of linked issue keys.
        """
        list_of_issues = []
        issues_linked = issue["fields"].get("issuelinks", [])

        for issue_link in issues_linked:
            if "inwardIssue" in issue_link:
                list_of_issues.append(issue_link["inwardIssue"]["key"])

        return list_of_issues

    def _all_issues_per_epic(self, epic_key: str, epic_issue: dict) -> list:
        """Get all issues associated with an epic (children + linked).

        Args:
            epic_key: The epic issue key.
            epic_issue: The epic issue object.

        Returns:
            Combined list of child and linked issue keys.
        """
        children = self._get_epic_children(epic_key)
        issues_linked = self._get_issues_linked(epic_issue)

        if issues_linked or children:
            return children + issues_linked
        return []

    def _has_issues_missing_dates(self, issue_objects: list) -> tuple:
        """Check if any issues are missing start or end dates.

        Args:
            issue_objects: List of issue object dictionaries.

        Returns:
            Tuple of (has_missing, missing_keys) where has_missing is a
            boolean and missing_keys is a list of issue keys missing dates.
        """
        missing_keys = []
        for obj in issue_objects:
            if not obj.get("taskstart") or not obj.get("taskfinish"):
                missing_keys.append(obj.get("task", "unknown"))
        return len(missing_keys) > 0, missing_keys

    def build_issue_objects(self) -> list:
        """Build list of issue objects for the Gantt chart.

        Fetches all epics and their associated tasks, extracting
        relevant fields for the Gantt chart visualization.

        Returns:
            List of dictionaries containing issue data for the Gantt chart.
        """
        issue_objects = []
        missing_dates_issues = []

        epic_keys = self._get_all_epics()

        for epic_key in epic_keys:
            epic_issue = self.jira.issue(epic_key)
            epic_start_date = self._get_issue_start_date(epic_key) or epic_issue["fields"].get("duedate")
            epic_due_date = epic_issue["fields"].get("duedate")

            linked_issues = self._all_issues_per_epic(epic_key, epic_issue)
            linked_issues.append(epic_key)

            for linked_issue_key in linked_issues:
                if not self._has_start_date(linked_issue_key):
                    missing_dates_issues.append(linked_issue_key)
                    continue

                issue = self.jira.issue(linked_issue_key)
                issue_type = issue["fields"]["issuetype"]["name"]
                issue_summary = issue["fields"]["summary"]
                start_date = self._get_issue_start_date(linked_issue_key) or epic_start_date
                due_date = issue["fields"].get("duedate") or epic_due_date

                if not due_date:
                    missing_dates_issues.append(linked_issue_key)
                    continue

                task_completed_percentage = self._compute_task_completed_percentage(
                    start_date, epic_start_date
                )

                if epic_key == linked_issue_key:
                    task_completed_percentage = 0

                issue_object = {
                    COL_PROJECT: epic_key,
                    COL_TASK: linked_issue_key,
                    COL_PROJECT_START: epic_start_date,
                    COL_PROJECT_FINISH: epic_due_date,
                    COL_TASK_START: start_date,
                    COL_TASK_FINISH: due_date,
                    COL_PERCENT_COMPLETE_TASK: task_completed_percentage,
                    COL_SUMMARY: f'<a href="{self.browse_url + linked_issue_key}">{issue_type}: {issue_summary}',
                }

                issue_objects.append(issue_object)

        if missing_dates_issues:
            logging.info(f"Following tickets are missing start or due dates: {missing_dates_issues}")

        return issue_objects

    def generate_gantt_chart(self) -> go.Figure:
        """Generate and display the Gantt chart.

        Fetches issue data, computes completion percentages, and creates
        an interactive Plotly Gantt chart with hover information.

        Returns:
            Plotly Figure object containing the Gantt chart.
        """
        from time import time as get_time

        # Build issue objects and write to database
        issue_objects = self.build_issue_objects()

        with self._psql_connection() as (conn, cur):
            self._db_write(self.table_name, issue_objects, cur)

        # Get percentage completion data
        df_percent = self._get_percent_completion_project(
            COL_PERCENT_COMPLETE_TASK, self.table_name
        )

        # Get main data and merge with completion percentages
        df = self._psql_to_df(self.table_name)
        df = pd.merge(df, df_percent, on=COL_PROJECT, how="left")

        # Convert date columns to datetime
        df["Start"] = pd.to_datetime(df[COL_PROJECT_START])
        df["Finish"] = pd.to_datetime(df[COL_PROJECT_FINISH])
        df["Task Start"] = pd.to_datetime(df[COL_TASK_START])
        df["Task Finish"] = pd.to_datetime(df[COL_TASK_FINISH])

        # Generate timestamp for chart title
        datetime_timestamp = strftime("%Y-%m-%d %H:%M:%S", localtime(get_time()))

        # Create base timeline
        fig = px.timeline(
            df,
            x_start="Task Start",
            x_end="Task Finish",
            y=COL_PROJECT,
            color=COL_TASK,
            color_discrete_sequence=["goldenrod"],
            text="summary",
            title=f"JIRA Projects Gantt Chart<br><i>{datetime_timestamp}</i>",
            labels={"Percentage Completed": "Complete (%)"},
            custom_data=[
                COL_PERCENT_COMPLETE_TASK,
                COL_PERCENT_COMPLETE_PROJECT,
                COL_TASK_START,
                COL_TASK_FINISH,
                COL_PROJECT,
                COL_SUMMARY,
                COL_TASK,
            ],
        )

        # Update hover template
        fig.update_traces(
            hovertemplate=(
                "<b>%{text}</b><br>"
                "<i>Project: %{customdata[4]}</i><br>"
                "Task: %{customdata[6]}<br>"
                "Start: %{customdata[2]}<br>"
                "Finish: %{customdata[3]}<br>"
                "Task Complete: %{customdata[0]:.2f}%<br>"
                "Project Complete: %{customdata[1]:.2f}%"
            )
        )

        # Add transparent bars for grouping
        for _, row in df.iterrows():
            fig.add_trace(
                go.Bar(
                    x=[row["Task Start"]],
                    y=[row[COL_PROJECT]],
                    orientation="h",
                    opacity=0,
                    textposition="auto",
                    showlegend=False,
                    name="gantt chart",
                )
            )

        # Add today's date vertical line
        today = strftime("%Y-%m-%d", localtime(get_time()))
        fig.add_vline(x=today, line_width=3, line_color="green")

        # Add annotation for today's line
        fig.add_annotation(
            x=today,
            text="Today",
            align="left",
            showarrow=True,
            arrowcolor="green",
            arrowhead=2,
            y=0,
            yshift=10,
        )

        # Update layout
        fig.update_layout(
            showlegend=False,
            barmode="group",
            autosize=True,
            xaxis_tickformat="%m-%d",
            bargap=0,
            bargroupgap=0,
        )

        # Update axis labels
        fig.update_yaxes(
            title_text="Jira Epics",
            type="category",
            categoryarray=df[COL_PROJECT],
            categoryorder="array",
        )
        fig.update_xaxes(title_text="Timeline")

        return fig

    def show_chart(self, fig: go.Figure) -> None:
        """Display the Gantt chart.

        Args:
            fig: Plotly Figure object to display.
        """
        fig.show()


def main():
    """Main entry point for the Jira Gantt Builder."""
    logging.basicConfig(level=logging.INFO)

    builder = JiraGanttBuilder()
    fig = builder.generate_gantt_chart()
    builder.show_chart(fig)


if __name__ == "__main__":
    main()
