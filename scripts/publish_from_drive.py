#!/usr/bin/env python3
"""Publish AFENET comms dashboards from Google Drive into this repository.

This runs inside GitHub Actions, not in the Cowork sandbox. The daily Cowork run
uploads AFENET_Social_Media_Dashboard_YYYY-MM-DD.html to a Google Drive folder;
this script pulls any dashboard that is not already in the repo, points
index.html at the newest one, rebuilds archive.html from the files actually in
the repo, keeps CNAME, and commits. Nothing outside the repo is ever written and
there is no force-push.

usage:
  publish_from_drive.py --repo .                    # pull from Drive and commit
  publish_from_drive.py --repo . --local-dir DIR    # use local files (testing)
  publish_from_drive.py --repo . --local-dir DIR --dry-run   # stage only

environment (Drive mode):
  GDRIVE_SA_KEY     service-account JSON key (the whole document, as a string)
  GDRIVE_FOLDER_ID  id of the Drive folder the daily run uploads to

Guards, all of which abort before anything is committed:
  * a dashboard missing the login gate is refused;
  * a publish set smaller than what is already in the repo is refused;
  * only files named AFENET_Social_Media_Dashboard_YYYY-MM-DD.html are touched.
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

PAT = re.compile(r"^AFENET_Social_Media_Dashboard_(\d{4}-\d{2}-\d{2})\.html$")
GATE_MARKERS = ('id="gate"', "afenet_auth", "gateForm")
MAX_BYTES = 5 * 1024 * 1024  # a dashboard is ~50 KB; anything near this is wrong


def log(msg):
    print(msg, flush=True)


def run(repo, *cmd):
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed: {r.stderr.strip()[:500]}")
    return r.stdout.strip()


# ---------------------------------------------------------------- sources


def from_local(local_dir):
    """Candidate dashboards from a local directory (used by tests)."""
    out = {}
    for name in sorted(os.listdir(local_dir)):
        if PAT.match(name):
            with open(os.path.join(local_dir, name), encoding="utf-8") as f:
                out[name] = f.read()
    return out


def from_drive():
    """Candidate dashboards from the configured Drive folder."""
    import json

    from google.oauth2 import service_account          # type: ignore
    from googleapiclient.discovery import build        # type: ignore
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore
    import io

    raw = os.environ.get("GDRIVE_SA_KEY", "").strip()
    folder = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
    if not raw or not folder:
        sys.exit("GDRIVE_SA_KEY and GDRIVE_FOLDER_ID must both be set.")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    files, page = [], None
    while True:
        resp = (
            svc.files()
            .list(
                q=(
                    f"'{folder}' in parents and trashed = false "
                    "and mimeType != 'application/vnd.google-apps.folder'"
                ),
                fields="nextPageToken, files(id, name, size, mimeType)",
                pageSize=200,
                pageToken=page,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files.extend(resp.get("files", []))
        page = resp.get("nextPageToken")
        if not page:
            break

    out = {}
    for f in files:
        if not PAT.match(f["name"]):
            continue
        if f["mimeType"].startswith("application/vnd.google-apps"):
            log(f"  ! {f['name']} is a converted Google file, not an HTML upload — skipped. "
                "The daily run must upload it with disableConversionToGoogleType: true.")
            continue
        if int(f.get("size") or 0) > MAX_BYTES:
            log(f"  ! {f['name']} is {f['size']} bytes, above the {MAX_BYTES} limit — skipped.")
            continue
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=f["id"]))
        done = False
        while not done:
            _, done = dl.next_chunk()
        out[f["name"]] = buf.getvalue().decode("utf-8")
    return out


# ---------------------------------------------------------------- archive page
# Markup kept identical to publish_cloud.py so the archive does not churn.


def archive_html(names):
    rows = ""
    for n in sorted(names, reverse=True):
        d = PAT.match(n).group(1)
        disp = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %-d %B %Y")
        rows += f"""
        <tr>
          <td><a href="{n}">{disp}</a></td>
          <td>{d}</td>
          <td><a href="{n}" target="_blank">Open ↗</a></td>
        </tr>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AFENET Comms Dashboard Archive</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f8f9fb; color: #111827; margin: 0; padding: 40px 24px; }}
  .wrap {{ max-width: 700px; margin: 0 auto; }}
  h1 {{ font-size: 22px; font-weight: 800; margin-bottom: 4px; }}
  p {{ font-size: 13px; color: #6b7280; margin-bottom: 28px; }}
  .btn {{ display: inline-block; background: #059669; color: white; padding: 10px 20px;
          border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; margin-bottom: 28px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th {{ background: #f1f3f7; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
        color: #6b7280; padding: 10px 16px; text-align: left; }}
  td {{ padding: 12px 16px; font-size: 13px; border-top: 1px solid #f1f3f7; }}
  td:first-child {{ font-weight: 600; }}
  a {{ color: #059669; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ font-size: 11px; color: #9ca3af; margin-top: 24px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>AFENET Comms Intelligence — Archive</h1>
  <p>Daily automated dashboard · African Field Epidemiology Network</p>
  <a class="btn" href="index.html">← Today's Dashboard</a>
  <table>
    <thead><tr><th>Date</th><th>File</th><th>Link</th></tr></thead>
    <tbody>{rows}
    </tbody>
  </table>
  <div class="footer">Generated automatically · afenet.net · Access restricted</div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------- publish


def publish(repo, candidates, dry_run=False):
    before = {f for f in os.listdir(repo) if PAT.match(f)}

    new = {}
    for name, html in candidates.items():
        missing = [k for k in GATE_MARKERS if k not in html]
        if missing:
            sys.exit(f"Refusing to publish: {name} has no login gate ({missing}).")
        path = os.path.join(repo, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == html:
                    continue  # already published, unchanged
        new[name] = html

    if not new:
        log("Nothing new in Drive; the site is already current.")
        return False

    for name, html in sorted(new.items()):
        with open(os.path.join(repo, name), "w", encoding="utf-8") as f:
            f.write(html)
        log(f"  + {name} ({len(html)} bytes)")

    published = sorted((f for f in os.listdir(repo) if PAT.match(f)),
                       key=lambda f: PAT.match(f).group(1))
    if len(published) < len(before):
        sys.exit("Refusing to publish: fewer dashboards than are already in the repo.")

    newest = published[-1]
    with open(os.path.join(repo, newest), encoding="utf-8") as src, \
         open(os.path.join(repo, "index.html"), "w", encoding="utf-8") as dst:
        dst.write(src.read())
    with open(os.path.join(repo, "archive.html"), "w", encoding="utf-8") as f:
        f.write(archive_html(published))
    with open(os.path.join(repo, "CNAME"), "w") as f:
        f.write("comms.afenet.org\n")

    log(f"Staged {len(new)} new dashboard(s); index.html -> {newest}; "
        f"archive: {len(published)} entries")

    if dry_run:
        log("Dry run: nothing committed.")
        return True

    run(repo, "git", "config", "user.email", "comms@afenet.net")
    run(repo, "git", "config", "user.name", "AFENET Comms Bot")
    run(repo, "git", "add", "-A")
    if not run(repo, "git", "status", "--porcelain"):
        log("No changes to commit.")
        return False
    dates = ", ".join(sorted(PAT.match(n).group(1) for n in new))
    run(repo, "git", "commit", "-q", "-m", f"Dashboard refresh {dates}")
    run(repo, "git", "push", "origin", "HEAD:main")
    log(f"Published: https://comms.afenet.org/  ({len(published)} dashboards in archive)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--local-dir", help="read dashboards from here instead of Drive")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    candidates = from_local(a.local_dir) if a.local_dir else from_drive()
    log(f"Found {len(candidates)} candidate dashboard(s) in "
        f"{'local dir' if a.local_dir else 'Drive'}.")
    publish(os.path.abspath(a.repo), candidates, dry_run=a.dry_run)


if __name__ == "__main__":
    main()
