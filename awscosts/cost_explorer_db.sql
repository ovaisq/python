CREATE TABLE IF NOT EXISTS costs (
	timestamp bigint NOT NULL,
	account_id text NOT NULL,
	time_period DATE NOT NULL,
	aws_service text NOT NULL,
    cost_type text NOT NULL,
	usage_type text  NOT NULL,
    amount decimal not null  --should be type money, but not supported by RPostgres
);