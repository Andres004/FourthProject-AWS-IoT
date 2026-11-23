"""Checks that no secret is published in the repository (test B03).

Looks for private keys, certificates, AWS access keys, AWS account numbers
inside ARNs, real IoT endpoints and WiFi passwords, both in the files that
git tracks now and in every commit of the history. It also checks that the
secret files are ignored by git.

Usage, from the project root:
    python tools/check_secrets.py [-o OUTPUT.txt]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----\s*\n\s*[A-Za-z0-9+/]{20}"),
    "certificate": re.compile(r"-----BEGIN CERTIFICATE-----\s*\n\s*MII"),
    "AWS access key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS account in ARN": re.compile(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:"),
    "IoT endpoint": re.compile(r"\b(?!x{8})[a-z0-9]{14}-ats\.iot\.[a-z0-9-]+\.amazonaws\.com"),
    "WiFi password": re.compile(
        r'WIFI_PASSWORD\[\]\s*=\s*"(?!YOUR_WIFI_PASSWORD")[^"]+"'
    ),
}
BOARDS = ("vent", "lights")
MUST_BE_IGNORED = (
    "include/secrets.h",
    "include/secrets_vent.h",
    "include/secrets_lights.h",
    "certificados-vent/device-certificate.pem.crt",
    "certificados-lights/private.pem.key",
    "certs/device-certificate.pem.crt",
    "certificados/private.pem.key",
    "AmazonRootCA1.pem",
    "lambda/lambda_deployment.zip",
)


def git(*arguments):
    return subprocess.run(
        ("git", *arguments), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    ).stdout


def scan(text):
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output")
    arguments = parser.parse_args()
    lines, failures = [], 0

    tracked = git("ls-files").splitlines()
    found_now = []
    for path in tracked:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in scan(text):
            found_now.append(f"{path}: {name}")
    lines.append(f"Tracked files scanned: {len(tracked)}")
    lines.extend(f"  FOUND {item}" for item in found_now)
    lines.append(f"RNF6 secrets in tracked files: {len(found_now)} (0) -> "
                 f"{'PASS' if not found_now else 'FAIL'}")
    failures += bool(found_now)

    commits = git("rev-list", "--all").split()
    found_history = []
    for commit in commits:
        patch = git("show", "--format=", "-p", commit)
        for name in scan(patch):
            found_history.append(f"{commit[:7]}: {name}")
    lines.append(f"Commits scanned: {len(commits)}")
    lines.extend(f"  FOUND {item}" for item in found_history)
    lines.append(f"RNF6 secrets in git history: {len(found_history)} (0) -> "
                 f"{'PASS' if not found_history else 'FAIL'}")
    failures += bool(found_history)

    not_ignored = [
        path for path in MUST_BE_IGNORED
        if not git("check-ignore", path).strip()
    ]
    lines.append(f"Secret paths checked against .gitignore: {len(MUST_BE_IGNORED)}")
    lines.extend(f"  NOT IGNORED {path}" for path in not_ignored)
    lines.append(f"RNF6 secret files ignored by git: "
                 f"{len(MUST_BE_IGNORED) - len(not_ignored)}/{len(MUST_BE_IGNORED)}"
                 f" -> {'PASS' if not not_ignored else 'FAIL'}")
    failures += bool(not_ignored)

    for board in BOARDS:
        template = f"include/secrets_{board}.example.h"
        template_ok = template in tracked
        lines.append(f"RNF6 template {template} published: "
                     f"{'yes' if template_ok else 'no'} -> "
                     f"{'PASS' if template_ok else 'FAIL'}")
        failures += not template_ok

    # Positive control: the real (ignored) secrets file must be detected,
    # which shows that a PASS above is not a blind scanner. Only the kinds
    # of secret are printed, never their values.
    expected = {"private key", "certificate", "IoT endpoint", "WiFi password"}
    for board in BOARDS:
        real = Path(f"include/secrets_{board}.h")
        if not real.exists():
            continue
        kinds = scan(real.read_text(encoding="utf-8", errors="replace"))
        control_ok = expected <= set(kinds)
        lines.append(f"Control: {real.as_posix()} (not published) detected as "
                     f"{kinds} -> {'PASS' if control_ok else 'FAIL'}")
        failures += not control_ok

    output = "\n".join(lines) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    print(output, end="")
    if arguments.output:
        Path(arguments.output).write_text(output, encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
