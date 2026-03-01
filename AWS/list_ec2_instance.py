#!/usr/bin/env python3

"""
Script to describe EC2 instances using AWS, filtered by tags.

The script fetches instance details such as:
- Name (from instance tags)
- Private IP address
- Launch time
- Instance state/status

It then prints the results in a formatted table.

Requirements:
- AWS CLI configured with profiles
- boto3 installed (`pip install boto3`)
"""

import argparse
import sys
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def create_ec2_client(profile: str) -> boto3.client:
    """Create an EC2 client using the specified AWS profile."""
    try:
        session = boto3.Session(profile_name=profile)
        return session.client('ec2')
    except BotoCoreError as e:
        print(f"Error creating session with profile '{profile}': {e}", file=sys.stderr)
        sys.exit(1)


def fetch_instances(ec2_client: boto3.client, tag_filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch EC2 instances matching the specified tag filters."""
    try:
        response = ec2_client.describe_instances(Filters=tag_filters)
        instances = []
        for reservation in response.get('Reservations', []):
            instances.extend(reservation.get('Instances', []))
        return instances
    except ClientError as e:
        print(f"Error fetching instances: {e}", file=sys.stderr)
        sys.exit(1)


def parse_instance_info(instance: dict[str, Any]) -> dict[str, str]:
    """Extract relevant information from an EC2 instance."""
    tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
    launch_time = instance.get('LaunchTime')

    return {
        'name': tags.get('Name', 'N/A'),
        'private_ip': instance.get('PrivateIpAddress', 'N/A'),
        'launch_time': launch_time.strftime('%Y-%m-%d %H:%M:%S') if launch_time else 'N/A',
        'status': instance.get('State', {}).get('Name', 'N/A'),
    }


def format_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    """Format a list of dictionaries as a table."""
    if not rows:
        return "No instances found."

    # Calculate column widths
    widths = {col: max(len(col), max((len(row.get(col, '')) for row in rows), default=0)) for col in columns}

    # Build header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)

    # Build rows
    data_rows = []
    for row in rows:
        data_row = " | ".join(str(row.get(col, 'N/A')).ljust(widths[col]) for col in columns)
        data_rows.append(data_row)

    return "\n".join([header, separator] + data_rows)


def main():
    parser = argparse.ArgumentParser(
        description='List EC2 instances filtered by tags'
    )
    parser.add_argument(
        '--profile', '-p',
        default='stage',
        help='AWS profile to use (default: stage)'
    )
    parser.add_argument(
        '--tag', '-t',
        action='append',
        nargs=2,
        metavar=('KEY', 'VALUE'),
        help='Filter by tag (can be specified multiple times)'
    )
    parser.add_argument(
        '--output', '-o',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    args = parser.parse_args()

    # Default tag filter if none specified
    if args.tag:
        tag_filters = [{'Name': f'tag:{key}', 'Values': [value]} for key, value in args.tag]
    else:
        tag_filters = [{'Name': 'tag:Name', 'Values': ['STAGE-CoreServer-AS']}]

    # Fetch and display instances
    ec2_client = create_ec2_client(args.profile)
    instances = fetch_instances(ec2_client, tag_filters)

    if not instances:
        print("No instances found matching the specified filters.")
        return

    parsed_instances = [parse_instance_info(inst) for inst in instances]

    if args.output == 'json':
        import json
        print(json.dumps(parsed_instances, indent=2))
    else:
        columns = ['name', 'private_ip', 'launch_time', 'status']
        print(format_table(parsed_instances, columns))


if __name__ == '__main__':
    main()

