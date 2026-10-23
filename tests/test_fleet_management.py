import json
import os
import tempfile
import time
import unittest
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as web_app
from PIL import Image
from fleet_management import FleetManagementError, FleetManager, _supabase_project_url
from manifest_ocr import canonical_warehouse_code, extract_manifest_fields, truck_route_rate
from openpyxl import load_workbook
from payroll import calculate_driver_payroll, period_date, trip_rate
from werkzeug.exceptions import MethodNotAllowed


class TripDeletionTests(unittest.TestCase):
    def test_admin_can_delete_historical_trip_and_dispatcher_cannot(self):
        delete_trip = Mock()
        manager = SimpleNamespace(delete_trip=delete_trip)
        with patch.dict(
            web_app.app.config,
            {"TESTING": True, "TEST_AUTH_BYPASS": True},
        ), patch.object(web_app, "get_manager", return_value=manager):
            client = web_app.app.test_client()
            with client.session_transaction() as browser_session:
                browser_session["csrf_token"] = "test-csrf-token"

            response = client.delete(
                "/api/trips/42",
                headers={"X-CSRF-Token": "test-csrf-token"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["message"], "Record deleted")
            delete_trip.assert_called_once_with(42)

            with patch.object(web_app, "_is_dispatcher", return_value=True):
                dispatcher_response = client.delete(
                    "/api/trips/42",
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )

            self.assertEqual(dispatcher_response.status_code, 403)
            delete_trip.assert_called_once_with(42)

    def test_dispatch_linked_trip_delete_returns_clear_integrity_message(self):
        manager = FleetManager(client=Mock())
        with patch.object(
            manager,
            "_delete",
            side_effect=FleetManagementError(
                "Supabase request failed: {'code': '23503', "
                "'constraint': 'dispatch_movements_canonical_trip_id_fkey'}"
            ),
        ):
            with self.assertRaisesRegex(
                FleetManagementError,
                "linked to a completed dispatch movement",
            ):
                manager.delete_trip(233)

    def test_dispatch_linked_trip_delete_api_returns_actionable_error(self):
        manager = SimpleNamespace(
            delete_trip=Mock(
                side_effect=FleetManagementError(
                    "This trip is linked to a completed dispatch movement and "
                    "cannot be deleted. The movement history must be preserved."
                )
            )
        )
        with patch.dict(
            web_app.app.config,
            {"TESTING": True, "TEST_AUTH_BYPASS": True},
        ), patch.object(web_app, "get_manager", return_value=manager):
            client = web_app.app.test_client()
            with client.session_transaction() as browser_session:
                browser_session["csrf_token"] = "test-csrf-token"
            response = client.delete(
                "/api/trips/233",
                headers={"X-CSRF-Token": "test-csrf-token"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "linked to a completed dispatch movement",
            response.json["error"],
        )

    def test_admin_historical_trip_rows_include_delete_action(self):
        app_js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "app.js"
        )
        with open(app_js_path, encoding="utf-8") as app_js_file:
            app_js = app_js_file.read()

        legacy_rows = app_js.split("const legacyRows = isAdmin", 1)[1].split(
            "return `", 1
        )[0]
        self.assertIn(
            "tableMarkup(state.data.trips || [], RESOURCE_CONFIG.trips.columns, "
            "RESOURCE_CONFIG.trips.api",
            legacy_rows,
        )
        self.assertIn('rowAction: "trip-details"', legacy_rows)
        self.assertIn('data-action="delete"', app_js)


class PayrollCalculationTests(unittest.TestCase):
    def test_manifest_fields_are_extracted_from_reference_layout(self):
        text = """
        Shipment No. : GLL-4471
        Issuing Plant : GENSAN Distribution Center
        Rec. Plant : Davao Bottling Plant 2
        Fwd Agent : Good Luck Forwarding
        Vehicle Lic. No. : ABC 123
        Vehicle Type : 6-Wheeler
        Manifest Date : 2026-10-02
        Delivery Date : 2026-10-03
        Time In : 08:30
        Time Out : 16:10
        """
        fields = extract_manifest_fields(text)
        self.assertEqual(fields["manifest_number"], "GLL-4471")
        self.assertEqual(fields["origin"], "GENSAN")
        self.assertEqual(fields["destination"], "DAV2")
        self.assertEqual(fields["vehicle_plate"], "ABC 123")
        self.assertEqual(fields["manifest_date"], "2026-10-02")
        self.assertEqual(fields["time_in"], "08:30")
        self.assertEqual(fields["time_out"], "16:10")

    def test_manifest_warehouse_aliases_normalize_to_canonical_codes(self):
        self.assertEqual(canonical_warehouse_code("GENSAN Distribution Center"), "GENSAN")
        self.assertEqual(canonical_warehouse_code("Davao Bottling Plant 2"), "DAV2")
        self.assertEqual(canonical_warehouse_code("Davao Bottling Plant 1"), "DAV1")
        self.assertEqual(canonical_warehouse_code("PLAS Astorga"), "PLAS")
        self.assertIsNone(canonical_warehouse_code("UNKNOWN PLANT"))

    def test_truck_route_rates_match_directional_capacity_and_flag_missing_config(self):
        self.assertEqual(str(truck_route_rate("GENSAN", "DAV2", 36)), "11000.00")
        self.assertEqual(str(truck_route_rate("GENSAN", "DAV2", 46)), "14000.00")
        self.assertIsNone(truck_route_rate("DAV1", "DAV2", 36))
        self.assertEqual(str(truck_route_rate("PLAS", "DAV1", 46)), "2300.00")

    def test_route_trip_migration_seeds_all_routes_and_null_rate_exceptions(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_route_trip_rate_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        self.assertTrue(all(f"({number}, '" in migration for number in range(1, 13)))
        self.assertEqual(migration.count("null::numeric"), 2)
        self.assertIn("on conflict (origin_code, destination_code)", migration)
        self.assertIn("on conflict (origin_code, destination_code, pallet_capacity)", migration)
        self.assertIn("hauling_rate drop not null", migration)
        self.assertIn("truck_route_rate numeric(12, 2)", migration)
        self.assertIn("trip_rate_review_required boolean not null default true", migration)

    def test_truck_trailer_migration_preserves_trucks_and_flags_unknown_trailers(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_truck_trailer_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        self.assertIn("create table if not exists public.trailers", migration)
        self.assertIn("references public.vehicles(id) on delete set null", migration)
        self.assertIn("set truck_id = vehicle_id", migration)
        self.assertIn("set trailer_review_required = true", migration)
        self.assertIn("legacy_vehicle_capacity_review", migration)
        self.assertIn("legacy_trip_rate_review", migration)
        self.assertIn("alter table public.vehicles drop column pallet_capacity", migration)
        self.assertIn("truck_route_rate = null", migration)
        self.assertIn("trip_rate_review_required = true", migration)
        self.assertIn("pallet_capacity integer check (pallet_capacity is null or pallet_capacity > 0)", migration)
        self.assertIn("on conflict (plate_number) do update", migration)
        for plate in (
            "MUB289", "MUA508", "MUA518", "MUA528", "MUA548", "MUA941",
            "MUB106", "MUB109", "MUB482", "MUA538", "MUA551", "MUA973",
            "MUB116", "MUB263", "MUB282", "MUB285", "TEMP120108",
        ):
            self.assertIn(f"('{plate}',", migration)

    def test_payroll_migration_locks_trips_without_hash_functions(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_payroll_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        self.assertIn("pg_advisory_xact_lock(item_row.trip_id)", migration)
        self.assertNotIn("hashtextext", migration)

    def test_dispatch_api_uses_authenticated_database_pagination(self):
        movements = [{
            "id": "11111111-1111-4111-8111-111111111111",
            "ism_no": None,
            "status": "awaiting_arrival",
        }]
        with patch.dict(
            web_app.app.config,
            {"TESTING": True, "TEST_AUTH_BYPASS": True, "TEST_AUTH_ROLE": "dispatcher"},
        ), patch.object(web_app, "_dispatch_rpc", return_value={
            "total": 1, "movements": movements,
        }) as dispatch_rpc:
            response = web_app.app.test_client().get(
                "/api/dispatch/movements?queue=arrivals&page=2&page_size=10&search=truck"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["movements"], movements)
        self.assertEqual(response.json["total"], 1)
        dispatch_rpc.assert_called_once_with(
            "list_dispatch_movements_page",
            {
                "p_queue": "arrivals",
                "p_page": 2,
                "p_page_size": 10,
                "p_search": "truck",
            },
        )

    def test_dispatch_client_uses_bounded_postgrest_timeout(self):
        request_client = SimpleNamespace(
            options=SimpleNamespace(headers={}),
            postgrest=SimpleNamespace(auth=Mock()),
            auth=SimpleNamespace(close=Mock()),
        )
        request_client.postgrest.session = SimpleNamespace(close=Mock())
        with patch.object(web_app, "_supabase_setting", side_effect={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon-key",
        }.get), patch.object(
            web_app, "_supabase_project_url", return_value="https://example.supabase.co"
        ), patch.object(web_app, "create_client", return_value=request_client) as create:
            with web_app.app.test_request_context("/api/dispatch/movements"):
                web_app.g.dispatch_access_token = "user-access-token"
                result = web_app.get_dispatch_client()

        self.assertIs(result, request_client)
        self.assertEqual(create.call_args.kwargs["options"].postgrest_client_timeout, 15)
        request_client.postgrest.auth.assert_called_once_with("user-access-token")

    def test_dispatch_rpc_reports_specific_database_failures(self):
        class DispatchDatabaseError(Exception):
            def __init__(self, code, message, status=None):
                super().__init__(message)
                self.code = code
                self.message = message
                self.status = status

        with patch.object(
            web_app,
            "get_dispatch_client",
            side_effect=DispatchDatabaseError("PGRST202", "function is missing"),
        ):
            with self.assertRaisesRegex(FleetManagementError, "function.*is missing"):
                web_app._dispatch_rpc("list_dispatch_movements_page")

        with patch.object(
            web_app,
            "get_dispatch_client",
            side_effect=DispatchDatabaseError("42501", "permission denied"),
        ):
            with self.assertRaisesRegex(FleetManagementError, "permission denied.*42501"):
                web_app._dispatch_rpc("list_dispatch_locations")

        with patch.object(
            web_app,
            "get_dispatch_client",
            side_effect=DispatchDatabaseError("XX000", "specific database failure"),
        ):
            with self.assertRaisesRegex(FleetManagementError, "specific database failure"):
                web_app._dispatch_rpc("list_dispatch_locations")

    def test_dispatchers_cannot_create_legacy_financial_trip_rows(self):
        with web_app.app.test_request_context("/api/trips", method="POST"):
            web_app.g.current_user = {"role": "dispatcher"}
            response, status = web_app._authorize_dispatcher_request()

        self.assertEqual(status, 403)
        self.assertIn("Departure", response.get_json()["error"])

    def test_dispatch_migration_never_grants_direct_ism_column_access(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_location_dispatch_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        create_movement = migration.split(
            "create or replace function public.create_dispatch_movement", 1
        )[1].split("create or replace function public.list_dispatch_movements_page", 1)[0]
        self.assertIn("select count(*)", create_movement)
        self.assertIn(") <> 2 then", create_movement)
        self.assertNotIn("group by true", create_movement)

        grant_block = migration.split(
            "grant select (", 1
        )[1].split(") on public.dispatch_movements", 1)[0]
        self.assertNotIn("ism_no", grant_block)
        self.assertIn(
            "movement.arrival_verified_by = auth.uid()",
            migration,
        )
        self.assertIn(
            "revoke all on public.dispatch_movements from anon, authenticated",
            migration,
        )
        listing = migration.split(
            "create or replace function public.list_dispatch_movements()", 1
        )[1].split("create or replace function public.create_dispatch_movement", 1)[0]
        self.assertIn(
            "or movement.arrival_verified_by = auth.uid()\n"
            "            then movement.arrival_manifest_path",
            listing,
        )
        storage_read = migration.split(
            "create policy dispatch_movement_documents_read", 1
        )[1].split(
            "drop policy if exists dispatch_movement_documents_scope_guard", 1
        )[0]
        self.assertIn("or movement.arrival_verified_by = auth.uid()", storage_read)
        self.assertNotIn(
            "or public.dispatch_has_location(movement.destination_location_id, 'view')",
            storage_read,
        )

    def test_dispatcher_add_trip_path_renders_location_workflow(self):
        app_js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "app.js"
        )
        index_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "index.html"
        )
        with open(app_js_path, encoding="utf-8") as app_js_file:
            app_js = app_js_file.read()
        with open(index_path, encoding="utf-8") as index_file:
            index_html = index_file.read()

        self.assertIn('if (isDedicatedAddTripPage) {\n    state.page = "trips";', app_js)
        self.assertIn(
            "if (isDedicatedAddTripPage && !isDispatcher) {",
            app_js,
        )
        self.assertIn('if (page === "trips") return renderDispatchWorkflow();', app_js)
        self.assertIn('app.js?v=location-dispatch-9', index_html)
        self.assertIn("window.setTimeout(() => controller.abort(), 20000)", app_js)
        self.assertIn("The dispatch service did not respond within 20 seconds.", app_js)
        render_workflow = app_js.split("function renderDispatchWorkflow() {", 1)[1].split(
            "function dispatchStatusLabel", 1
        )[0]
        self.assertLess(
            render_workflow.index("if (state.dispatch.error && !state.dispatch.loaded)"),
            render_workflow.index("if (!state.dispatch.loaded && !state.dispatch.loading)"),
        )
        self.assertIn(
            "updateDispatchDepartureAvailability(form);",
            app_js.split("function refreshDispatchDestinations", 1)[1].split(
                "function validateDispatchPalletQuantity", 1
            )[0],
        )

    def test_dispatcher_dashboard_uses_limited_authorized_queues_and_masks_ism(self):
        app_js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "app.js"
        )
        with open(app_js_path, encoding="utf-8") as app_js_file:
            app_js = app_js_file.read()

        dashboard_loader = app_js.split(
            "async function loadDispatcherDashboard", 1
        )[1].split("function renderDispatcherDashboard", 1)[0]
        movement_card = app_js.split(
            "function dispatchMovementCard", 1
        )[1].split("function dispatchDepartureForm", 1)[0]
        self.assertIn(
            "/api/dispatch/movements?queue=arrivals&page=1&page_size=5",
            dashboard_loader,
        )
        self.assertIn(
            "/api/dispatch/movements?queue=departures&page=1&page_size=5",
            dashboard_loader,
        )
        self.assertIn('api("/api/dispatch/locations"', dashboard_loader)
        self.assertIn("canViewIsm && movement.ism_no", movement_card)
        self.assertIn("movement.arrival_verified_at", movement_card)
        self.assertIn("Record Arrival for Review", movement_card)

    def test_dispatcher_code_migration_assigns_matching_dav_location(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "supabase_dispatcher_code_location_migration.sql",
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        self.assertIn("profile.dispatcher_code)) ~ '^D[1-6]$'", migration)
        self.assertIn("'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2)", migration)
        self.assertIn("join auth.users as auth_user on auth_user.id = profile.id", migration)
        self.assertNotIn("auth_user.raw_app_meta_data ->> 'role' = 'dispatcher'", migration)
        dispatcher_migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_location_dispatch_migration.sql"
        )
        with open(
            dispatcher_migration_path,
            encoding="utf-8",
        ) as dispatcher_migration_file:
            dispatcher_functions = dispatcher_migration_file.read()
        self.assertIn(
            "or users.raw_user_meta_data ->> 'role' = 'dispatcher'",
            dispatcher_functions,
        )
        self.assertIn(
            "or raw_user_meta_data ->> 'role' = 'dispatcher'",
            dispatcher_functions,
        )
        self.assertIn("information_schema.tables", migration)
        self.assertIn("profile_table_count > 1", migration)
        self.assertNotIn("from public.users as profile", migration)
        self.assertIn("can_depart, can_arrive", migration)
        self.assertIn("on conflict (user_id, location_id) do update set", migration)

    def test_dispatch_origin_access_is_any_active_origin_but_requires_assignment(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "supabase_dispatch_origin_access_migration.sql",
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        helper = migration.split(
            "create or replace function public.dispatch_has_location", 1
        )[1].split(
            "create or replace function public.list_dispatch_movements", 1
        )[0]
        self.assertIn("p_permission = 'depart'", helper)
        self.assertIn("where location.id = p_location_id", helper)
        self.assertIn("and location.active", helper)
        self.assertIn("and assignment.can_depart", helper)
        self.assertNotIn("auth.jwt() -> 'user_metadata'", helper)
        self.assertIn("p_permission = 'arrive' and assignment.can_arrive", helper)

        listing = migration.split(
            "create or replace function public.list_dispatch_movements", 1
        )[1].split("drop policy if exists dispatch_movements_read", 1)[0]
        self.assertIn("or movement.departure_user_id = auth.uid()", listing)
        self.assertIn(
            "movement.status <> 'completed'\n"
            "           and public.dispatch_has_location(movement.origin_location_id, 'depart')",
            listing,
        )
        ism_visibility = listing.split("case\n            when", 1)[1].split(
            "then movement.ism_no", 1
        )[0]
        self.assertNotIn(
            "public.dispatch_has_location(movement.origin_location_id, 'view')",
            ism_visibility,
        )
        self.assertIn("then movement.arrival_manifest_path", listing)
        movement_policy = migration.split(
            "create policy dispatch_movements_read", 1
        )[1].split("drop policy if exists dispatch_audit_read", 1)[0]
        self.assertIn("public.dispatch_has_location(origin_location_id, 'depart')", movement_policy)

    def test_dispatch_page_reuses_eligible_movements_for_count_and_rows(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "supabase_dispatch_origin_access_migration.sql",
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        page_function = migration.split(
            "create or replace function public.list_dispatch_movements_page", 1
        )[1].split("drop policy if exists dispatch_movements_read", 1)[0]
        self.assertIn("with eligible as materialized", page_function)
        self.assertEqual(page_function.count("public.list_dispatch_movements()"), 1)
        self.assertIn("(select count(*) from eligible)", page_function)
        self.assertIn(
            "jsonb_agg(\n"
            "                to_jsonb(page_row)\n"
            "                order by page_row.departure_at desc, page_row.id",
            page_function,
        )

    def test_app_pages_are_not_cached(self):
        with patch.dict(
            web_app.app.config,
            {"TESTING": True, "TEST_AUTH_BYPASS": True},
        ):
            client = web_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = "test-user"

            index_response = client.get("/")
            dispatch_response = client.get("/dispatcher/add-trip")
            self.assertEqual(index_response.headers["Cache-Control"], "no-store")
            self.assertEqual(
                dispatch_response.headers["Cache-Control"],
                "no-store",
            )
            index_response.close()
            dispatch_response.close()

    def test_payroll_get_route_is_not_claimed_by_generic_resource_routes(self):
        adapter = web_app.app.url_map.bind("127.0.0.1")

        self.assertEqual(adapter.match("/api/payroll", method="GET")[0], "payroll_report")
        with self.assertRaises(MethodNotAllowed):
            adapter.match("/api/payroll", method="POST")
        self.assertEqual(adapter.match("/api/trips", method="POST")[0], "create_record")

    def test_revenue_api_rejects_unsupported_trend_buckets(self):
        with patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ), patch.object(web_app, "get_manager") as get_manager:
            response = web_app.app.test_client().get(
                "/api/revenue?start_date=2026-10-01&end_date=2026-10-14&bucket=quarter"
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("day, week, or month", response.json["error"])
        get_manager.assert_not_called()

    def test_revenue_api_passes_selected_trend_bucket_to_dashboard_rpc(self):
        manager = SimpleNamespace(
            revenue_dashboard=lambda filters: {"received_bucket": filters["p_bucket"]}
        )
        with patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ), patch.object(web_app, "get_manager", return_value=manager):
            response = web_app.app.test_client().get(
                "/api/revenue?start_date=2026-10-01&end_date=2026-10-14&bucket=week"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["received_bucket"], "week")

    def test_revenue_dashboard_uses_saved_eligibility_and_recorded_expense_sources(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_revenue_dashboard_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read()

        self.assertIn("trip.revenue_status <> 'cancelled'", migration)
        self.assertIn("trip.truck_route_rate", migration)
        self.assertIn("and not coalesce(trip.trip_rate_review_required, true)", migration)
        self.assertIn("and not coalesce(trip.trailer_review_required, true)", migration)
        self.assertIn("public.fuel_logs", migration)
        self.assertIn("coalesce(actual_expense, total_cost)", migration)
        self.assertIn("public.payroll_items", migration)
        self.assertIn("period.status in ('reviewed', 'finalized')", migration)
        self.assertIn("coalesce(sum(rate) filter (where item_rank = 1), 0)", migration)
        self.assertIn("public.maintenance", migration)
        self.assertIn("'other_operating_expenses_available', false", migration)
        self.assertIn("'net_operating_revenue_available'", migration)

    def test_known_route_rates_are_bidirectional_and_case_insensitive(self):
        routes = [
            ("DAV2", "PLAS", "200.00"),
            ("PLAS", "DAV2", "200.00"),
            ("DAV1", "DAV2", "200.00"),
            ("DAV2", "DAV1", "200.00"),
            ("DAV1", "PLAS", "200.00"),
            ("PLAS", "DAV1", "200.00"),
            ("GENSAN", "DAV2", "900.00"),
            ("DAV2", "GENSAN", "900.00"),
            ("GENSAN", "PLAS", "900.00"),
            ("PLAS", "GENSAN", "900.00"),
            ("GENSAN", "DAV1", "900.00"),
            ("DAV1", "GENSAN", "900.00"),
            ("gensan", "plas", "900.00"),
        ]
        for origin, destination, expected in routes:
            with self.subTest(origin=origin, destination=destination):
                self.assertEqual(str(trip_rate(origin, destination)), expected)
        self.assertIsNone(trip_rate(None, "DAV2"))

    def test_payroll_net_and_explicit_overdraft_settlement(self):
        trips = [{"rate": "900.00"}, {"rate": "200.00"}]
        advances = [{"amount": "300.00"}]
        before_settlement = calculate_driver_payroll(trips, advances, "500.00")
        self.assertEqual(before_settlement["gross_pay"], Decimal("1100.00"))
        self.assertEqual(before_settlement["net_before_overdraft"], Decimal("800.00"))
        self.assertEqual(before_settlement["overdraft_deduction"], Decimal("0.00"))
        settled = calculate_driver_payroll(
            trips, advances, "500.00", settle_overdraft=True
        )
        self.assertEqual(settled["overdraft_deduction"], Decimal("500.00"))
        self.assertEqual(settled["final_net_pay"], Decimal("300.00"))
        negative = calculate_driver_payroll(
            [{"rate": "200.00"}], [{"amount": "300.00"}], "500.00"
        )
        self.assertEqual(negative["net_before_overdraft"], Decimal("-100.00"))
        self.assertEqual(negative["remaining_amount_due"], Decimal("100.00"))
        self.assertEqual(negative["overdraft_deduction"], Decimal("0.00"))

    def test_payroll_period_dates_are_validated(self):
        self.assertEqual(period_date("2026-10-01", "Start date").isoformat(), "2026-10-01")
        with self.assertRaisesRegex(ValueError, "valid date"):
            period_date("not-a-date", "Start date")

    def test_payroll_report_uses_routes_without_requiring_trip_times(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-001", "Toyota", "Hiace", 2022)
        driver = manager.add_driver("Payroll Driver", "PAY-DL-1")
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV2 to PLAS", 0, 0,
            ism_no="ISM-200", shipment_date="2026-10-02",
            time_in="08:00", time_out="10:00", origin="DAV2", destination="PLAS",
        )
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV1 to PLAS", 0, 0,
            ism_no="ISM-201", shipment_date="2026-10-03",
            time_in="08:00", time_out="10:00", origin="DAV1", destination="PLAS",
        )
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV1 to DAV2", 0, 0,
            ism_no="ISM-202", shipment_date="2026-10-04",
            time_in="08:00", origin="DAV1", destination="DAV2",
        )
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV1 to UNKNOWN", 0, 0,
            ism_no="ISM-203", shipment_date="2026-10-05",
            time_in="08:00", time_out="10:00", origin="DAV1", destination="UNKNOWN",
        )

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertEqual(report["drivers"][0]["gross_pay"], "600.00")
        self.assertEqual(len([trip for trip in report["trips"] if trip["eligible"]]), 3)
        self.assertEqual(
            {trip["issue"] for trip in report["issues"]},
            {"Unconfigured Route"},
        )

    def test_payroll_matches_imported_trip_driver_name_when_driver_id_is_missing(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-IMPORT", "Toyota", "Hiace", 2022)
        driver = manager.add_driver("Imported Driver", "PAY-DL-IMPORT")
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV1 to PLAS", 0, 0,
            ism_no="ISM-IMPORT", shipment_date="2026-10-03",
            origin="DAV1", destination="PLAS",
        )
        client.tables["trips"][0]["driver_id"] = None
        client.tables["trips"][0]["driver_name"] = "  imported   DRIVER "

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertEqual(report["trips"][0]["driver_id"], driver["id"])
        self.assertTrue(report["trips"][0]["eligible"])
        self.assertEqual(report["trips"][0]["rate"], "200.00")
        self.assertEqual(report["drivers"][0]["gross_pay"], "200.00")

    def test_payroll_matches_unique_imported_last_name_to_registered_driver(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        driver = manager.add_driver("Rey Madamba", "PAY-DL-MADAMBA")
        client.tables["trips"] = [{
            "id": 21,
            "driver_id": None,
            "driver_name": "  MADAMBA ",
            "ism_no": "ISM-MADAMBA",
            "shipment_date": "2026-10-03",
            "origin": "DAV1",
            "destination": "PLAS",
            "time_in": None,
            "time_out": None,
        }]

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertEqual(report["trips"][0]["driver_id"], driver["id"])
        self.assertEqual(report["trips"][0]["driver_name"], "Rey Madamba")
        self.assertEqual(report["trips"][0]["driver_key"], f"id:{driver['id']}")
        self.assertEqual(report["drivers"][0]["gross_pay"], "200.00")
        self.assertEqual(report["drivers"][0]["total_trips"], 1)

    def test_payroll_does_not_guess_when_imported_last_name_is_ambiguous(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        manager.add_driver("Rey Madamba", "PAY-DL-MADAMBA-1")
        manager.add_driver("Jose Madamba", "PAY-DL-MADAMBA-2")
        client.tables["trips"] = [{
            "id": 22,
            "driver_id": None,
            "driver_name": "Madamba",
            "ism_no": "ISM-MADAMBA-AMBIGUOUS",
            "shipment_date": "2026-10-03",
            "origin": "DAV1",
            "destination": "PLAS",
            "time_in": None,
            "time_out": None,
        }]

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertIsNone(report["trips"][0]["driver_id"])
        self.assertEqual(report["trips"][0]["driver_name"], "Madamba")
        self.assertEqual(report["trips"][0]["rate"], "200.00")
        self.assertEqual(
            [driver["gross_pay"] for driver in report["drivers"]],
            ["0.00", "0.00", "200.00"],
        )

    def test_payroll_calculates_unassigned_import_by_route_without_ism_or_times(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        manager.add_driver("Registered Driver", "PAY-DL-REGISTERED")
        client.tables["trips"] = [{
            "id": 12,
            "driver_id": None,
            "driver_name": "Manifest Only Driver",
            "ism_no": None,
            "shipment_date": "2026-10-03",
            "origin": "PLAS",
            "destination": "DAV1",
            "time_in": None,
            "time_out": None,
        }]

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertEqual(report["trips"][0]["rate"], "200.00")
        self.assertTrue(report["trips"][0]["eligible"])
        self.assertEqual(report["trips"][0]["issue"], None)
        self.assertEqual(report["drivers"][1]["driver_name"], "Manifest Only Driver")
        self.assertEqual(report["drivers"][1]["gross_pay"], "200.00")

    def test_review_rejects_unassigned_trip_after_showing_route_earnings(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        client.tables["trips"] = [{
            "id": 12,
            "driver_id": None,
            "driver_name": "Manifest Only Driver",
            "ism_no": "ISM-IMPORT",
            "shipment_date": "2026-10-03",
            "origin": "GENSAN",
            "destination": "PLAS",
            "time_in": None,
            "time_out": None,
        }]

        report = manager.payroll_report("2026-10-01", "2026-10-15")
        self.assertEqual(report["drivers"][0]["gross_pay"], "900.00")
        with self.assertRaisesRegex(ValueError, "registered driver"):
            manager.review_payroll(
                "2026-10-01", "2026-10-15",
                "00000000-0000-0000-0000-000000000001",
            )

    def test_payroll_counts_configured_route_without_trip_times(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-INCOMPLETE", "Toyota", "Hiace", 2022)
        driver = manager.add_driver("Incomplete Driver", "PAY-DL-INCOMPLETE")
        manager.add_trip(
            vehicle["id"], driver["id"], "GENSAN to PLAS", 0, 0,
            ism_no="ISM-INCOMPLETE", shipment_date="2026-10-03",
            time_in="08:00", origin="GENSAN", destination="PLAS",
        )

        report = manager.payroll_report("2026-10-01", "2026-10-15")

        self.assertEqual(report["trips"][0]["rate"], "900.00")
        self.assertTrue(report["trips"][0]["eligible"])
        self.assertIsNone(report["trips"][0]["issue"])
        self.assertEqual(report["drivers"][0]["gross_pay"], "900.00")

    def test_review_snapshots_eligible_trip_rates(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-002", "Toyota", "Hiace", 2022)
        driver = manager.add_driver("Reviewed Driver", "PAY-DL-2")
        manager.add_trip(
            vehicle["id"], driver["id"], "GENSAN to DAV2", 0, 0,
            ism_no="ISM-900", shipment_date="2026-10-05",
            time_in="08:00", time_out="16:00",
            origin="GENSAN", destination="DAV2",
        )
        client.tables["trips"][0]["truck_route_rate"] = "11000.00"

        report = manager.review_payroll(
            "2026-10-01", "2026-10-15", "00000000-0000-0000-0000-000000000001"
        )

        self.assertEqual(report["status"], "reviewed")
        self.assertEqual(report["trips"][0]["rate"], "900.00")
        self.assertEqual(report["trips"][0]["truck_route_rate"], "11000.00")
        self.assertEqual(report["drivers"][0]["gross_pay"], "900.00")
        self.assertEqual(client.tables["payroll_items"][0]["trip_id"], 1)
        self.assertEqual(client.tables["payroll_items"][0]["rate"], "900.00")
        self.assertEqual(client.tables["payroll_items"][0]["truck_route_rate"], "11000.00")

    def test_payroll_report_api_returns_existing_trip_line_items(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-003", "Toyota", "Hiace", 2022)
        driver = manager.add_driver("API Payroll Driver", "PAY-DL-3")
        manager.add_trip(
            vehicle["id"], driver["id"], "DAV1 to DAV2", 0, 0,
            ism_no="ISM-API", shipment_date="2026-10-06",
            time_in="08:00", time_out="11:00",
            origin="DAV1", destination="DAV2",
        )
        with patch.object(web_app, "manager", manager), patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ):
            response = web_app.app.test_client().get(
                "/api/payroll?start_date=2026-10-01&end_date=2026-10-15"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["trips"][0]["ism_no"], "ISM-API")
        self.assertEqual(response.json["trips"][0]["rate"], "200.00")

    def test_payroll_excel_export_matches_selected_report_filters(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-XLS-1", "Toyota", "Hiace", 2022)
        first_driver = manager.add_driver("Excel Payroll Driver", "PAY-XLS-DL-1")
        second_driver = manager.add_driver("Other Payroll Driver", "PAY-XLS-DL-2")
        manager.add_trip(
            vehicle["id"], first_driver["id"], "DAV1 to DAV2", 0, 0,
            ism_no="ISM-XLS-MATCH", shipment_date="2026-10-05",
            origin="DAV1", destination="DAV2",
        )
        manager.add_trip(
            vehicle["id"], first_driver["id"], "DAV1 to DAV2", 0, 0,
            ism_no="ISM-XLS-OTHER", shipment_date="2026-10-06",
            origin="DAV1", destination="DAV2",
        )
        manager.add_trip(
            vehicle["id"], second_driver["id"], "GENSAN to DAV2", 0, 0,
            ism_no="ISM-XLS-MATCH-OTHER", shipment_date="2026-10-07",
            origin="GENSAN", destination="DAV2",
        )
        with patch.object(web_app, "manager", manager), patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ):
            response = web_app.app.test_client().get(
                "/api/payroll/export?start_date=2026-10-01&end_date=2026-10-15"
                f"&driver_id={first_driver['id']}&ism_no=MATCH&origin=DAV1&destination=DAV2"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("payroll-2026-10-01-to-2026-10-15.xlsx", response.headers["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        self.assertEqual(
            workbook.sheetnames,
            [
                "Payroll Summary", "Trip Details", "Cash Advances",
                "Overdraft Ledger", "Review Items", "Audit History",
                "Payslip Excel Payroll Driver",
            ],
        )
        summary = workbook["Payroll Summary"]
        self.assertEqual(summary["B6"].value, 1)
        self.assertEqual(summary["B7"].value, 1)
        self.assertEqual(summary["A16"].value, "Excel Payroll Driver")
        self.assertEqual(summary["B16"].value, 1)
        trips = workbook["Trip Details"]
        self.assertEqual(trips["B6"].value, "Excel Payroll Driver")
        self.assertEqual(trips["C6"].value, "ISM-XLS-MATCH")
        self.assertEqual(trips["F6"].value, 200)
        payslip = workbook["Payslip Excel Payroll Driver"]
        self.assertEqual(payslip["A1"].value, "EMPLOYEE PAYSLIP")
        self.assertEqual(payslip["B7"].value, "Excel Payroll Driver")
        self.assertEqual(payslip["B12"].value, "ISM-XLS-MATCH")
        self.assertEqual(payslip["E12"].value, 200)
        self.assertEqual(payslip["F17"].value, 400)
        self.assertEqual(payslip.page_setup.fitToWidth, 1)
        self.assertEqual(payslip.page_setup.fitToHeight, 1)
        self.assertEqual(payslip.print_area, "'Payslip Excel Payroll Driver'!$A$1:$F$28")

    def test_payroll_excel_export_creates_one_payslip_sheet_per_driver(self):
        client = FakeSupabaseClient()
        manager = FleetManager(client=client)
        vehicle = manager.add_vehicle("PAY-XLS-2", "Toyota", "Hiace", 2022)
        drivers = [
            manager.add_driver("First Payslip Driver", "PAY-XLS-DL-3"),
            manager.add_driver("Second Payslip Driver", "PAY-XLS-DL-4"),
        ]
        for index, driver in enumerate(drivers, start=1):
            manager.add_trip(
                vehicle["id"], driver["id"], "DAV1 to DAV2", 0, 0,
                ism_no=f"ISM-PAYSLIP-{index}", shipment_date=f"2026-10-0{index}",
                origin="DAV1", destination="DAV2",
            )
        with patch.object(web_app, "manager", manager), patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ):
            response = web_app.app.test_client().get(
                "/api/payroll/export?start_date=2026-10-01&end_date=2026-10-15"
            )

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        self.assertIn("Payslip First Payslip Driver", workbook.sheetnames)
        self.assertIn("Payslip Second Payslip Driver", workbook.sheetnames)
        self.assertEqual(
            [
                name for name in workbook.sheetnames
                if name.startswith("Payslip ")
            ],
            ["Payslip First Payslip Driver", "Payslip Second Payslip Driver"],
        )


class FakeAuthApiError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status
        self.code = "invalid_credentials"


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.action = "select"
        self.columns = "*"
        self.values = None
        self.filters = []
        self.sort = None
        self.row_limit = None
        self.row_range = None

    def select(self, columns="*", **kwargs):
        self.columns = columns
        return self

    def insert(self, values):
        self.action = "insert"
        self.values = values
        return self

    def update(self, values):
        self.action = "update"
        self.values = values
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def order(self, column, desc=False):
        self.sort = (column, desc)
        return self

    def limit(self, count):
        self.row_limit = count
        return self

    def range(self, start, end):
        self.row_range = (start, end)
        return self

    def _matches(self, row):
        for filter_value in self.filters:
            if filter_value[0] == "in":
                _, column, values = filter_value
                if row.get(column) not in values:
                    return False
            elif filter_value[0] in {"gte", "lte"}:
                operator, column, value = filter_value
                row_value = row.get(column)
                if row_value is None:
                    return False
                if operator == "gte" and row_value < value:
                    return False
                if operator == "lte" and row_value > value:
                    return False
            else:
                column, value = filter_value
                if row.get(column) != value:
                    return False
        return True

    def execute(self):
        self.client.query_log.append({
            "table": self.table_name,
            "action": self.action,
            "columns": self.columns,
            "filters": list(self.filters),
        })
        rows = self.client.tables.setdefault(self.table_name, [])
        if self.action == "insert":
            inserted = []
            values = self.values if isinstance(self.values, list) else [self.values]
            for value in values:
                row = dict(value)
                row["id"] = self.client.next_ids.get(self.table_name, 0) + 1
                self.client.next_ids[self.table_name] = row["id"]
                if self.table_name == "payroll_periods":
                    row.setdefault("status", "draft")
                rows.append(row)
                inserted.append(dict(row))
            return SimpleNamespace(data=inserted)
        if self.action == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self.values)
                    updated.append(row)
            return SimpleNamespace(data=[dict(row) for row in updated])
        if self.action == "delete":
            self.client.tables[self.table_name] = [
                row for row in rows if not self._matches(row)
            ]
            return SimpleNamespace(data=[])

        result = [dict(row) for row in rows if self._matches(row)]
        if self.sort:
            column, desc = self.sort
            result.sort(key=lambda row: row.get(column) or "", reverse=desc)
        if self.row_limit is not None:
            result = result[: self.row_limit]
        if self.row_range is not None:
            start, end = self.row_range
            result = result[start : end + 1]
        if (
            self.columns not in ("*",)
            and "driver:" not in self.columns
            and "vehicle:" not in self.columns
            and "truck:" not in self.columns
        ):
            selected = [column.strip() for column in self.columns.split(",")]
            result = [{key: row.get(key) for key in selected} for row in result]
        for row in result:
            if "driver:drivers(" in self.columns:
                driver = next(
                    (
                        item
                        for item in self.client.tables.get("drivers", [])
                        if item["id"] == row["driver_id"]
                    ),
                    None,
                )
                row["driver"] = {"name": driver["name"]} if driver else None
            if "truck:vehicles!" in self.columns or "vehicle:vehicles(" in self.columns:
                relation_name = "truck" if "truck:vehicles!" in self.columns else "vehicle"
                vehicle = next(
                    (
                        item
                        for item in self.client.tables.get("vehicles", [])
                        if item["id"] == row.get("truck_id", row.get("vehicle_id"))
                    ),
                    None,
                )
                if vehicle:
                    row[relation_name] = {
                        key: vehicle.get(key)
                        for key in ("plate_number", "make", "model")
                    }
                else:
                    row[relation_name] = None
            if "trailer:trailers(" in self.columns:
                trailer = next(
                    (
                        item
                        for item in self.client.tables.get("trailers", [])
                        if item["id"] == row.get("trailer_id")
                    ),
                    None,
                )
                row["trailer"] = (
                    {
                        key: trailer.get(key)
                        for key in ("plate_number", "pallet_capacity", "trailer_type", "status")
                    }
                    if trailer else None
                )
        return SimpleNamespace(data=result)


class FakeSupabaseClient:
    def __init__(self):
        self.tables = {}
        self.next_ids = {}
        self.query_log = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FakeStorage:
    def __init__(self):
        self.files = {}

    def from_(self, _bucket):
        return self

    def upload(self, path, file, _options):
        self.files[path] = file

    def download(self, path):
        return self.files[path]

    def remove(self, paths):
        for path in paths:
            self.files.pop(path, None)


class FakeAuthClient:
    def __init__(self):
        self.auth = self
        self.user = SimpleNamespace(id="auth-user-1", email="fleet@example.com")
        self.auth_session = SimpleNamespace(
            access_token="valid-access-token",
            refresh_token="valid-refresh-token",
            expires_in=3600,
        )

    def sign_in_with_password(self, credentials):
        if credentials != {"email": "fleet@example.com", "password": "correct-password"}:
            raise FakeAuthApiError("Invalid credentials", 400)
        return SimpleNamespace(session=self.auth_session, user=self.user)

    def get_user(self, access_token):
        if access_token != self.auth_session.access_token:
            raise ValueError("Expired access token")
        return SimpleNamespace(user=self.user)

    def refresh_session(self, refresh_token):
        if refresh_token != self.auth_session.refresh_token:
            raise ValueError("Invalid refresh token")
        return SimpleNamespace(session=self.auth_session, user=self.user)

class TireMonitoringTests(unittest.TestCase):
    def test_tire_date_and_percentage_validation(self):
        self.assertEqual(web_app._tire_date("2026-10-19", "date_installed", True), "2026-10-19")
        with self.assertRaisesRegex(ValueError, "valid date"):
            web_app._tire_date("19/10/2026", "date_installed", True)
        self.assertEqual(web_app._tire_lifespan_percent({"remaining_lifespan_pct": "82.5"}), 82.5)
        with self.assertRaisesRegex(ValueError, "percentage between 0 and 100"):
            web_app._tire_lifespan_percent({"remaining_lifespan_pct": 101})

    def test_tire_api_rejects_invalid_pagination_and_install_dates(self):
        with patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ), patch.object(web_app, "get_manager", return_value=SimpleNamespace()):
            client = web_app.app.test_client()
            invalid_page = client.get("/api/tires?page=0")
            self.assertEqual(invalid_page.status_code, 400)

            with client.session_transaction() as browser_session:
                browser_session["csrf_token"] = "test-csrf"
                browser_session["user_id"] = "test-user"
            invalid_date = client.post(
                "/api/tires",
                json={
                    "asset_type": "truck",
                    "vehicle_id": 1,
                    "brand": "Test",
                    "size": "11R22.5",
                    "tire_type": "Steer",
                    "date_installed": "not-a-date",
                },
                headers={"X-CSRF-Token": "test-csrf"},
            )
            self.assertEqual(invalid_date.status_code, 400)
            self.assertIn("valid date", invalid_date.json["error"])

            invalid_percentage = client.post(
                "/api/tires",
                json={
                    "asset_type": "truck",
                    "vehicle_id": 1,
                    "brand": "Test",
                    "size": "11R22.5",
                    "tire_type": "Steer",
                    "date_installed": "2026-10-19",
                    "remaining_lifespan_pct": 101,
                },
                headers={"X-CSRF-Token": "test-csrf"},
            )
            self.assertEqual(invalid_percentage.status_code, 400)
            self.assertIn("percentage between 0 and 100", invalid_percentage.json["error"])
    def test_dispatchers_cannot_replace_or_remove_tire_records(self):
        with patch.dict(
            web_app.app.config, {"TESTING": True, "TEST_AUTH_BYPASS": True}
        ), patch.object(web_app, "_is_dispatcher", return_value=True):
            client = web_app.app.test_client()
            with client.session_transaction() as browser_session:
                browser_session["csrf_token"] = "test-csrf"
                browser_session["user_id"] = "test-user"

            for action in ("replace", "remove"):
                response = client.post(
                    f"/api/tires/12/{action}",
                    json={},
                    headers={"X-CSRF-Token": "test-csrf"},
                )
                self.assertEqual(response.status_code, 403)

    def test_tire_migration_preserves_history_and_enforces_asset_and_role_rules(self):
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "supabase_tire_monitoring_migration.sql"
        )
        with open(migration_path, encoding="utf-8") as migration_file:
            migration = migration_file.read().lower()

        self.assertIn("create table if not exists public.tire_monitoring", migration)
        self.assertIn("references public.vehicles(id) on delete restrict", migration)
        self.assertIn("references public.trailers(id) on delete restrict", migration)
        self.assertIn("tire_monitoring_asset_assignment_check", migration)
        self.assertIn("tire_monitoring_lifecycle_check", migration)
        self.assertIn("remaining_lifespan_pct numeric(5, 2) not null default 100", migration)
        self.assertIn("check (remaining_lifespan_pct between 0 and 100)", migration)
        self.assertIn("create table if not exists public.tire_monitoring_history", migration)
        self.assertIn("create policy tire_monitoring_dispatcher_select", migration)
        self.assertIn("created_by = (select auth.uid())", migration)
        self.assertIn("create or replace function public.replace_tire_monitoring", migration)
        self.assertIn("replaces_tire_id bigint references public.tire_monitoring(id)", migration)
        self.assertIn("add column if not exists replaces_tire_id bigint", migration)
        self.assertLess(
            migration.index("add column if not exists replaces_tire_id bigint"),
            migration.index("on public.tire_monitoring (replaces_tire_id)"),
        )
        self.assertIn(
            "add column if not exists remaining_lifespan_pct numeric(5, 2) not null default 100",
            migration,
        )
        view_definition = migration.split(
            "create or replace view public.tire_monitoring_sheet", 1
        )[1].split("create or replace function public.get_tire_monitoring_summary", 1)[0]
        self.assertNotIn("tire.*", view_definition)
        self.assertLess(
            view_definition.index("null::integer as expected_lifespan_days"),
            view_definition.index("tire.reason"),
        )
        self.assertLess(
            view_definition.index("as plate_number"),
            view_definition.index("tire.remaining_lifespan_pct::numeric as remaining_lifespan_pct"),
        )
        self.assertLess(
            view_definition.index("tire.remaining_lifespan_pct::numeric as remaining_lifespan_pct"),
            view_definition.index("tire.replaces_tire_id"),
        )
        self.assertIn("btrim(p_brand), btrim(p_size), btrim(p_tire_type), old_tire.id", migration)
        self.assertNotIn("drop table", migration)


class FleetManagerTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeSupabaseClient()
        self.manager = FleetManager(client=self.client)

    def test_trailer_without_capacity_is_reviewed_and_cannot_resolve_trip_rate(self):
        self.configure_davao_plas_routes()
        truck = self.manager.add_vehicle("NO-CAP-TRUCK", "Hino", "300", 2024)
        trailer = self.manager.add_trailer(
            "NO-CAP-TRAILER",
            year_model=2007,
            make_model="0",
            mv_file_no="1244-00000043278",
            engine_no="NA",
            chassis_no="LTOX111010-048C",
        )
        driver = self.manager.add_driver("No Capacity Driver", "NO-CAP-DL")

        self.assertIsNone(trailer["pallet_capacity"])
        self.assertTrue(trailer["capacity_review_required"])
        with self.assertRaisesRegex(FleetManagementError, "valid pallet capacity"):
            self.manager.add_trip(
                truck["id"], driver["id"], "DAV1 to PLAS", 0, 0,
                origin="DAV1", destination="PLAS",
                require_truck_rate=True, trailer_id=trailer["id"],
            )

    def configure_route(self, route_number, origin, destination, route_pair, rates):
        route_id = route_number
        self.client.tables.setdefault("truck_routes", []).append({
            "id": route_id,
            "route_number": route_number,
            "origin_code": origin,
            "destination_code": destination,
            "origin_name": origin,
            "destination_name": destination,
            "route_pair": route_pair,
            "active": True,
        })
        route_rates = self.client.tables.setdefault("truck_route_rates", [])
        for capacity, amount in rates.items():
            route_rates.append({
                "id": len(route_rates) + 1,
                "route_id": route_id,
                "origin_code": origin,
                "destination_code": destination,
                "pallet_capacity": capacity,
                "hauling_rate": amount,
                "active": True,
            })

    def configure_davao_plas_routes(self):
        self.configure_route(3, "DAV1", "PLAS", "DAV1 ↔ PLAS", {36: "1847.00", 46: "2300.00"})
        self.configure_route(2, "DAV1", "DAV2", "DAV2 ↔ DAV1", {36: None, 46: "2300.00"})
        self.configure_route(11, "PLAS", "DAV2", "DAV2 ↔ PLAS", {36: "1847.00", 46: "2200.00"})
        self.configure_route(7, "GENSAN", "DAV2", "GENSAN ↔ DAV2", {36: "11000.00", 46: "14000.00"})

    def configure_all_routes(self):
        route_records = [
            (1, "DAV1", "GENSAN", "GENSAN ↔ DAV1", "12284.85", "15500.00"),
            (2, "DAV1", "DAV2", "DAV2 ↔ DAV1", None, "2300.00"),
            (3, "DAV1", "PLAS", "DAV1 ↔ PLAS", "1847.00", "2300.00"),
            (4, "DAV2", "GENSAN", "GENSAN ↔ DAV2", "11000.00", "14000.00"),
            (5, "DAV2", "DAV1", "DAV2 ↔ DAV1", None, "2300.00"),
            (6, "DAV2", "PLAS", "DAV2 ↔ PLAS", "1847.00", "2200.00"),
            (7, "GENSAN", "DAV2", "GENSAN ↔ DAV2", "11000.00", "14000.00"),
            (8, "GENSAN", "DAV1", "GENSAN ↔ DAV1", "12284.85", "15500.00"),
            (9, "GENSAN", "PLAS", "GENSAN ↔ PLAS", "11000.00", "14000.00"),
            (10, "PLAS", "GENSAN", "GENSAN ↔ PLAS", "11000.00", "14000.00"),
            (11, "PLAS", "DAV2", "DAV2 ↔ PLAS", "1847.00", "2200.00"),
            (12, "PLAS", "DAV1", "DAV1 ↔ PLAS", "1847.00", "2300.00"),
        ]
        for number, origin, destination, pair, rate36, rate46 in route_records:
            self.configure_route(
                number,
                origin,
                destination,
                pair,
                {36: rate36, 46: rate46},
            )

    def test_all_directional_routes_resolve_capacity_specific_rates(self):
        self.configure_all_routes()
        self.assertEqual(len(self.manager.list_truck_routes()), 12)
        self.assertEqual(len(self.manager.list_truck_route_rates()), 24)
        expected = {
            ("DAV1", "GENSAN", 36): "12284.85",
            ("DAV1", "GENSAN", 46): "15500.00",
            ("DAV1", "DAV2", 36): None,
            ("DAV1", "DAV2", 46): "2300.00",
            ("DAV1", "PLAS", 36): "1847.00",
            ("DAV1", "PLAS", 46): "2300.00",
            ("DAV2", "GENSAN", 36): "11000.00",
            ("DAV2", "GENSAN", 46): "14000.00",
            ("DAV2", "DAV1", 36): None,
            ("DAV2", "DAV1", 46): "2300.00",
            ("DAV2", "PLAS", 36): "1847.00",
            ("DAV2", "PLAS", 46): "2200.00",
            ("GENSAN", "DAV2", 36): "11000.00",
            ("GENSAN", "DAV2", 46): "14000.00",
            ("GENSAN", "DAV1", 36): "12284.85",
            ("GENSAN", "DAV1", 46): "15500.00",
            ("GENSAN", "PLAS", 36): "11000.00",
            ("GENSAN", "PLAS", 46): "14000.00",
            ("PLAS", "GENSAN", 36): "11000.00",
            ("PLAS", "GENSAN", 46): "14000.00",
            ("PLAS", "DAV2", 36): "1847.00",
            ("PLAS", "DAV2", 46): "2200.00",
            ("PLAS", "DAV1", 36): "1847.00",
            ("PLAS", "DAV1", 46): "2300.00",
        }
        for key, expected_rate in expected.items():
            with self.subTest(route=key):
                result = self.manager.resolve_truck_route_rate(*key[:2], key[2])
                self.assertEqual(
                    str(result) if result is not None else None,
                    expected_rate,
                )

    def test_new_trip_requires_a_configured_rate_and_snapshots_it(self):
        self.configure_all_routes()
        truck = self.manager.add_vehicle("RATE-TRUCK", "Toyota", "Hiace", 2024)
        second_truck = self.manager.add_vehicle("RATE-TRUCK-2", "Hino", "300", 2023)
        trailer = self.manager.add_trailer("RATE-TRAILER-36", 36)
        driver = self.manager.add_driver("Rate Driver", "RATE-DL")
        with self.assertRaisesRegex(FleetManagementError, "Rate not configured"):
            self.manager.add_trip(
                truck["id"], driver["id"], "DAV1 to DAV2", 0, 0,
                origin="DAV1", destination="DAV2", require_truck_rate=True,
                trailer_id=trailer["id"],
            )
        self.assertEqual(self.client.tables.get("trips", []), [])

        self.manager.update_trailer(
            trailer["id"],
            {
                "plate_number": "RATE-TRAILER-36",
                "pallet_capacity": 46,
                "trailer_type": None,
                "status": "active",
                "remarks": None,
            },
        )
        trip = self.manager.add_trip(
            truck["id"], driver["id"], "DAV1 to DAV2", 0, 0,
            origin="DAV1", destination="DAV2", require_truck_rate=True,
            trailer_id=trailer["id"],
        )
        self.assertEqual(trip["route_number"], 2)
        self.assertEqual(trip["route_pair"], "DAV2 ↔ DAV1")
        self.assertEqual(trip["pallet_capacity"], 46)
        self.assertEqual(trip["truck_route_rate"], "2300.00")
        self.assertFalse(trip["trip_rate_review_required"])
        trip_details = self.manager.get_trip(trip["id"])
        self.assertEqual(trip_details["truck_plate_number"], "RATE-TRUCK")

        rate_row = next(
            row for row in self.client.tables["truck_route_rates"]
            if row["origin_code"] == "DAV1"
            and row["destination_code"] == "DAV2"
            and row["pallet_capacity"] == 46
        )
        rate_row["hauling_rate"] = "2700.00"
        updated = self.manager.update_trip(
            trip["id"],
            {
                "ism_no": None,
                "shipment_date": "2026-10-09",
                "time_in": None,
                "time_out": None,
                "origin": "DAV1",
                "destination": "DAV2",
                "vehicle_id": second_truck["id"],
                "truck_id": second_truck["id"],
                "trailer_id": trailer["id"],
                "driver_id": driver["id"],
                "load_details": None,
                "trip_fuel": None,
                "notes": "Date-only change",
                "route": "DAV1 to DAV2",
            },
            edited_by="admin",
            editor_email=None,
        )
        self.assertEqual(updated["truck_route_rate"], "2300.00")
        self.assertEqual(updated["pallet_capacity"], 46)
        self.assertEqual(updated["truck_id"], second_truck["id"])
        next(
            row for row in self.client.tables["vehicles"]
            if row["id"] == second_truck["id"]
        )["status"] = "maintenance"
        unchanged_assignment = self.manager.update_trip(
            trip["id"],
            {
                "ism_no": None,
                "shipment_date": "2026-10-10",
                "time_in": None,
                "time_out": None,
                "origin": "DAV1",
                "destination": "DAV2",
                "vehicle_id": second_truck["id"],
                "truck_id": second_truck["id"],
                "trailer_id": trailer["id"],
                "driver_id": driver["id"],
                "load_details": None,
                "trip_fuel": None,
                "notes": "Inactive truck history only",
                "route": "DAV1 to DAV2",
            },
            edited_by="admin",
            editor_email=None,
        )
        self.assertEqual(unchanged_assignment["truck_route_rate"], "2300.00")
        self.manager.update_trailer(
            trailer["id"],
            {
                "plate_number": "RATE-TRAILER-36",
                "pallet_capacity": 36,
                "trailer_type": None,
                "status": "active",
                "remarks": None,
            },
        )
        self.assertEqual(self.manager.list_trips()[0]["pallet_capacity"], 46)
        self.manager.update_trailer(
            trailer["id"],
            {
                "plate_number": "RATE-TRAILER-36",
                "pallet_capacity": 46,
                "trailer_type": None,
                "status": "active",
                "remarks": None,
            },
        )

        rerouted = self.manager.update_trip(
            trip["id"],
            {
                "ism_no": None,
                "shipment_date": "2026-10-09",
                "time_in": None,
                "time_out": None,
                "origin": "DAV2",
                "destination": "PLAS",
                "vehicle_id": truck["id"],
                "truck_id": truck["id"],
                "trailer_id": trailer["id"],
                "driver_id": driver["id"],
                "load_details": None,
                "trip_fuel": None,
                "notes": None,
                "route": "DAV2 to PLAS",
            },
            edited_by="admin",
            editor_email=None,
        )
        self.assertEqual(rerouted["route_number"], 6)
        self.assertEqual(rerouted["truck_route_rate"], "2200.00")

        trailer_36 = self.manager.add_trailer("RATE-TRAILER-ALT", 36)
        reassigned = self.manager.update_trip(
            trip["id"],
            {
                "ism_no": None,
                "shipment_date": "2026-10-09",
                "time_in": None,
                "time_out": None,
                "origin": "DAV2",
                "destination": "PLAS",
                "vehicle_id": truck["id"],
                "truck_id": truck["id"],
                "trailer_id": trailer_36["id"],
                "driver_id": driver["id"],
                "load_details": None,
                "trip_fuel": None,
                "notes": None,
                "route": "DAV2 to PLAS",
            },
            edited_by="admin",
            editor_email=None,
        )
        self.assertEqual(reassigned["pallet_capacity"], 36)
        self.assertEqual(reassigned["truck_route_rate"], "1847.00")

    def test_trips_reject_missing_or_inactive_truck_and_trailer(self):
        self.configure_davao_plas_routes()
        truck = self.manager.add_vehicle("VALIDATION-TRUCK", "Hino", "300", 2024)
        inactive_trailer = self.manager.add_trailer(
            "VALIDATION-INACTIVE-TRAILER", 36, status="maintenance"
        )
        driver = self.manager.add_driver("Validation Driver", "VALIDATION-DL")
        with self.assertRaisesRegex(FleetManagementError, "trailer is inactive"):
            self.manager.add_trip(
                truck["id"], driver["id"], "DAV1 to PLAS", 0, 0,
                origin="DAV1", destination="PLAS",
                require_truck_rate=True, trailer_id=inactive_trailer["id"],
            )
        with self.assertRaisesRegex(FleetManagementError, "existing active trailer"):
            self.manager.add_trip(
                truck["id"], driver["id"], "DAV1 to PLAS", 0, 0,
                origin="DAV1", destination="PLAS",
                require_truck_rate=True, trailer_id=9999,
            )

        next(
            row for row in self.client.tables["trailers"]
            if row["id"] == inactive_trailer["id"]
        )["status"] = "active"
        next(
            row for row in self.client.tables["vehicles"]
            if row["id"] == truck["id"]
        )["status"] = "maintenance"
        with self.assertRaisesRegex(FleetManagementError, "truck is inactive"):
            self.manager.add_trip(
                truck["id"], driver["id"], "DAV1 to PLAS", 0, 0,
                origin="DAV1", destination="PLAS",
                require_truck_rate=True, trailer_id=inactive_trailer["id"],
            )

    def test_add_vehicle_driver_and_assignment(self):
        vehicle = self.manager.add_vehicle("ABC-123", "Toyota", "Hiace", 2022, "White")
        driver = self.manager.add_driver("Jane Doe", "DL-1001", phone="555-0100")
        assignment = self.manager.assign_vehicle(
            driver["id"], vehicle["id"], "2026-10-03"
        )
        listed = self.manager.list_assignments()

        self.assertEqual(vehicle["plate_number"], "ABC-123")
        self.assertEqual(driver["name"], "Jane Doe")
        self.assertEqual(assignment["driver_id"], driver["id"])
        self.assertEqual(listed[0]["driver_name"], "Jane Doe")
        self.assertEqual(listed[0]["plate_number"], "ABC-123")
        self.assertEqual(self.manager.get_vehicle(vehicle["id"])["status"], "assigned")

    def test_trip_and_maintenance_and_fuel_tracking(self):
        vehicle = self.manager.add_vehicle("XYZ-988", "Mercedes", "Sprinter", 2021, "Blue")
        driver = self.manager.add_driver("John Smith", "DL-9988")

        trip = self.manager.add_trip(
            vehicle["id"], driver["id"], "Accra to Kumasi", 15000, 15375,
            "2026-10-02", "Routine delivery route",
        )
        maintenance = self.manager.add_maintenance(
            vehicle["id"], "service", "Oil change", 120.0
        )
        fuel = self.manager.add_fuel(vehicle["id"], "diesel", 80, 15.5)

        self.assertEqual(trip["route"], "Accra to Kumasi")
        self.assertEqual(maintenance["service_type"], "service")
        self.assertEqual(fuel["total_cost"], 1240.0)
        self.assertEqual(self.manager.dashboard()["recent_trips"], 1)
        self.assertEqual(self.manager.dashboard()["total_fuel_spend"], 1240.0)
        self.assertEqual(self.manager.get_vehicle(vehicle["id"])["odometer"], 15375)

    def test_imported_trip_without_vehicle_or_driver_ids_displays_source_fields(self):
        self.client.tables["trips"] = [{
            "id": 1,
            "vehicle_id": None,
            "driver_id": None,
            "record_date": "2026-09-28",
            "ism_no": "31946326",
            "shipment_date": "2026-09-27",
            "time_in": "10:27:00",
            "time_out": None,
            "origin": "GENSAN",
            "destination": "DAV2",
            "plate_no": "MUB289",
            "load_details": "1P",
            "driver_name": "SALCEDA",
            "trip_fuel": "1ST-105 INV12125 9.27",
            "route": "GENSAN to DAV2",
            "trip_date": "2026-09-27",
        }]

        trip = self.manager.list_trips()[0]
        self.assertEqual(trip["plate_number"], "MUB289")
        self.assertEqual(trip["driver_name"], "SALCEDA")

    def test_trip_and_fuel_enrichment_reads_only_linked_records(self):
        self.client.tables["trips"] = [
            {
                "id": 1,
                "created_by": "dispatcher-1",
                "ism_no": "OWN-TRIP",
                "origin": "DAV1",
                "destination": "PLAS",
                "route_number": 3,
            },
            {
                "id": 2,
                "created_by": "dispatcher-2",
                "ism_no": "OTHER-TRIP",
                "origin": "DAV2",
                "destination": "PLAS",
                "route_number": 6,
            },
        ]
        self.client.tables["fuel_logs"] = [
            {
                "id": 11,
                "trip_id": 1,
                "created_by": "dispatcher-1",
                "fuel_allocation": 350,
                "actual_expense": 200,
                "remarks": "Own fuel",
            },
            {
                "id": 12,
                "trip_id": 2,
                "created_by": "dispatcher-2",
                "fuel_allocation": 500,
                "actual_expense": 450,
            },
        ]

        trip = self.manager.list_trips(user_id="dispatcher-1")[0]
        fuel_queries = [
            query for query in self.client.query_log
            if query["table"] == "fuel_logs" and query["action"] == "select"
        ]
        self.assertEqual(trip["fuel_id"], 11)
        self.assertEqual(trip["fuel_allocation"], 350)
        self.assertEqual(len(fuel_queries), 1)
        self.assertIn(("in", "trip_id", [1]), fuel_queries[0]["filters"])
        self.assertEqual(
            fuel_queries[0]["columns"],
            "id,trip_id,fuel_allocation,actual_expense,remarks,invoice_object_path",
        )

        self.client.query_log.clear()
        fuel = self.manager.list_fuel_logs(user_id="dispatcher-1")[0]
        linked_trip_queries = [
            query for query in self.client.query_log
            if query["table"] == "trips" and query["action"] == "select"
        ]
        self.assertEqual(fuel["trip_ism_no"], "OWN-TRIP")
        self.assertEqual(len(linked_trip_queries), 1)
        self.assertIn(("in", "id", [1]), linked_trip_queries[0]["filters"])
        self.assertIn(("created_by", "dispatcher-1"), linked_trip_queries[0]["filters"])

    def test_trip_date_range_is_filtered_in_the_database_query(self):
        self.client.tables["trips"] = [
            {"id": 1, "shipment_date": "2026-10-01", "ism_no": "IN-RANGE"},
            {"id": 2, "shipment_date": "2026-11-01", "ism_no": "OUT-OF-RANGE"},
        ]

        trips = self.manager.list_trips(
            include_fuel=False,
            start_date="2026-10-01",
            end_date="2026-10-31",
        )

        self.assertEqual([trip["ism_no"] for trip in trips], ["IN-RANGE"])
        trips_query = next(
            query for query in self.client.query_log
            if query["table"] == "trips" and query["action"] == "select"
        )
        self.assertIn(("gte", "shipment_date", "2026-10-01"), trips_query["filters"])
        self.assertIn(("lte", "shipment_date", "2026-10-31"), trips_query["filters"])

    def test_export_report(self):
        self.manager.add_vehicle("ZZZ-001", "Ford", "Transit", 2023)
        self.manager.add_driver("Esther Kofi", "DL-4411")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "report.xlsx")
            result = self.manager.export_report(output_path)
            self.assertTrue(os.path.exists(result["output_path"]))
            self.assertGreater(result["records_written"], 0)
            workbook = load_workbook(output_path, data_only=True)
            self.assertEqual(workbook["Vehicles"]["B5"].value, "ZZZ-001")

    def test_web_export_returns_preformatted_system_wide_excel_workbook(self):
        vehicle = self.manager.add_vehicle("XLS-001", "Toyota", "Hiace", 2024)
        driver = self.manager.add_driver("Excel Driver", "XLS-DL-1")
        self.manager.assign_vehicle(driver["id"], vehicle["id"])
        self.manager.add_maintenance(
            vehicle["id"], "Service", '=HYPERLINK("https://example.com","Open")', 1250.5
        )
        self.manager.add_fuel(vehicle["id"], "Diesel", 50, 60.25)
        self.manager.add_trip(
            vehicle["id"], driver["id"], "Manila to Cavite", 100, 150,
            origin="Manila", destination="Cavite",
        )
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)

        response = client.get("/api/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("fleet_system_report.xlsx", response.headers["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        self.assertEqual(
            workbook.sheetnames,
            ["Dashboard", "Vehicles", "Trailers", "Drivers", "Assignments", "Maintenance", "Fuel Logs", "Trips"],
        )
        vehicles = workbook["Vehicles"]
        self.assertEqual(vehicles["B4"].value, "Plate Number")
        self.assertEqual(vehicles["B5"].value, "XLS-001")
        self.assertEqual(vehicles.freeze_panes, "A5")
        self.assertEqual(vehicles.auto_filter.ref, "A4:K5")
        self.assertEqual(workbook["Fuel Logs"]["G5"].value, 3012.5)
        self.assertIn("₱", workbook["Fuel Logs"]["G5"].number_format)
        self.assertEqual(workbook["Maintenance"]["E5"].data_type, "s")
        self.assertEqual(workbook["Trips"]["G5"].value, "Manila")

    def test_web_trip_history_export_returns_trip_details_as_excel(self):
        vehicle = self.manager.add_vehicle("TRIP-XLS-1", "Toyota", "Hiace", 2024)
        driver = self.manager.add_driver("Trip Export Driver", "TRIP-DL-1")
        self.manager.add_trip(
            vehicle["id"],
            driver["id"],
            "Manila to Cavite",
            100,
            150,
            ism_no="ISM-TRIP-1",
            shipment_date="2026-10-05",
            time_in="08:15",
            time_out="10:30",
            origin="Manila",
            destination="Cavite",
            load_details="12 cartons",
            trip_fuel="Diesel",
        )
        self.client.tables["trips"][0].update({
            "route_number": 3,
            "route_pair": "DAV1 ↔ PLAS",
            "pallet_capacity": 36,
            "truck_route_rate": "1847.00",
            "trip_rate_review_required": False,
        })
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)

        response = client.get("/api/export/trips")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("trip_history.xlsx", response.headers["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        self.assertEqual(workbook.sheetnames, ["Trip History"])
        trips = workbook["Trip History"]
        self.assertEqual(trips["B4"].value, "Ism No")
        self.assertEqual(trips["B5"].value, "ISM-TRIP-1")
        self.assertEqual(trips["F5"].value, "Manila")
        self.assertEqual(trips["H5"].value, "TRIP-XLS-1")
        self.assertEqual(trips["K5"].value, "Trip Export Driver")
        self.assertEqual(trips["C5"].number_format, "yyyy-mm-dd")
        self.assertEqual(trips["D5"].number_format, "hh:mm")
        self.assertEqual(trips.freeze_panes, "A5")
        self.assertEqual(trips.auto_filter.ref, "A4:Y5")
        self.assertEqual(trips["Q5"].value, 1847)
        self.assertIn("₱", trips["Q5"].number_format)

    def test_web_trip_history_export_uses_selected_group_and_search(self):
        vehicle = self.manager.add_vehicle("TRIP-XLS-2", "Toyota", "Hiace", 2024)
        first_driver = self.manager.add_driver("Alpha Driver", "TRIP-DL-2")
        second_driver = self.manager.add_driver("Beta Driver", "TRIP-DL-3")
        self.manager.add_trip(
            vehicle["id"],
            first_driver["id"],
            "Manila to Cavite",
            100,
            150,
            ism_no="MATCH-TRIP",
            origin="Manila",
            destination="Cavite",
        )
        self.manager.add_trip(
            vehicle["id"],
            second_driver["id"],
            "Cavite to Manila",
            150,
            200,
            ism_no="OTHER-TRIP",
            origin="Cavite",
            destination="Manila",
        )
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)

        response = client.get(
            "/api/export/trips?group_by=driver_name&search=MATCH-TRIP"
        )

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        self.assertEqual(workbook.sheetnames, ["Alpha Driver"])
        self.assertEqual(workbook["Alpha Driver"]["B5"].value, "MATCH-TRIP")

    def test_cli_export_report_defaults_to_excel_file(self):
        from fleet_management import _build_cli

        args = _build_cli().parse_args(["export-report"])
        self.assertEqual(args.output, "fleet_system_report.xlsx")

    def test_missing_supabase_configuration_is_reported(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(FleetManagementError, "SUPABASE_URL"):
                FleetManager()

    def test_supabase_rest_endpoint_is_normalized_to_project_url(self):
        self.assertEqual(
            _supabase_project_url("https://project-ref.supabase.co/rest/v1/"),
            "https://project-ref.supabase.co",
        )

    def test_supabase_client_receives_normalized_url(self):
        with patch("fleet_management.create_client") as create_client:
            FleetManager(
                url="https://project-ref.supabase.co/rest/v1/",
                key="test-key",
            )
        create_client.assert_called_once_with(
            "https://project-ref.supabase.co", "test-key"
        )

    def test_dns_error_nested_in_transport_exception_gets_actionable_message(self):
        class BrokenQuery:
            def execute(self):
                try:
                    raise OSError(11001, "getaddrinfo failed")
                except OSError as cause:
                    raise RuntimeError("request transport failed") from cause

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://project-ref.supabase.co"},
        ):
            with self.assertRaisesRegex(
                FleetManagementError, "Could not resolve the Supabase server"
            ):
                self.manager._execute(BrokenQuery())

    def test_missing_trip_migration_has_actionable_error(self):
        class UnmigratedTripsQuery:
            def execute(self):
                raise RuntimeError(
                    "{'message': 'column trips.shipment_date does not exist', "
                    "'code': '42703'}"
                )

        with self.assertRaisesRegex(
            FleetManagementError, "supabase_trips_migration.sql"
        ):
            self.manager._execute(UnmigratedTripsQuery())

    def test_missing_fuel_trip_link_migration_has_actionable_error(self):
        class UnmigratedFuelAllocationQuery:
            def execute(self):
                raise RuntimeError(
                    "{'message': 'column fuel_logs.trip_id does not exist', "
                    "'code': '42703'}"
                )

        with self.assertRaisesRegex(
            FleetManagementError, "supabase_fuel_allocation_migration.sql"
        ):
            self.manager._execute(UnmigratedFuelAllocationQuery())

    def test_missing_route_rate_migration_has_actionable_error(self):
        class UnmigratedRouteRatesQuery:
            def execute(self):
                raise RuntimeError(
                    "{'message': 'column trips.route_id does not exist', "
                    "'code': '42703'}"
                )

        with self.assertRaisesRegex(
            FleetManagementError, "supabase_route_trip_rate_migration.sql"
        ):
            self.manager._execute(UnmigratedRouteRatesQuery())

    def test_outdated_payroll_finalization_function_has_actionable_error(self):
        class OutdatedPayrollFunctionQuery:
            def execute(self):
                raise RuntimeError(
                    "{'message': 'function hashtextext(text) does not exist', "
                    "'code': '42883'}"
                )

        with self.assertRaisesRegex(
            FleetManagementError,
            "updated supabase_payroll_migration.sql",
        ):
            self.manager._execute(OutdatedPayrollFunctionQuery())

    def test_web_dashboard_and_vehicle_form_use_supabase_manager(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.configure_davao_plas_routes()

        self.sign_in(client)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<!doctype html>", response.data.lower())
        self.assertIn(b"/static/app.js", response.data)
        response.close()

        response = client.post(
            "/api/vehicles",
            json={
                "plate_number": "WEB-123",
                "make": "Toyota",
                "model": "Hiace",
                "year": 2022,
            },
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["plate_number"], "WEB-123")

        invalid_trailer = client.post(
            "/api/trailers",
            json={
                "plate_number": "WEB-TRAILER-BAD",
                "pallet_capacity": 36.5,
                "status": "active",
            },
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(invalid_trailer.status_code, 400)
        trailer_response = client.post(
            "/api/trailers",
            json={
                "plate_number": "WEB-TRAILER",
                "pallet_capacity": 36,
                "status": "active",
            },
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(trailer_response.status_code, 201)
        trailer = trailer_response.json["data"]
        driver = self.manager.add_driver("Web Driver", "WEB-DL-1")
        vehicle = self.manager.list_vehicles()[0]
        response = client.post(
            "/api/trips",
            json={
                "ism_no": "ISM-008",
                "shipment_date": "2026-10-03",
                "time_in": "08:15",
                "time_out": "09:40",
                "origin": "DAV1",
                "destination": "PLAS",
                "truck_id": vehicle["id"],
                "trailer_id": trailer["id"],
                "driver_id": driver["id"],
                "load_details": "12 cartons",
                "trip_fuel": "Diesel",
                "fuel_allocation": 250,
                "actual_fuel_expense": 0,
            },
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["ism_no"], "ISM-008")
        self.assertEqual(response.json["data"]["origin"], "DAV1")
        self.assertEqual(response.json["data"]["time_in"], "08:15")
        self.assertEqual(response.json["data"]["trip_fuel"], "Diesel")
        self.assertEqual(response.json["data"]["route_number"], 3)
        self.assertEqual(response.json["data"]["pallet_capacity"], 36)
        self.assertEqual(response.json["data"]["truck_route_rate"], "1847.00")
        self.assertEqual(response.json["data"]["fuel_log"]["fuel_allocation"], 250)
        self.assertEqual(response.json["data"]["fuel_log"]["actual_expense"], 0)
        unconfigured_rate = client.post(
            "/api/trips",
            json={
                "shipment_date": "2026-10-04",
                "origin": "DAV1",
                "destination": "DAV2",
                "truck_id": vehicle["id"],
                "trailer_id": trailer["id"],
                "vehicle_id": vehicle["id"],
                "driver_id": driver["id"],
            },
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(unconfigured_rate.status_code, 400)
        self.assertIn("Rate not configured", unconfigured_rate.json["error"])

        response = client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["vehicles"][0]["plate_number"], "WEB-123")
        self.assertEqual(response.json["dashboard"]["total_vehicles"], 1)
        self.assertEqual(response.json["dashboard"]["active_drivers"], 1)
        self.assertEqual(response.json["dashboard"]["recent_trips"], 1)
        trip = response.json["trips"][0]
        self.assertEqual(trip["shipment_date"], "2026-10-03")
        self.assertEqual(trip["plate_number"], "WEB-123")
        self.assertEqual(trip["driver_name"], "Web Driver")
        self.assertEqual(trip["truck_route_rate"], "1847.00")
        self.assertEqual(len(response.json["truck_routes"]), 4)
        self.assertEqual(response.json["trips"][0]["trailer_plate_number"], "WEB-TRAILER")

    def test_admin_can_edit_existing_trailer_and_dispatcher_cannot(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)
        csrf = self.csrf_token(client)

        created = client.post(
            "/api/trailers",
            json={
                "plate_number": "EDIT-TRAILER-1",
                "year_model": 2007,
                "make_model": "0",
                "mv_file_no": "1244-00000043278",
                "engine_no": "NA",
                "chassis_no": "LTOX111010-048C",
                "status": "active",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(created.status_code, 201)
        trailer_id = created.json["data"]["id"]
        self.assertIsNone(created.json["data"]["pallet_capacity"])
        self.assertTrue(created.json["data"]["capacity_review_required"])

        updated = client.patch(
            f"/api/trailers/{trailer_id}",
            json={
                "plate_number": "EDIT-TRAILER-UPDATED",
                "year_model": 2008,
                "make_model": "Updated model",
                "mv_file_no": "MV-UPDATED-001",
                "engine_no": "ENGINE-UPDATED",
                "chassis_no": "CHASSIS-UPDATED",
                "pallet_capacity": 46,
                "trailer_type": "Flatbed",
                "status": "active",
                "remarks": "Capacity verified",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["data"]["plate_number"], "EDIT-TRAILER-UPDATED")
        self.assertEqual(updated.json["data"]["year_model"], 2008)
        self.assertEqual(updated.json["data"]["pallet_capacity"], 46)
        self.assertFalse(updated.json["data"]["capacity_review_required"])
        self.assertEqual(updated.json["data"]["remarks"], "Capacity verified")
        persisted = self.manager.list_trailers()[0]
        self.assertEqual(persisted["mv_file_no"], "MV-UPDATED-001")
        self.assertEqual(persisted["engine_no"], "ENGINE-UPDATED")
        self.assertEqual(persisted["chassis_no"], "CHASSIS-UPDATED")

        dispatcher_auth = FakeAuthClient()
        dispatcher_auth.user.user_metadata = {"role": "dispatcher"}
        dispatcher_client = web_app.app.test_client()
        self.sign_in(dispatcher_client, dispatcher_auth)
        dispatcher_response = dispatcher_client.patch(
            f"/api/trailers/{trailer_id}",
            json={
                "plate_number": "UNAUTHORIZED-EDIT",
                "pallet_capacity": 36,
                "status": "active",
            },
            headers={"X-CSRF-Token": self.csrf_token(dispatcher_client)},
        )
        self.assertEqual(dispatcher_response.status_code, 403)
        self.assertEqual(
            self.manager.list_trailers()[0]["plate_number"],
            "EDIT-TRAILER-UPDATED",
        )

    def test_dispatcher_is_limited_to_owned_records_and_allowed_endpoints(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        vehicle = self.manager.add_vehicle("DSP-123", "Toyota", "Hiace", 2022)
        driver = self.manager.add_driver("Dispatcher Driver", "DSP-DL-1")
        own_trip = self.manager.add_trip(
            vehicle["id"], driver["id"], "Origin to Destination", 0, 0,
            ism_no="DSP-OWN", origin="Origin", destination="Destination",
            created_by="auth-user-1",
        )
        self.manager.add_trip(
            vehicle["id"], driver["id"], "Other to Route", 0, 0,
            ism_no="OTHER-TRIP", origin="Other", destination="Route",
            created_by="another-dispatcher",
        )
        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {"role": "dispatcher", "full_name": "Dispatch User"}
        auth_client.user.app_metadata = {"role": "administrator"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)

        bootstrap = client.get("/api/bootstrap")
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(bootstrap.json["user"]["role"], "dispatcher")
        self.assertEqual([row["id"] for row in bootstrap.json["trips"]], [own_trip["id"]])
        self.assertEqual(bootstrap.json["dashboard"]["total_trips"], 1)
        self.assertNotIn("total_vehicles", bootstrap.json["dashboard"])
        self.assertEqual(
            bootstrap.json["drivers"],
            [{"id": driver["id"], "name": "Dispatcher Driver", "status": "active"}],
        )

        csrf = bootstrap.json["csrf_token"]
        denied_vehicle_create = client.post(
            "/api/vehicles",
            json={"plate_number": "DENIED", "make": "Toyota", "model": "Hiace", "year": 2022},
            headers={"X-CSRF-Token": csrf},
        )
        denied_vehicle_list = client.get("/api/vehicles")
        denied_capacity_update = client.patch(
            f"/api/vehicles/{vehicle['id']}/capacity",
            json={"pallet_capacity": 46},
            headers={"X-CSRF-Token": csrf},
        )
        denied_driver_list = client.get("/api/drivers")
        denied_payroll = client.get("/api/payroll?start_date=2026-10-01&end_date=2026-10-31")
        denied_export = client.get("/api/export")
        denied_delete = client.delete(
            f"/api/trips/{own_trip['id']}",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(denied_vehicle_create.status_code, 403)
        self.assertEqual(denied_vehicle_list.status_code, 403)
        self.assertEqual(denied_capacity_update.status_code, 403)
        self.assertEqual(denied_driver_list.status_code, 403)
        self.assertEqual(denied_payroll.status_code, 403)
        self.assertEqual(denied_export.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        created_trip = client.post(
            "/api/trips",
            json={
                "ism_no": "DSP-NEW",
                "shipment_date": "2026-10-03",
                "origin": "Origin",
                "destination": "Destination",
                "vehicle_id": vehicle["id"],
                "driver_id": driver["id"],
                "created_by": "another-dispatcher",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(created_trip.status_code, 403)
        self.assertIn("Departure", created_trip.json["error"])
        self.assertEqual(len(self.manager.list_trips(user_id="auth-user-1")), 1)

    def test_dispatcher_cannot_upload_legacy_trip_manifest(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        vehicle = self.manager.add_vehicle("DOC-123", "Toyota", "Hiace", 2022)
        driver = self.manager.add_driver("Document Driver", "DOC-DL-1")
        trip = self.manager.add_trip(
            vehicle["id"], driver["id"], "Origin to Destination", 0, 0,
            ism_no="DOC-TRIP", origin="Origin", destination="Destination",
            created_by="auth-user-1",
        )

        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {"role": "dispatcher"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)
        csrf = self.csrf_token(client)

        response = client.post(
            f"/api/trips/{trip['id']}/manifest",
            data={"image": (BytesIO(b"legacy manifest"), "manifest.png")},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Departure", response.json["error"])
        self.assertFalse(self.client.tables.get("notifications"))

    def test_dispatcher_cannot_edit_legacy_trip_but_can_view_its_history(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        self.configure_davao_plas_routes()
        vehicle = self.manager.add_vehicle("EDIT-123", "Toyota", "Hiace", 2022)
        trailer = self.manager.add_trailer("EDIT-TRAILER", 36)
        driver = self.manager.add_driver("Edit Driver", "EDIT-DL-1")
        own_trip = self.manager.add_trip(
            vehicle["id"],
            driver["id"],
            "DAV1 to PLAS",
            0,
            0,
            ism_no="EDIT-TRIP",
            shipment_date="2026-10-01",
            origin="DAV1",
            destination="PLAS",
            trailer_id=trailer["id"],
            require_truck_rate=True,
            created_by="auth-user-1",
        )
        other_trip = self.manager.add_trip(
            vehicle["id"],
            driver["id"],
            "Other Origin to Other Destination",
            0,
            0,
            ism_no="OTHER-EDIT-TRIP",
            created_by="another-dispatcher",
        )
        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {"role": "dispatcher"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)
        csrf = self.csrf_token(client)

        response = client.patch(
            f"/api/trips/{own_trip['id']}",
            json={
                "ism_no": "EDIT-TRIP-UPDATED",
                "shipment_date": "2026-10-02",
                "time_in": "08:00",
                "time_out": "10:00",
                "origin": "GENSAN",
                "destination": "DAV2",
                "truck_id": vehicle["id"],
                "trailer_id": trailer["id"],
                "vehicle_id": vehicle["id"],
                "driver_id": driver["id"],
                "load_details": "Updated load",
                "trip_fuel": "Diesel",
            },
            headers={"X-CSRF-Token": csrf},
        )
        denied = client.patch(
            f"/api/trips/{other_trip['id']}",
            json={
                "ism_no": "NO-ACCESS",
                "shipment_date": "2026-10-02",
                "origin": "No",
                "destination": "Access",
                "vehicle_id": vehicle["id"],
                "driver_id": driver["id"],
            },
            headers={"X-CSRF-Token": csrf},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Departure", response.json["error"])
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            self.manager.get_trip(own_trip["id"])["destination"],
            "PLAS",
        )
        self.manager.client.tables["trip_edit_history"] = [{
            "id": 1,
            "trip_id": own_trip["id"],
            "edited_by": "auth-user-1",
            "edited_by_email": "dispatcher@example.com",
            "edited_at": "2026-10-02T08:00:00+00:00",
            "old_values": {"destination": "Old Destination"},
            "new_values": {"destination": "New Destination"},
        }]
        history = client.get(f"/api/trips/{own_trip['id']}/history")
        denied_history = client.get(f"/api/trips/{other_trip['id']}/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json["history"][0]["edited_by_email"], "dispatcher@example.com")
        self.assertEqual(denied_history.status_code, 403)

    def test_dispatcher_creates_notification_for_each_supported_record_type(self):
        vehicle = self.manager.add_vehicle("NOTIFY-1", "Toyota", "Hiace", 2024)
        trailer = self.manager.add_trailer("NOTIFY-TRAILER", 46)
        self.configure_route(
            7, "GENSAN", "DAV2", "GENSAN ↔ DAV2",
            {36: "11000.00", 46: "14000.00"},
        )
        driver = self.manager.add_driver("Notify Driver", "NOTIFY-DL-1")
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {
            "role": "dispatcher",
            "full_name": "Juan Dela Cruz",
        }
        auth_client.user.app_metadata = {"role": "administrator"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)
        csrf = self.csrf_token(client)

        trip_response = client.post(
            "/api/trips",
            json={
                "ism_no": "31946326",
                "shipment_date": "2026-10-08",
                "origin": "GENSAN",
                "destination": "DAV2",
                "truck_id": vehicle["id"],
                "trailer_id": trailer["id"],
                "vehicle_id": vehicle["id"],
                "driver_id": driver["id"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(trip_response.status_code, 403)

        requests = [
            (
                "fuel",
                {
                    "vehicle_id": vehicle["id"],
                    "fuel_type": "Diesel",
                    "quantity": 50,
                    "price_per_liter": 70,
                    "total_cost": 3500,
                },
                "NEW_FUEL_LOG",
            ),
            (
                "maintenance",
                {
                    "vehicle_id": vehicle["id"],
                    "service_type": "Oil change",
                    "description": "Scheduled service",
                    "cost": 1200,
                },
                "NEW_MAINTENANCE_LOG",
            ),
        ]
        with patch.object(web_app, "_admin_recipient_ids", return_value=["admin-user"]):
            created_records = []
            for resource, payload, expected_type in requests:
                response = client.post(
                    f"/api/{resource}",
                    json=payload,
                    headers={"X-CSRF-Token": csrf},
                )
                self.assertEqual(response.status_code, 201)
                created_records.append((response.json["data"], expected_type))

        notifications = self.client.tables["notifications"]
        self.assertEqual(len(notifications), 2)
        for record, expected_type in created_records:
            matching = [
                item for item in notifications
                if item["record_id"] == str(record["id"])
                and item["notification_type"] == expected_type
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["notification_type"], expected_type)
            self.assertEqual(matching[0]["recipient_user_id"], "admin-user")
            self.assertEqual(matching[0]["actor_user_id"], "auth-user-1")
            self.assertEqual(matching[0]["actor_name"], "Juan Dela Cruz")
            self.assertFalse(matching[0]["is_read"])
        self.assertNotIn(
            "31946326",
            [item.get("ism_no") for item in self.client.tables["trips"]],
        )

    def test_dispatcher_notification_creation_is_idempotent_per_record(self):
        web_app.manager = self.manager
        with patch.object(web_app, "_admin_recipient_ids", return_value=["admin-user"]):
            record = {
                "id": 51,
                "origin": "GENSAN",
                "destination": "DAV2",
                "ism_no": "ISM-51",
            }
            actor = {
                "id": "dispatcher-id",
                "full_name": "Dispatcher",
                "email": "dispatcher@example.com",
            }
            web_app._create_dispatcher_notifications("trips", record, actor)
            web_app._create_dispatcher_notifications("trips", record, actor)

        self.assertEqual(len(self.client.tables["notifications"]), 1)

    def test_admin_notification_api_scopes_records_and_marks_them_read(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        self.client.tables["notifications"] = [
            {
                "id": 1,
                "recipient_user_id": "admin-user",
                "actor_user_id": "dispatcher-id",
                "actor_name": "Maria Santos",
                "actor_email": "maria@example.com",
                "notification_type": "NEW_FUEL_LOG",
                "module": "fuel",
                "record_id": "10",
                "title": "New Fuel Log Added",
                "message": "Vehicle: MUB289",
                "is_read": False,
                "created_at": "2026-10-08T01:10:00+00:00",
                "read_at": None,
            },
            {
                "id": 2,
                "recipient_user_id": "another-admin",
                "actor_user_id": "dispatcher-id",
                "actor_name": "Another Dispatcher",
                "actor_email": "other@example.com",
                "notification_type": "NEW_TRIP",
                "module": "trips",
                "record_id": "11",
                "title": "New Trip Added",
                "message": "GENSAN → DAV2",
                "is_read": False,
                "created_at": "2026-10-08T01:11:00+00:00",
                "read_at": None,
            },
        ]
        auth_client = FakeAuthClient()
        auth_client.user.id = "admin-user"
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)

        listing = client.get(
            "/api/notifications?dispatcher=maria&type=new_fuel_log&date=2026-10-08&status=unread"
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([row["id"] for row in listing.json["notifications"]], [1])
        self.assertEqual(client.get("/api/notifications/unread-count").json["unread_count"], 1)

        read = client.patch(
            "/api/notifications/1/read",
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(read.status_code, 200)
        self.assertTrue(read.json["notification"]["is_read"])
        self.assertTrue(read.json["notification"]["read_at"])
        self.assertEqual(client.get("/api/notifications/unread-count").json["unread_count"], 0)
        self.assertEqual(
            self.client.tables["notifications"][0]["message"],
            "Vehicle: MUB289",
        )
        self.client.tables["notifications"].append({
            "id": 3,
            "recipient_user_id": "admin-user",
            "actor_user_id": "dispatcher-id",
            "actor_name": "Maria Santos",
            "actor_email": "maria@example.com",
            "notification_type": "NEW_TRIP",
            "module": "trips",
            "record_id": "12",
            "title": "New Trip Added",
            "message": "GENSAN → DAV2",
            "is_read": False,
            "created_at": "2026-10-08T01:12:00+00:00",
            "read_at": None,
        })
        read_all = client.patch(
            "/api/notifications/read-all",
            headers={"X-CSRF-Token": self.csrf_token(client)},
        )
        self.assertEqual(read_all.status_code, 200)
        self.assertEqual(read_all.json["updated"], 1)
        self.assertTrue(self.client.tables["notifications"][2]["is_read"])
        self.assertFalse(self.client.tables["notifications"][1]["is_read"])

    def test_dispatcher_cannot_access_admin_notifications(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {"role": "dispatcher"}
        auth_client.user.app_metadata = {"role": "administrator"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)

        self.assertEqual(client.get("/api/notifications").status_code, 403)
        self.assertEqual(client.get("/api/notifications/unread-count").status_code, 403)

    def test_notification_failure_does_not_fail_successful_dispatcher_fuel_record(self):
        vehicle = self.manager.add_vehicle("NOTIFY-FAIL", "Toyota", "Hiace", 2024)
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        auth_client = FakeAuthClient()
        auth_client.user.user_metadata = {"role": "dispatcher"}
        client = web_app.app.test_client()
        self.sign_in(client, auth_client)
        csrf = self.csrf_token(client)

        payload = {
            "vehicle_id": vehicle["id"],
            "fuel_type": "Diesel",
            "quantity": 50,
            "price_per_liter": 70,
            "total_cost": 3500,
        }
        with patch.object(
            self.manager,
            "add_fuel",
            side_effect=FleetManagementError("Fuel log insert failed"),
        ):
            failed_insert = client.post(
                "/api/fuel",
                json=payload,
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(failed_insert.status_code, 503)
        self.assertFalse(self.client.tables.get("notifications"))

        with patch.object(
            web_app, "_admin_recipient_ids", side_effect=RuntimeError("Auth lookup failed")
        ):
            with self.assertLogs(web_app.logger, level="ERROR"):
                response = client.post(
                    "/api/fuel",
                    json=payload,
                    headers={"X-CSRF-Token": csrf},
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.client.tables["fuel_logs"]), 1)
        self.assertFalse(self.client.tables.get("notifications"))

    def test_web_reports_missing_supabase_configuration(self):
        web_app.manager = None
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)
        with patch.dict(os.environ, {}, clear=True):
            response = client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"SUPABASE_URL", response.data)

    def csrf_token(self, client):
        response = client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        return response.json["csrf_token"]

    def sign_in(self, client, auth_client=None):
        patcher = patch.object(
            web_app,
            "get_auth_client",
            return_value=auth_client or FakeAuthClient(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        csrf = client.get("/api/auth/csrf").json["csrf_token"]
        response = client.post(
            "/api/auth/login",
            json={"email": "fleet@example.com", "password": "correct-password"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("HttpOnly", response.headers.get("Set-Cookie", ""))
        cookies = response.headers.getlist("Set-Cookie")
        for name in ("glfs_access_token", "glfs_refresh_token"):
            auth_cookie = next(cookie for cookie in cookies if cookie.startswith(f"{name}="))
            self.assertNotIn("Max-Age=", auth_cookie)
            self.assertNotIn("Expires=", auth_cookie)
        with client.session_transaction() as browser_session:
            self.assertFalse(browser_session.permanent)
            self.assertIn("last_activity", browser_session)
        return response

    def test_app_and_api_require_authentication_but_login_assets_are_public(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()

        self.assertEqual(client.get("/").status_code, 302)
        self.assertEqual(client.get("/api/bootstrap").status_code, 401)
        self.assertEqual(client.get("/static/index.html").status_code, 302)
        login_page = client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        login_page.close()
        login_script = client.get("/static/login.js")
        self.assertEqual(login_script.status_code, 200)
        login_script.close()

    def test_login_rejects_bad_credentials_and_requires_csrf(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        with patch.object(web_app, "get_auth_client", return_value=FakeAuthClient()):
            csrf = client.get("/api/auth/csrf").json["csrf_token"]
            no_csrf = client.post(
                "/api/auth/login",
                json={"email": "fleet@example.com", "password": "correct-password"},
            )
            bad_password = client.post(
                "/api/auth/login",
                json={"email": "fleet@example.com", "password": "wrong-password"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(bad_password.status_code, 401)
        self.assertIn(b"Sign-in failed", bad_password.data)

    def test_login_reports_missing_supabase_anon_key(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        with patch.object(web_app, "_supabase_setting", return_value=None):
            csrf = client.get("/api/auth/csrf").json["csrf_token"]
            response = client.post(
                "/api/auth/login",
                json={"email": "fleet@example.com", "password": "correct-password"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"SUPABASE_ANON_KEY", response.data)

    def test_mutations_require_csrf_and_logout_clears_authenticated_session(self):
        web_app.manager = self.manager
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        auth_client = FakeAuthClient()
        self.sign_in(client, auth_client)
        csrf = self.csrf_token(client)
        payload = {
            "plate_number": "CSRF-1",
            "make": "Toyota",
            "model": "Hiace",
            "year": 2022,
        }
        blocked = client.post("/api/vehicles", json=payload)
        created = client.post(
            "/api/vehicles",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        protected = client.get("/api/bootstrap")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(protected.status_code, 401)

    def test_logout_clears_local_session_without_csrf_token(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)

        response = client.post(
            "/api/auth/logout",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/login", response.json["redirect"])
        self.assertTrue(any(
            "glfs_access_token=;" in cookie
            for cookie in response.headers.getlist("Set-Cookie")
        ))
        self.assertEqual(client.get("/api/bootstrap").status_code, 401)

    def test_expired_access_token_is_refreshed(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        auth_client = FakeAuthClient()
        self.sign_in(client, auth_client)
        auth_client.auth_session.access_token = "refreshed-access-token"
        # The old browser token expires; the refresh token supplies a new one.
        response = client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertIn("refreshed-access-token", response.headers.get("Set-Cookie", ""))

    def test_idle_session_expires_after_three_minutes_and_clears_auth_cookies(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)
        with client.session_transaction() as browser_session:
            browser_session["last_activity"] = (
                time.time() - web_app.SESSION_IDLE_TIMEOUT_SECONDS - 1
            )

        response = client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 401)
        self.assertIn(b"inactivity", response.data)
        self.assertTrue(any(
            "glfs_refresh_token=;" in cookie
            for cookie in response.headers.getlist("Set-Cookie")
        ))

    def test_idle_browser_redirect_shows_inactivity_notice(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)
        with client.session_transaction() as browser_session:
            browser_session["last_activity"] = (
                time.time() - web_app.SESSION_IDLE_TIMEOUT_SECONDS - 1
            )

        response = client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?expired=1", response.headers["Location"])
        login_page = client.get(response.headers["Location"])
        self.assertIn(b"You have been logged out due to inactivity.", login_page.data)
        login_page.close()

    def test_expired_browser_redirect_forces_login_page(self):
        web_app.app.config["TESTING"] = True
        client = web_app.app.test_client()
        self.sign_in(client)

        response = client.get("/login?expired=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back", response.data)
        self.assertTrue(any(
            "glfs_access_token=;" in cookie
            for cookie in response.headers.getlist("Set-Cookie")
        ))
        response.close()


if __name__ == "__main__":
    unittest.main()
