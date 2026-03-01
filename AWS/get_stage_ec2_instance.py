#!/usr/bin/env python3
import boto3

def list_ec2_instances_by_name_prefix(region_name='us-east-2', profile_name='moo', name_prefix='-'):
    """
    Lists EC2 instances in a specific AWS region that have a Name tag starting with a given prefix.

    Args:
        region_name (str): AWS region to search in. Default is 'us-east-2'.
        profile_name (str): AWS CLI profile name to use. Default is 'stage'.
        name_prefix (str): Prefix of the Name tag to filter instances. Default is '-'.

    Returns:
        list: A list of dictionaries containing instance details (Name, InstanceId, InstanceType, State, Public/Private IPs).
    """
    session = boto3.Session(profile_name=profile_name, region_name=region_name)
    ec2 = session.client('ec2')

    try:
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': 'tag:Name',
                    'Values': [f"{name_prefix}*"]
                }
            ]
        )

        instances = []

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), None)
                instance_info = {
                    'Name': name,
                    'InstanceId': instance.get('InstanceId'),
                    'InstanceType': instance.get('InstanceType'),
                    'State': instance.get('State', {}).get('Name'),
                    'PublicIpAddress': instance.get('PublicIpAddress'),
                    'PrivateIpAddress': instance.get('PrivateIpAddress'),
                }
                instances.append(instance_info)

        return instances

    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    """
    Main execution block:
    - Calls the EC2 instance listing function using the 'stage' profile and 'us-east-2' region.
    - Prints out the matching instance details to the console.
    """
    instances = list_ec2_instances_by_name_prefix()

    if instances:
        print(f"\nFound {len(instances)} EC2 instance(s) matching 'STAGE-CoreServer-*':\n")
        for i, inst in enumerate(instances, start=1):
            print(f"Instance {i}:")
            for key, val in inst.items():
                print(f"  {key}: {val}")
            print("-" * 40)
    else:
        print("No matching instances found or error occurred.")

