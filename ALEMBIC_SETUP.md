# How to Use and Install Alembic for FASTAPI

[read more](https://testdriven.io/blog/fastapi-sqlmodel/)
Installing Alembic...

```bash
pip install alembic
```

## Initialize Alembic for async PostgreSQL with SQLModel support

Initializing Alembic for async PostgreSQL...

```bash
alembic init -t async migrations
```

## Instructions for editing env.py

"Alembic initialized."

### Next steps

1. Open the generated *`migrations/env.py`* file.
2. Add your models' imports to *`env.py`*. For example:
`from your_project.models import YourModel`

3. Import SQLModel and set *`target_metadata`*. Add the following line in 'env.py':
`from sqlmodel import SQLModel`

4. Replace the existing *`target_metadata`* line with:
`target_metadata = SQLModel.metadata`

5. Open the generated `migrations/script.py.mako` file:

6. import the model driver file to your project. For example:
`import sqlmodel`

7. Open the generated `./alembic.ini` file.

6. Add the database driver you are working with:
`sqlalchemy.url = postgresql+asyncpg://username:password@localhost:5432/db_name`

Make sure to complete these steps before running an initial migration.

```bash
alembic revision --autogenerate -m "Migration Message"
alembic upgrade head
alembic stamp head # if the database is not uptodate
```


```bash
from src.utils.sui_json_rpc_apis import SUI
import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
mnemonic_phrase = "ozone proof crawl brief abuse minor flower invest save banana seat head goose eternal chunk ecology liquid gentle arrange erosion vital photo music beach"
future = loop.run_until_complete(SUI.paySui("0xaa8bea4226bda3a323a13f33157547c5847cbeca1384018bcfc7a4b18cb43b7c", "0x28768bb2c5ede1e7e99ba27301494ba75f933e3c83ce242f43d9dc1b9b455a30", "10", "10000", "0x21a571e5082bea828eeb8c07a940a0194181a0223cb3502d71f4b0f9d1003f26"))
transactionResponse = loop.run_until_complete(SUI.executeTransaction(future.txBytes, mnemonic_phrase))
```
