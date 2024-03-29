### A gantt chart using EPICS and Projects in JIRA Cloud
***Originally I wanted to use HIGHCHART lib to build this but due to this [bug](https://github.com/highcharts-for-python/highcharts-gantt/issues/46) I could not***

For several years, particularly since assuming leadership roles across multiple Engineering functions, I have aspired to create a streamlined dashboard offering a comprehensive overview, akin to a 50,000-foot view, of timelines encompassing ALL EPICS/Issues across key projects within JIRA. In the early days of computing, MS Project was the go-to tool. In the SaaS era, options range from a manual approach, demanding proficiency in JQL and chart creation in spreadsheets, to the use of costly third-party tools like Asana, Monday, or ClickUp. Somewhere in between, JIRA introduced the 'Roadmap' feature (now called Plan) within individual Jira projects.

However, the JIRA Roadmap feature came with a caveat—it was confined to a single project. To extend roadmaps across multiple Jira projects, an upgrade to the premium version was necessary. The cost of JIRA Premium, depending on the license type and user tier, varied from a minimum of around 2000 USD to tens of thousands of dollars. In situations where a single user or a small team sought a high-level view of project timelines, the JIRA Premium option proved cost-prohibitive, and the manual approach was both time and resource-intensive.

Having previously delved into Atlassian product APIs, I always aspired to construct a dashboard without the need for manual query execution, data filtering, spreadsheet updates, or chart creation. Recently, my foray into data analytics led me to develop a basic yet effective daily spend bar chart using AWS-CLI, R, PostgreSQL, and Python. Building on my past familiarity with JIRA APIs, I subsequently crafted a straightforward Project Roadmap/Gantt chart using Pandas, HighCharts, and Python.

### Examples
* Main Screenshot ![Gantt Chart Screenshot](jira_gantt_highchart_main.png)
