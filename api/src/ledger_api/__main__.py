"""``ledger-api``: serve the API with uvicorn (CL_API_HOST, CL_API_PORT)."""

import os

import uvicorn

from ledger_api.app import create_app


def main() -> None:
    uvicorn.run(
        create_app(),
        host=os.environ.get("CL_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("CL_API_PORT", "8000")),
        proxy_headers=True,
        server_header=False,
    )


if __name__ == "__main__":
    main()
