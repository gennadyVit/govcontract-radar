import os
import base64
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def load_private_key():
    from keyvault import get_secret
    key_env = get_secret("SNOWFLAKE-PRIVATE-KEY", "SNOWFLAKE_PRIVATE_KEY")
    if not key_env:
        if os.path.exists("rsa_key.p8"):
            with open("rsa_key.p8", "rb") as f:
                return load_pem_private_key(f.read(), password=None)
        return None
    # SNOWFLAKE_PRIVATE_KEY is a base64-encoded PEM file
    pem_bytes = base64.b64decode(key_env.strip())
    return load_pem_private_key(pem_bytes, password=None)


def get_connection():
    from keyvault import get_secret
    private_key = load_private_key()
    account = get_secret("SNOWFLAKE-ACCOUNT", "SNOWFLAKE_ACCOUNT")
    user = get_secret("SNOWFLAKE-USER", "SNOWFLAKE_USER")
    warehouse = get_secret("SNOWFLAKE-WAREHOUSE", "SNOWFLAKE_WAREHOUSE")
    database = get_secret("SNOWFLAKE-DATABASE", "SNOWFLAKE_DATABASE")
    schema = get_secret("SNOWFLAKE-SCHEMA", "SNOWFLAKE_SCHEMA")

    if private_key:
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return snowflake.connector.connect(
            account=account,
            user=user,
            private_key=private_key_der,
            warehouse=warehouse,
            database=database,
            schema=schema,
        )
    password = get_secret("SNOWFLAKE-PASSWORD", "SNOWFLAKE_PASSWORD")
    return snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema=schema,
    )
