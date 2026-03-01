#!/usr/bin/env python3
"""
Fetch EC2 and RDS instance info across accounts and regions.
Store results in tab-delimited CSV files sorted by launch/create time (descending).

Requirements:
    pip3 install boto3 botocore

    Make sure your ~/.aws/credentials file contains current AWS credentials.
"""

import csv
import time
from operator import itemgetter
from typing import Any

import boto3
from botocore.exceptions import ClientError

AWS_PROFILES = ['ankr']
REGIONS = ['us-east-2']


def get_ec2_instances(profile: str, region: str) -> list[dict[str, Any]]:
    """Fetch EC2 instances for a given profile and region."""
    try:
        session = boto3.Session(profile_name=profile)
        ec2_client = session.client('ec2', region_name=region)
        response = ec2_client.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
        )

        rows = []
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                row = dict(instance)
                row['profile'] = profile
                row['region'] = region
                rows.append(row)

        if rows:
            return sorted(rows, key=itemgetter('LaunchTime'), reverse=True)
        return []
    except ClientError as e:
        print(f"EC2 Error in region {region} for profile {profile}: {e}")
        return []


def get_rds_instances(profile: str, region: str) -> list[dict[str, Any]]:
    """Fetch RDS instances for a given profile and region."""
    try:
        session = boto3.Session(profile_name=profile)
        rds_client = session.client('rds', region_name=region)
        response = rds_client.describe_db_instances()

        rows = []
        for db_instance in response.get('DBInstances', []):
            row = dict(db_instance)
            row['profile'] = profile
            row['region'] = region
            rows.append(row)

        if rows:
            return sorted(rows, key=itemgetter('InstanceCreateTime'), reverse=True)
        return []
    except ClientError as e:
        print(f"RDS Error in region {region} for profile {profile}: {e}")
        return []


def write_csv(filename: str, instances: list[dict[str, Any]], resource_type: str) -> None:
    """Write instances to a tab-delimited CSV file."""
    if not instances:
        return

    with open(filename, 'w', newline='') as csvfile:
        fieldnames = instances[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        for instance in instances:
            writer.writerow(instance)
    print(f"{resource_type.upper()} instances written to {filename}")


def main():
    for resource_type in ['ec2', 'rds']:
        all_instances: list[dict[str, Any]] = []
        csv_filename = f"{int(time.time())}_{resource_type}_instances.csv"

        for profile in AWS_PROFILES:
            for region in REGIONS:
                if resource_type == 'ec2':
                    instances = get_ec2_instances(profile, region)
                else:
                    instances = get_rds_instances(profile, region)

                if instances:
                    all_instances.extend(instances)
                else:
                    print(f"{region}: No {resource_type.upper()} instances found for profile {profile}")

        if all_instances:
            write_csv(csv_filename, all_instances, resource_type)
        else:
            print(f"No {resource_type.upper()} instances found across all profiles/regions")


if __name__ == "__main__":
    main()
