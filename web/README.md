# JWT Lab

A local web interface for presenting the research, inspecting synthetic JWTs, running
the existing evaluation harness, and exploring measured results. It uses Python's
standard-library HTTP server and plain HTML, CSS, and JavaScript; no frontend build
or additional web dependencies are needed.

## Start

On Windows, double-click **`web/Start JWT Lab.cmd`** to start the server and open the
application in your browser. Keep its terminal window open while using the application.

From the repository root, use the Python environment containing the generator dependencies:

```powershell
.\.venv\Scripts\python.exe web/server.py
```

On macOS/Linux:

```bash
.venv/bin/python web/server.py
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if the default port is occupied.
Stop the server with Ctrl+C after any active evaluation finishes.

If setting up a new environment, follow the main README's prerequisites, then install
`generator/requirements.txt`. Native evaluations additionally need the selected targets'
dependencies (Python target requirements, `npm ci` for each Node target, .NET SDKs 8/10).
Alternatively use Docker Compose with a running Docker engine. Merely having a runtime
installed does not mean a target is ready to run.

## Screens

- **Overview:** the research questions, experiment design, target list, and shared policy.
  Presentation mode hides the sidebar and widens the content; the top button exits it.
- **Token studio:** search/filter cases, inspect decoded headers and payloads, view
  differences from the control, copy an encoded token, or generate and verify a fresh set.
  A decoded token is not itself a signature-verification result.
- **Evaluation:** select targets and native/Docker launch mode. Both configurations run
  through the existing harness, including its control gate and fresh-token verification.
  Progress updates after a target configuration finishes. Pending is not a success result.
- **Results explorer:** choose a saved run; compare false-accept rates; filter by target,
  category, configuration, or outcome; inspect individual HTTP responses; export the
  original raw CSV. Presentation mode works on every screen.

## Data and execution

`components.json`, `testmatrix.json`, and `policy.json` remain the sources of truth.
The UI reads historical `results/**/raw.csv` files, excluding mock results. Legacy
directory-style target names are normalized for display. Missing measurements are
shown as dashes; they are never filled with simulated results. Historical result sets
may cover fewer targets or cases than the current matrix. Dates and source paths are
displayed alongside the results.

HTTP 200 means accepted, 401/403 means rejected, and every other status or missing
response is an error. Errors are excluded from false-accept denominators. Matches
and mismatches use each recorded row's expected outcome. The displayed percentages
are rounded; raw data is preserved in CSV. Header cards and comparison charts cover
the whole selected run; table filters apply only to the matrix/request table.

New runs are saved to `results/web/<UTC timestamp>/`, ignored by Git. Existing evidence
is not overwritten. `harness/metrics.py` creates the standard metric files there too.
The runner uses the server's Python environment and, when available, the repository's
`.tools/dotnet` SDK for the .NET 10 target only. A run saves its resolved component
configuration beside its output. These local files may contain local SDK paths.

Only one UI generation/evaluation operation can run at a time because the existing
generator shares `tokens/`. Do not run separate CLI evaluations concurrently. Keys are
created only when absent; existing key pairs are not rotated. Generation overwrites
the generated token set, as the existing generator normally does.

The server binds to loopback, validates Host and Origin, requires a session token for
mutations, and serves only three static files plus specific API routes. It never serves
the repository directory or private keys. This is a local research tool, not a deployed
multi-user service. Browser refreshes reconnect to the active job. Job progress is held
in memory; completed result files persist across server restarts. Do not terminate the
server while a harness subprocess is running.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s web/tests -v
node --check web/static/app.js
```

The API tests use a temporary repository and mock subprocess execution. The native
cleanup regression launches a small real HTTP server twice to verify that a Python
virtualenv target releases its port between configurations. A real evaluation through
the browser or API checks installed target toolchains separately.
