import hashlib
import hmac
import sys
from pathlib import Path


# Load settings from .env if present
def get_default_secret():
    try:
        # Check current directory and parent directory for .env
        paths_to_check = [
            Path(__file__).resolve().parent / ".env",
            Path(__file__).resolve().parent.parent / ".env",
            Path.cwd() / ".env",
        ]
        for env_path in paths_to_check:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("GATEWAY_CLAIM_SECRET="):
                            return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "change-me-in-production"


def compute_claim_code(serial_number: str, secret: str) -> str:
    return (
        hmac.new(
            secret.encode(),
            serial_number.strip().upper().encode(),
            hashlib.sha256,
        )
        .hexdigest()[:8]
        .upper()
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_claim_code.py <SERIAL_NUMBER> [CLAIM_SECRET]")
        print("Example: python generate_claim_code.py GW-TEST-001")
        sys.exit(1)

    serial = sys.argv[1].upper()
    claim_secret = sys.argv[2] if len(sys.argv) > 2 else get_default_secret()

    code = compute_claim_code(serial, claim_secret)
    print("==========================================")
    print("  Factory Claim Code Generator")
    print("==========================================")
    print(f"Serial Number:       {serial}")
    print(f"Claim Secret used:   {claim_secret}")
    print(f"Generated Claim Code: {code}")
    print("==========================================")
