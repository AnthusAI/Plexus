from aws_cdk import core
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_glue as glue

class DataLakeStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create an S3 bucket for storing data
        bucket = s3.Bucket(self, "DataLakeBucket",
                           versioned=True,
                           removal_policy=core.RemovalPolicy.DESTROY)

        # Create a Glue database
        database = glue.Database(self, "GlueDatabase",
                                 database_name="datalake_database")

        # Create Glue Crawlers
        crawler = glue.CfnCrawler(self, "DataLakeCrawler",
                                  role="arn:aws:iam::account-id:role/service-role/AWSGlueServiceRole",
                                  database_name=database.database_name,
                                  targets={
                                      "s3Targets": [
                                          {"path": f"s3://{bucket.bucket_name}/"}
                                      ]
                                  })

        # Output the S3 bucket name
        core.CfnOutput(self, "BucketName",
                       value=bucket.bucket_name,
                       description="The name of the S3 bucket used for the data lake.")

app = core.App()
DataLakeStack(app, "DataLakeStack")
app.synth()
