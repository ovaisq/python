#!/usr/bin/env python3
"""
Script to list EC2 instances across all regions in an AWS account.
Outputs instance LaunchTime, InstanceType, KeyName, and InstanceId.
"""

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def get_regions(profile: str) -> list[str]:
    """Get all available EC2 regions."""
    try:
        session = boto3.Session(profile_name=profile)
        ec2_client = session.client('ec2', region_name='us-east-2')
        response = ec2_client.describe_regions()
        return [region['RegionName'] for region in response['Regions']]
    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching regions: {e}")
        return []


def get_instances_in_region(profile: str, region: str) -> list[dict]:
    """Fetch EC2 instances in a specific region."""
    try:
        session = boto3.Session(profile_name=profile)
        ec2_client = session.client('ec2', region_name=region)
        response = ec2_client.describe_instances()

        instances = []
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                instances.append({
                    'LaunchTime': instance.get('LaunchTime'),
                    'InstanceType': instance.get('InstanceType'),
                    'KeyName': instance.get('KeyName'),
                    'InstanceId': instance.get('InstanceId'),
                })
        return instances
    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching instances in {region}: {e}")
        return []


def main():
    profile = 'ankr'

    regions = get_regions(profile)
    if not regions:
        print("No regions found or unable to connect to AWS.")
        return

    all_instances = []
    for region in regions:
        instances = get_instances_in_region(profile, region)
        for inst in instances:
            inst['Region'] = region
            all_instances.append(inst)

    if all_instances:
        for inst in all_instances:
            print(f"{inst['LaunchTime']} | {inst['InstanceType']} | {inst['KeyName']} | {inst['InstanceId']} | {inst['Region']}")
    else:
        print("No instances found.")


if __name__ == '__main__':
    main()
