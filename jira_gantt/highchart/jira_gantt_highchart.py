#!/usr/bin/env python3

from highcharts_gantt.chart import Chart
from highcharts_gantt.options.series.gantt import GanttSeries
from highcharts_core.options.exporting import Exporting
from highcharts_gantt.global_options.shared_options import SharedGanttOptions
import datetime

options_as_dict = {
    'chart': {
        'plotBackgroundColor': 'rgba(128,128,128,0.02)',
        'plotBorderColor': 'rgba(128,128,128,0.1)',
        'plotBorderWidth': 1
    },
    'plotOptions': {
        'series': {
            'borderRadius': '50%',
            'connectors': {
                'dashStyle': 'ShortDot',
                'lineWidth': 2,
                'radius': 5,
                'startMarker': {
                    'enabled': 'false'
                }
            },
            'groupPadding': 0,
            'dataLabels': [{
                'enabled': 'true',
                'align': 'left',
                'format': '{point.name}',
                'padding': 10,
                'style': {
                    'fontWeight': 'normal',
                    'textOutline': 'none'
                }
            }, {
                'enabled': 'true',
                'align': 'right',
                'format': '{#if point.completed}{(multiply point.completed.amount 100):.0f}%{/if}',
                'padding': 10,
                'style': {
                    'fontWeight': 'normal',
                    'textOutline': 'none',
                    'opacity': 0.6
                }
            }]
        }
    },
    'title': {
        'text': 'JIRA Gantt Chart',
        'align': 'left'
    },

    'xAxis': [{
        'min': datetime.date(2023, 12, 17),
        'max': datetime.date(2024, 4, 30),
    'currentDateIndicator': {
            'color': '#2caffe',
            'dashStyle': 'ShortDot',
            'width': 2,
            'label': {
                'format': ''
            }},
    'dateTimeLabelFormats': {
            'day': '%e<br><span style="opacity: 0.5; font-size: 0.7em">%a</span>'
        },
        'grid': {
            'borderWidth': 0
        },
        'gridLineWidth': 1,
        'custom': {
            'today':'',
            'weekendPlotBands': 'true'
        }}
    ],
    'yAxis': {
        'grid': {
            'borderWidth': 0
        },
        'gridLineWidth': 0,
        'labels': {
            'symbol': {
                'width': 8,
                'height': 6,
                'x': -4,
                'y': -2
            }
        },
        'staticScale': 30
    },
    'accessibility': {
        'point': {
            'descriptionFormatter': """function (point) {
                var completedValue = point.completed ?
                        point.completed.amount || point.completed : null,
                    completed = completedValue ?
                        ' Task completed ' + Math.round(completedValue * 1000) / 10 + '%.' :
                        '',
                                            dependency = point.dependency &&
                        point.series.chart.get(point.dependency).name,
                    dependsOn = dependency ? ' Depends on ' + dependency + '.' : '';;
                return Highcharts.format(
                    point.milestone ?
                        '{point.yCategory}. Milestone at {point.x:%Y-%m-%d}. Owner: {point.owner}.{dependsOn}' :
                        '{point.yCategory}.{completed} Start {point.x:%Y-%m-%d}, end {point.x2:%Y-%m-%d}. Owner: {point.owner}.{dependsOn}',
                    { point, completed, dependsOn }
                );
            }"""
        }
    },

    'lang': {
        'accessibility': {
            'axis': {
                'xAxisDescriptionPlural': 'The chart has a two-part X axis showing time in both week numbers and days.'
            }
        }
    },

    'series': [{
        'type': 'gantt',
        'name': 'Project 1',
        'data': [{'name': 'SCRUM-5',
                  'id' : 'scrum_5',
                  'owner': 'Janet Jackson',
                  'start':datetime.date(2023, 12, 18),
                  'end': datetime.date(2024, 3, 26)
        }, {
            'name': 'SCRUM-6 - Story: MVP Frontend',
            'id':'start_prototype',
            'parent':'scrum_5',
            'owner':'Janet Reno',
            'start': datetime.date(2024, 1, 1),
            'end': datetime.date(2024, 2, 5),
            'completed': 0.38
        },  {
            'name': 'SCRUM-3 - Story: MVP PWA',
            'id':'mvp_pwa',
            'parent':'scrum_5',
            'owner':'Danny Elfman',
            'start': datetime.date(2024, 1, 3),
            'end': datetime.date(2024, 2, 5),
            'completed': 0.29
            }]
    },
    ]
}

chart = Chart.from_options(options_as_dict, chart_kwargs = {'is_gantt_chart': True})
as_js_literal = chart.to_js_literal(filename = './foo.js')
chart.display()
