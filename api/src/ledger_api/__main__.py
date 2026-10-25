"""``ledger-api``: serve the API with uvicorn (CL_API_HOST, CL_API_PORT, CL_API_ROOT_PATH)."""

import os

import uvicorn

from ledger_api.app import create_app


def main() -> None:
    uvicorn.run(
        create_app(),
        host=os.environ.get("CL_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("CL_API_PORT", "8000")),
        # Behind Caddy the API is served under /api; the docs page needs to know that prefix.
        root_path=os.environ.get("CL_API_ROOT_PATH", ""),
        proxy_headers=True,
        server_header=False,
    )


if __name__ == "__main__":
    main()
