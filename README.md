# Good Luck Forwarding Systems Inc. Fleet Management System

A fleet management system with a semantic HTML5 interface, responsive CSS3
styling, and a vanilla JavaScript single-page frontend. Flask provides a JSON
API and securely connects to Supabase; the Supabase service key never goes into
browser code.

It tracks vehicles, drivers, assignments, maintenance, fuel purchases, tire service
history, and trips.
The web interface supports light and dark themes, follows the device preference
by default, and remembers the selected theme in the browser.

## Supabase setup

1. Create a Supabase project.
2. In the Supabase SQL Editor, run [`supabase_schema.sql`](./supabase_schema.sql).
3. Run [`supabase_dispatcher_ownership_migration.sql`](./supabase_dispatcher_ownership_migration.sql)
   to add record ownership fields.
4. Run [`supabase_fuel_allocation_migration.sql`](./supabase_fuel_allocation_migration.sql)
   to add the `fuel_logs.trip_id` relationship and fuel allocation fields. This
   step is required even if `fuel_logs` already exists: `CREATE TABLE IF NOT EXISTS`
   does not add missing columns to an existing table. If the app reports that
   `fuel_logs.trip_id` does not exist, run this migration in the SQL Editor and
   refresh the app.
5. Copy `.env.example` to `.env`.
6. Fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and
   `SUPABASE_SERVICE_ROLE_KEY` from the project's API settings. The anon or
   publishable key is used for password authentication; the service-role/secret
   key is used only by the server for fleet data access. Never put the
   service-role key in browser code or commit either secret to source control.
7. Replace `SECRET_KEY` with a long random value (for example, generate one with
   `python -c "import secrets; print(secrets.token_hex(32))"`).
8. In Supabase **Authentication → Users**, invite or create each authorized
   user's email/password account. Public sign-up is not enabled by this app.

## Dispatcher roles and data isolation

Run [`supabase_dispatcher_ownership_migration.sql`](./supabase_dispatcher_ownership_migration.sql)
in the Supabase SQL Editor before using dispatcher accounts if you have not
already run it during initial setup. It adds immutable
`created_by` ownership fields to trips, fuel logs, and maintenance records.
It also adds private image storage for trip load manifests and fuel invoices.
If you ran an earlier version of this migration, run the updated file again;
the changes are safe to reapply. The migration also advances the trip, fuel,
and maintenance ID counters past existing records, which prevents duplicate
IDs after CSV imports. Existing records remain unowned and are visible only to
administrators.

For location-based dispatch, run
[`supabase_dispatch_origin_access_migration.sql`](./supabase_dispatch_origin_access_migration.sql)
after [`supabase_location_dispatch_migration.sql`](./supabase_location_dispatch_migration.sql).
Reapply the origin-access migration to existing projects to update the paginated
dispatch listing; it now computes the eligible movements once per page request.

Run [`supabase_fuel_allocation_migration.sql`](./supabase_fuel_allocation_migration.sql)
after the base trips/routes schema and dispatcher ownership migration. It adds
the `fuel_logs.trip_id` foreign key and allocation fields; rerun it for existing
projects because an earlier `CREATE TABLE IF NOT EXISTS` does not update a
pre-existing `fuel_logs` table.

Run [`supabase_notifications_migration.sql`](./supabase_notifications_migration.sql)
in the Supabase SQL Editor to enable Admin notifications. Each successful
dispatcher-created trip, fuel log, maintenance log, or first load-manifest upload
is recorded for each administrator. Admins can filter, open, and mark their
notifications as read. The notification center refreshes unread counts every
12 seconds while the app is open.

Run [`supabase_dispatch_completed_trip_deletion_migration.sql`](./supabase_dispatch_completed_trip_deletion_migration.sql)
after the location-dispatch, payroll, and revenue migrations to allow
administrators to delete completed dispatch trips.

## Directional truck route rates

After the base schema, trips, existing truck-rate, and payroll migrations are installed,
run [`supabase_route_trip_rate_migration.sql`](./supabase_route_trip_rate_migration.sql)
in the Supabase SQL Editor. It adds the 12 directional route records and their
capacity-specific rates, including `NULL` for the two unsupplied 36-pallet
DAV1/DAV2 rates. Reapplying it updates the master records rather than inserting
duplicates. It stores an immutable hauling-rate snapshot on each trip and flags
historical trips for review instead of assigning rates from today's configuration.

Then run [`supabase_truck_trailer_migration.sql`](./supabase_truck_trailer_migration.sql).
The existing `vehicles` table remains the truck registry so its IDs and existing
references are preserved. Trailers are stored separately and carry pallet
capacity. The migration backfills each historical trip's truck ID from its
existing vehicle ID, but cannot determine which trailer hauled a historical
trip; those trailer assignments remain NULL and flagged for manual review.
Any former capacity values on trucks are copied to
`legacy_vehicle_capacity_review` for review, never automatically assigned to
trailers. Earlier hauling-rate snapshots that may have used truck capacity are
preserved in `legacy_trip_rate_review`, cleared from the active trip-rate fields,
and marked unresolved until reviewed against an actual trailer.

## Tire Monitoring Sheet

After the truck/trailer migration, run
[`supabase_tire_monitoring_migration.sql`](./supabase_tire_monitoring_migration.sql)
in the Supabase SQL Editor. It adds the tire record and immutable audit-history
tables, truck/trailer foreign keys, lifecycle checks, indexes, RLS policies, and
the server-side summary, lifespan, replacement, and removal functions. The
migration is additive and does not delete existing fleet records.

Administrators can view all tire records, add and edit details, replace installed
tires, and record removals. Dispatchers can see and add only tire records they
created; they cannot edit, replace, or remove submitted records. Tire records
cannot be deleted through the application. A replacement keeps the old record,
sets its replacement date and reason, and atomically registers the new tire on
the same truck or trailer. The new record links back to the tire it replaces,
and both records remain accessible from their details and audit history.
Database constraints and RLS complement the Flask authorization checks.

Life Span (%) is entered and maintained directly as the estimated percentage
remaining; no lifespan-days field or elapsed-days calculation is used. New tires
default to 100%, and the input is validated between 0% and 100%. The warning
threshold defaults to 20% remaining and can be configured server-side with
`TIRE_LIFESPAN_WARNING_PERCENT`. Update the percentage after inspection; it is
not a substitute for physical tread inspection. Tire lists use server-side
filtering and pagination, and filtered results can be exported to CSV.

## Revenue dashboard setup

After the route/rate and truck/trailer migrations above, run
[`supabase_revenue_dashboard_migration.sql`](./supabase_revenue_dashboard_migration.sql)
in the Supabase SQL Editor. The Revenue dashboard is administrator-only and
uses this migration's RPC and audit tables. Restart the Flask app after applying
database migrations so it reloads the current application code.

When updating an existing installation, rerun the current Revenue migration so
the dashboard RPC includes the latest report fields and rate calculation.
Hauling rate revenue sums each trip's verified saved rate snapshot and audited
adjustments, including trips whose management revenue status is still `pending`;
cancelled trips and snapshots still requiring rate or trailer review are
excluded. The separate status remains available for management review and is
required before adding audited revenue adjustments. The schema has no separate
trip completion status. Expense totals use recorded fuel costs
(`actual_expense`, falling back to `total_cost`), reviewed/finalized payroll
items, and maintenance costs. There is no general operating-expense ledger,
and unreviewed payroll or fuel logs without a recorded cost are not estimated.
Net operating revenue is therefore explicitly provisional, and is unavailable
when route, driver, trailer, capacity, or text-search filters would make its
cost scope misleading.

Create trucks and trailers separately in Fleet Management. Select an eligible
truck and an active trailer when dispatching a trip; the trailer's configured
capacity determines the exact directional route rate. Trips cannot be saved
when the route, trailer capacity, or applicable rate is missing. Editing only
the truck or unrelated trip details does not change a saved hauling-rate
snapshot. Driver payroll's separate trip allowance remains unchanged.

The trailer migration also imports the 17 unique plate numbers from the
provided trailer register and preserves its supplied year/model and vehicle
identifiers. The source does not list pallet capacity, so each imported trailer
has an unknown capacity and is marked for review; set its verified capacity in
the Trailers section before it can be assigned to a rate-based trip. The
duplicate `MUA941` source row is represented by one trailer record.

Set a dispatcher's role to `dispatcher` in that user's Supabase **User Metadata**
to enable the compatibility role restriction. Prefer setting `role` in
**App Metadata** when provisioning accounts server-side; App Metadata is
administrator-controlled. The application never accepts `administrator` from
User Metadata as an authorization grant. Users without an explicit dispatcher
role retain the existing administrator access model.

Dispatchers can access their own trips, fuel logs, maintenance records, and tire
records, plus the shared vehicle/driver choices needed to submit them. Payroll,
system exports, fleet registry pages, and delete requests are denied by the
server as well as hidden in the dispatcher interface. Tire history is scoped to
the dispatcher who created each record. The dedicated trip-entry page is
available at `/dispatcher/add-trip` and opens the same verified trip wizard and
business logic used in the in-app Add Trip flow.

Trip entry accepts an optional load-manifest image, and fuel-log entry accepts
an optional invoice image. JPG, PNG, and WEBP files are decoded and validatedon the server and limited to 10 MB by default. Set
`DOCUMENT_IMAGE_MAX_BYTES` to change the server-side per-image limit (up to the
bucket's 50 MB limit). Images are stored in a private Supabase Storage bucket
and delivered through record-ownership-checked app endpoints; they are not
public URLs. Selecting a trip row in the dashboard or Trips page opens a
details popup with its route, vehicle, driver, shipment information, and
uploaded load manifest when available. The popup also lets authorized users
upload a missing manifest later or replace the current image.

New trips are entered through a five-step wizard covering trip details,
assignments, load information, fuel details, and final review. Configured
route/trailer rate rules and route fuel allocations are reused. Load-manifest
and fuel-invoice images are uploaded to private storage after the trip is
created; if an upload fails, the wizard retains the saved trip ID and retries
only the unfinished upload instead of creating another trip. The Full/Empty
load type is included in the existing `load_details` text because the current
schema has no separate load-type column. Persistent draft saving is not offered
because the current schema has no draft-trip workflow.

Open a trip to edit its shipment details and review its edit history. Each
change records the authenticated editor, timestamp, and before/after values.
The edit history is stored by a database trigger; run the current
`supabase_dispatcher_ownership_migration.sql` in Supabase before deploying this
feature. Dispatchers can edit only their own trips.

The interface uses grouped, collapsible desktop navigation and a compact
scrollable navigation bar on mobile. Record tables adapt into labeled cards on
narrow screens and dialogs use device-safe viewport sizing. Fonts use local
system stacks to avoid blocking initial rendering on an external font download.
The bootstrap endpoint reuses its loaded records to calculate its dashboard
summary instead of requesting those tables a second time. The dispatcher
migration adds indexes for commonly sorted trip, fuel, maintenance, and
assignment lists.

The web app requires Supabase email/password authentication. Its access and
refresh tokens are stored in HttpOnly, SameSite browser-session cookies;
protected pages, data APIs, and report exports reject unauthenticated requests.
Sessions expire after three minutes of inactivity, and the open page returns to
sign-in when idle. State-changing API requests also require a CSRF token. For an
HTTPS deployment, set `COOKIE_SECURE=true`; leave it `false` for local HTTP
development.

## Deploy on Vercel

Vercel does not use your local `.env` file. In the Vercel project, open
**Settings → Environment Variables** and add these server-side variables for
every environment you deploy (Production, and Preview if applicable):

- `SUPABASE_URL`: the project URL from Supabase **Settings → API**.
- `SUPABASE_ANON_KEY`: the project's anon/publishable key, used for sign-in.
- `SUPABASE_SERVICE_ROLE_KEY`: the service-role/secret key, used by the server
  to read and update fleet records. Never add this key to frontend code.
- `SECRET_KEY`: a long, random value used to sign session cookies. Generate a
  value locally with `python -c "import secrets; print(secrets.token_hex(32))"`
  and enter it directly in Vercel; do not commit it.
- `COOKIE_SECURE`: `true` for the HTTPS Vercel deployment.

After saving or changing environment variables, redeploy the project so the
serverless functions receive them. A `503` from `/api/auth/login` means the
server could not initialize Supabase Auth; check the response's JSON `error`
and confirm the Vercel `SUPABASE_URL` and `SUPABASE_ANON_KEY` values. If sign-in
then returns `401`, the Supabase connection is working, but the account
credentials were rejected.

The **Export Excel report** action downloads a pre-formatted `.xlsx` workbook
with a dashboard summary and separate worksheets for trucks, trailers, drivers,
assignments, maintenance, fuel logs, and trips.

## Payroll setup and workflow

After creating the fleet/trips tables, run
[`supabase_payroll_migration.sql`](./supabase_payroll_migration.sql) in the
Supabase SQL Editor. This adds payroll periods, immutable reviewed trip/rate
snapshots, driver summaries, cash advances, overdraft transactions, and audit
history. Payroll uses the existing trip and driver IDs and does not copy or
modify trip records. The migration's database function finalizes payroll
atomically and prevents a trip from being finalized in more than one period.
If the payroll migration was already run before an update, rerun the updated SQL
in the Supabase SQL Editor so the finalization function is replaced.

Payroll is available to signed-in users, matching the existing app-wide access
model (the current app does not define separate user roles). Payroll eligibility
uses the route fields and does not require `time_in` or `time_out`. Shipment date
is taken from `shipment_date`, then the legacy `trip_date` or `record_date`.
When `driver_id` is missing, a unique, case-insensitive full-name or last-name
match is used if available; ambiguous matches remain under the imported name.
Matched trips are grouped under the registered driver's full name.
Trips with missing origin/destination, unknown routes, or already finalized
elsewhere are flagged and excluded. A registered driver and ISM number are
required to review and save payroll.

Rates are ₱200 for DAV2–PLAS, DAV1–DAV2, and DAV1–PLAS, and ₱900 for
GENSAN–DAV2, GENSAN–PLAS, and GENSAN–DAV1, in either direction. Payroll review
snapshots each eligible trip and its rate. Finalized payroll retains those
values if trips or route rules later change. Cash advances must be recorded before
review; overdrafts are recorded as explicit opening/new ledger entries and are
never inferred from negative pay. Overdraft settlement is separately confirmed
at finalization. Claims are shown as Coming Soon and do not affect pay.
Payroll reports can be exported as a formatted Excel workbook. Restart the Flask
server or redeploy the application after updating the backend so the payroll
export endpoint is registered.

## Data retrieval performance

Trip and fuel list enrichment reads only fuel records linked to the loaded trip
IDs and only trips linked to the loaded fuel IDs. The bootstrap reuses its fuel
result rather than issuing another enrichment query. Draft payroll reports
filter trips by shipment date in Supabase; reviewed or finalized reports load
their saved payroll items without first loading trip history. Existing ownership
filters and date/foreign-key indexes remain in place.

## Run the app

```powershell
python -m pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000> and sign in with an account created in Supabase
Authentication. Flask serves the static frontend from
[`static/index.html`](./static/index.html), [`static/style.css`](./static/style.css),
and [`static/app.js`](./static/app.js), plus the sign-in screen in
[`static/login.html`](./static/login.html). The JavaScript client uses the
same-origin `/api/` endpoints for data.

Administrators can delete completed dispatch movements from the **Completed
Trips** queue. Deletion requires confirmation and removes the linked trip,
dispatch audit history, and uploaded documents. It is rejected when protected
financial records such as payroll still reference the trip. Unlinked historical
trips can be deleted from the historical trip records table.
Dispatchers cannot delete trips.

### Dispatcher dashboard

The dispatcher dashboard prioritizes arrival verification and receiving work,
shows a small preview of authorized arrival and outbound queues, and provides
shortcuts to record departures or open pending arrivals. Queue counts and
location names come from the authenticated dispatch endpoints; the dashboard
requests only the first five movements per queue and leaves full filtering and
pagination to the Movement Queues page under Dispatch. ISM values remain hidden until the existing
server-side verification flow permits them. The current movement model starts
when a departure is recorded, so the dashboard labels those records as open
outbound movements rather than presenting a separate pending-departure status.

### Dispatcher load catalog

The Add Trip departure form uses `public.load_catalog` for selectable trailer
contents. Import the beverage list with `supabase_load_catalog_import.sql`, then
run `supabase_dispatch_load_catalog_migration.sql` after the location dispatch
migration. The migration adds catalog and movement RPCs so selected products,
pack sizes, and per-product pallet quantities are saved atomically with each
movement and shown in the movement queues. Add Trip presents departure entry as
a seven-step wizard; its searchable, section-filtered product cards support
multiple catalog items and count each selected product in pallets. The overall
trailer pallet quantity remains a separate field. `FULLS` movements require at
least one catalog product, while `EMPTIES` movements do not.
If the migration was run previously, run it again after updating the app so the
database RPC accepts and stores per-product `pallet_quantity` values.
In dispatcher departures, fuel allocation is recorded in liters and actual fuel
expense is recorded in pesos. When the movement is finalized, the allocation is
saved as fuel-log quantity rather than as a currency allocation.
After updating this behavior on an existing Supabase project, rerun
`supabase_location_dispatch_migration.sql` so the finalization RPC saves the
allocated liters to `fuel_logs.quantity`.

### Tailwind CSS assets

The frontend uses Tailwind CSS 4.3.3 through its CLI; it does not use Vite. The
Tailwind toolchain is isolated under `tools/tailwind/` so it does not change the
root Flask/Vercel project detection. Tailwind scans the static HTML and SPA
JavaScript, then writes the production stylesheet to
`static/tailwind.generated.css`, which Flask serves from the existing `/static/`
path.

Install the frontend build dependencies and generate the stylesheet before
deploying changes to the Tailwind source:

```powershell
npm.cmd --prefix tools/tailwind install
npm.cmd --prefix tools/tailwind run build
```

For local styling work, run `npm.cmd --prefix tools/tailwind run watch` in a second
terminal while running Flask. Commit the generated stylesheet with its source
changes; the existing Flask deployment continues to serve static assets without
running a Node build step.

The migration is incremental. The sign-in page, application shell, shared page
heading, KPI card, and dashboard panel now use Tailwind utilities. Existing
`style.css` and `login.css` rules are retained as a lower-priority component
layer for the remaining operational modules, complex responsive tables, charts,
and interactive states. Remove those rules only as their corresponding pages
are migrated and regression-checked. To roll back the Tailwind layer, restore
the previous stylesheet links in `static/index.html` and `static/login.html`;
the original CSS files remain available.

The website uses the supplied SF Pro Display font files from
`static/fonts/` through the shared Tailwind stylesheet. Install and build steps
include those local font assets when deploying.

The same Supabase project is used by the command-line interface:

```powershell
python fleet_management.py dashboard
python fleet_management.py add-vehicle --plate-number ABC-123 --make Toyota --model Hiace --year 2022 --pallet-capacity 36
python fleet_management.py export-report
```

The CLI export writes the same pre-formatted Excel workbook as the web export
to `fleet_system_report.xlsx` by default. Use `--output` to choose another file
path (the file contents remain an Excel workbook).

## Data tables

The schema creates `vehicles`, `drivers`, `assignments`, `maintenance`,
`fuel_logs`, and `trips`. The foreign keys cascade deletion of a vehicle or
driver to its related history.

For an existing Supabase project, run
[`supabase_trips_csv_schema.sql`](./supabase_trips_csv_schema.sql) in the SQL
Editor to adapt `public.trips` to the manifest CSV columns. It preserves
existing trip rows, makes database vehicle/driver IDs optional for imported
records, and backfills fields where possible. For a new project, run
`supabase_schema.sql` first, then this file.

The Trips page columns are ISM NO, SHIPMENT DATE, TIME IN, TIME OUT, ORIGIN,
DESTINATION, PLATE NO, LOAD, DRIVER, and TRIP/FUEL.

To import the supplied sample manifest into an existing project:

1. Run `supabase_trips_csv_schema.sql` first.
2. In Supabase Table Editor, open `public.trips` and choose **Import data from CSV**.
3. Upload [`supabase_trips_import.csv`](./supabase_trips_import.csv).

Dates in the supplied file were converted using 2026. The source's first date
is retained as `record_date`; the second date is `shipment_date`. The CSV also
populates the legacy `route` and `trip_date` columns. Since the source contains
plate numbers and driver names rather than database IDs, it leaves
`vehicle_id` and `driver_id` empty while preserving the source values in
`plate_no` and `driver_name`.

## Test

```powershell
python -m unittest discover -s tests -v
```
