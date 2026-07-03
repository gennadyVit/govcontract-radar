import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization


def load_private_key():
    key_env = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    if key_env:
        key_pem = key_env.replace("\\n", "\n")
        return serialization.load_pem_private_key(key_pem.encode(), password=None)
    with open("rsa_key.p8", "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=load_private_key(),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )
