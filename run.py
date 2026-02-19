#!/usr/bin/env python3
"""Entry point for SocialChain application."""
from socialchain.api.app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
