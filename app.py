from __future__ import annotations

import hmac
import csv
import logging
import math
import os
import secrets
import time
import uuid
import warnings
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, g, jsonify, redirect, request, send_file, send_from_directory, session, stream_with_context, url_for
from dotenv import dotenv_values
from PIL import Image, UnidentifiedImageError
from supabase import Client, ClientOptions, create_client

from excel_report import (
    build_excel_report,
    build_payroll_excel_report,
    build_trip_excel_report,
)
from fleet_management import (
    FleetManagementError,
    FleetManager,
    TripRateValidationError,
    _supabase_project_url,
)
from manifest_ocr import extract_manifest_fields, scan_manifest_image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["DOCUMENT_IMAGE_MAX_BYTES"] = int(
    os.environ.get("DOCUMENT_IMAGE_MAX_BYTES", str(10 * 1024 * 1024))
)
app.config["MAX_CONTENT_LENGTH"] = max(
    16 * 1024 * 1024, app.config["DOCUMENT_IMAGE_MAX_BYTES"] + 1024 * 1024
)
app.config["DOCUMENT_IMAGE_BUCKET"] = os.environ.get(
    "DOCUMENT_IMAGE_BUCKET", "fleet-trip-documents"
)
app.config["TIRE_LIFESPAN_WARNING_PERCENT"] = int(
    os.environ.get("TIRE_LIFESPAN_WARNING_PERCENT", "20")
)
if not 0 <= app.config["TIRE_LIFESPAN_WARNING_PERCENT"] <= 100:
    raise ValueError("TIRE_LIFESPAN_WARNING_PERCENT must be between 0 and 100.")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "").strip().lower() in {
    "1", "true", "yes", "on",
}
SESSION_IDLE_TIMEOUT_SECONDS = 3 * 60
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)

manager: FleetManager | None = None
logger = logging.getLogger(__name__)

try:
    BUSINESS_TIMEZONE = ZoneInfo("Asia/Manila")
except ZoneInfoNotFoundError:
    BUSINESS_TIMEZONE = timezone(timedelta(hours=8))


def _supabase_setting(name: str) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    return dotenv_values(os.path.join(BASE_DIR, ".env")).get(name)


def get_auth_client() -> Client:
    request_client = getattr(g, "supabase_auth_client", None)
    if request_client is not None:
        return request_client
    project_url = _supabase_setting("SUPABASE_URL")
    anon_key = _supabase_setting("SUPABASE_ANON_KEY")
    if not project_url or not anon_key:
        raise FleetManagementError(
            "Supabase login is not configured. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY in the project .env file."
        )
    try:
        request_client = create_client(_supabase_project_url(project_url), anon_key)
        g.supabase_auth_client = request_client
        return request_client
    except Exception as exc:
        raise FleetManagementError(f"Could not initialize Supabase Auth: {exc}") from exc


def get_dispatch_client() -> Client:
    request_client = getattr(g, "supabase_dispatch_client", None)
    if request_client is not None:
        return request_client
    access_token = getattr(g, "dispatch_access_token", None)
    project_url = _supabase_setting("SUPABASE_URL")
    anon_key = _supabase_setting("SUPABASE_ANON_KEY")
    if not access_token:
        raise FleetManagementError("Your sign-in expired. Please sign in again.")
    if not project_url or not anon_key:
        raise FleetManagementError(
            "Supabase dispatch access is not configured. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY in the project .env file."
        )
    try:
        request_client = create_client(
            _supabase_project_url(project_url),
            anon_key,
            options=ClientOptions(postgrest_client_timeout=15),
        )
        request_client.options.headers["Authorization"] = f"Bearer {access_token}"
        request_client.postgrest.auth(access_token)
        g.supabase_dispatch_client = request_client
        return request_client
    except Exception as exc:
        raise FleetManagementError(f"Could not initialize secure dispatch access: {exc}") from exc


def _dispatch_rpc(function_name: str, params: dict[str, Any] | None = None) -> Any:
    try:
        return get_dispatch_client().rpc(function_name, params or {}).execute().data
    except FleetManagementError:
        raise
    except Exception as exc:
        logger.warning("Secure dispatch RPC %s failed.", function_name, exc_info=True)
        message = str(getattr(exc, "message", "") or "")
        code = str(getattr(exc, "code", "") or "")
        status = getattr(exc, "status", None)
        details = str(getattr(exc, "details", "") or "")
        if code == "23505" and "dispatch_movements_ism_unique" in f"{message} {details}":
            raise FleetManagementError(
                "This ISM number is already assigned to a movement. Check the movement "
                "queues for an existing departure or enter the correct unique ISM number."
            ) from exc
        if code == "PGRST202":
            raise FleetManagementError(
                f"Dispatch database function '{function_name}' is missing. "
                "Apply the latest location-dispatch migration."
            ) from exc
        if code == "42501":
            raise FleetManagementError(
                f"Database permission denied during dispatch operation '{function_name}' "
                "(42501). Apply the latest location-dispatch grants."
            ) from exc
        if message and any(
            phrase in message.lower()
            for phrase in (
                "authorized", "required", "must be", "select an active",
                "configured", "verify", "manifests", "earlier than",
                "not ready", "not available", "correction reason",
                "capacity", "different", "complete all",
            )
        ):
            raise FleetManagementError(message) from exc
        if status in {401, 403}:
            raise FleetManagementError(
                message or "You are not authorized to perform this dispatch action."
            ) from exc
        if message:
            raise FleetManagementError(message) from exc
        if code:
            raise FleetManagementError(
                f"Dispatch database request '{function_name}' failed ({code})."
            ) from exc
        raise FleetManagementError(
            "The secure dispatch operation could not be completed. Check the migration "
            "and try again."
        ) from exc


def get_manager() -> FleetManager:
    global manager
    if manager is None:
        manager = FleetManager()
    return manager


def _json_error(message: str, status: int) -> tuple[Any, int]:
    return jsonify({"error": message}), status


def _user_role() -> str:
    return str((g.current_user or {}).get("role") or "administrator").lower()


def _is_dispatcher() -> bool:
    return _user_role() == "dispatcher"


def _role_for_auth_user(user: Any) -> str:
    app_metadata = getattr(user, "app_metadata", None) or {}
    user_metadata = getattr(user, "user_metadata", None) or {}
    trusted_role = str(app_metadata.get("role") or "").strip().lower()
    # A user-metadata dispatcher designation can only reduce access, never grant it.
    if str(user_metadata.get("role") or "").strip().lower() == "dispatcher":
        return "dispatcher"
    if trusted_role in {"administrator", "dispatcher"}:
        return trusted_role
    return "administrator"


def _authorize_dispatcher_request() -> Any:
    if not _is_dispatcher():
        return None
    if request.path.startswith("/api/payroll") or request.path == "/api/export":
        return _json_error("This function is only available to administrators.", 403)
    if request.path.startswith("/api/") and request.path not in {
        "/api/auth/me",
        "/api/bootstrap",
        "/api/export/trips",
    }:
        resource = request.path.split("/")[2] if len(request.path.split("/")) > 2 else ""
        if resource not in {"trips", "fuel", "maintenance", "tires", "dispatch"}:
            return _json_error("Dispatchers are not authorized to access this function.", 403)
        if resource == "trips" and request.method != "GET":
            return _json_error(
                "Use the Departure → Arrival workflow for trip changes.",
                403,
            )
        if request.method == "DELETE":
            return _json_error("Dispatchers cannot delete submitted records.", 403)
        is_trip_update = (
            request.method == "PATCH"
            and request.path.startswith("/api/trips/")
            and request.path.removeprefix("/api/trips/").isdigit()
        )
        if request.method not in {"GET", "POST"} and not is_trip_update:
            return _json_error("Dispatchers cannot modify submitted records this way.", 403)
    return None


def _clear_auth() -> None:
    session.clear()
    g.clear_auth_cookies = True


def _secure_cookies() -> bool:
    configured = os.environ.get("COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return request.is_secure


@app.teardown_request
def close_auth_client(_error: BaseException | None) -> None:
    for request_client in (
        getattr(g, "supabase_auth_client", None),
        getattr(g, "supabase_dispatch_client", None),
    ):
        if request_client is None:
            continue
        request_client.auth.close()
        request_client.postgrest.session.close()


@app.before_request
def enforce_authentication() -> Any:
    if request.endpoint == "auth_logout" and request.method == "POST":
        return None

    protected_path = (
        request.path in {"/", "/static/index.html"}
        or request.path.startswith("/api/")
        or request.path.startswith("/dispatcher/")
    )
    if (
        protected_path
        and not (app.testing and app.config.get("TEST_AUTH_BYPASS"))
        and session.get("user_id")
        and time.time() - session.get("last_activity", 0) >= SESSION_IDLE_TIMEOUT_SECONDS
    ):
        _clear_auth()
        if request.path.startswith("/api/") and request.endpoint not in {
            "auth_csrf", "auth_login", "auth_logout",
        }:
            return _json_error("Your session expired due to inactivity. Please sign in again.", 401)
        if request.path in {"/", "/static/index.html"}:
            return redirect(url_for("login_page", expired="1"))

    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith("/api/"):
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return _json_error("Your session token is missing or expired. Refresh and try again.", 403)

    public_endpoints = {"login_page", "auth_csrf", "auth_login", "auth_logout"}
    if request.endpoint == "static" and request.path != "/static/index.html":
        return None
    if request.endpoint in public_endpoints:
        return None

    if not protected_path:
        return None

    if app.testing and app.config.get("TEST_AUTH_BYPASS"):
        g.current_user = {"id": "test-user", "email": "test@example.com", "role": "administrator"}
        session.setdefault("user_role", "administrator")
        return None

    if not session.get("user_id"):
        _clear_auth()
        if request.path.startswith("/api/"):
            return _json_error("Authentication required.", 401)
        return redirect(url_for("login_page"))

    access_token = request.cookies.get("glfs_access_token")
    refresh_token = request.cookies.get("glfs_refresh_token")
    auth = get_auth_client().auth

    if access_token:
        try:
            user_response = auth.get_user(access_token)
            user = getattr(user_response, "user", None)
            if user and str(getattr(user, "id", "")) == str(session.get("user_id")):
                session["last_activity"] = time.time()
                g.dispatch_access_token = access_token
                role = _role_for_auth_user(user)
                session["user_role"] = role
                g.current_user = {
                    "id": str(user.id),
                    "email": getattr(user, "email", None) or session.get("email", ""),
                    "role": role,
                    "full_name": (
                        (getattr(user, "user_metadata", None) or {}).get("full_name")
                        or (getattr(user, "user_metadata", None) or {}).get("name")
                    ),
                }
                return _authorize_dispatcher_request()
        except Exception:
            pass

    if refresh_token:
        try:
            refreshed = auth.refresh_session(refresh_token)
            refreshed_session = getattr(refreshed, "session", None)
            user = getattr(refreshed, "user", None)
            if refreshed_session and user and str(getattr(user, "id", "")) == str(session.get("user_id")):
                g.auth_tokens = refreshed_session
                g.dispatch_access_token = refreshed_session.access_token
                session["last_activity"] = time.time()
                role = _role_for_auth_user(user)
                session["user_role"] = role
                g.current_user = {
                    "id": str(user.id),
                    "email": getattr(user, "email", None) or session.get("email", ""),
                    "role": role,
                    "full_name": (
                        (getattr(user, "user_metadata", None) or {}).get("full_name")
                        or (getattr(user, "user_metadata", None) or {}).get("name")
                    ),
                }
                return _authorize_dispatcher_request()
        except Exception as exc:
            status = getattr(exc, "status", None)
            if status not in {400, 401}:
                logger.warning("Supabase Auth could not refresh the session (status %s).", status)
                return _json_error("Authentication is temporarily unavailable. Please retry.", 503)

    _clear_auth()
    if request.path.startswith("/api/"):
        return _json_error("Your sign-in expired. Please sign in again.", 401)
    return redirect(url_for("login_page"))


@app.after_request
def set_auth_cookies(response: Any) -> Any:
    if request.path.startswith("/api/") or request.path in {
        "/", "/static/index.html", "/static/app.js", "/static/style.css",
    }:
        response.headers["Cache-Control"] = "no-store"
    auth_tokens = getattr(g, "auth_tokens", None)
    secure = _secure_cookies()
    if auth_tokens is not None:
        access_token = getattr(auth_tokens, "access_token", None)
        refresh_token = getattr(auth_tokens, "refresh_token", None)
        if access_token:
            response.set_cookie(
                "glfs_access_token",
                access_token,
                httponly=True,
                secure=secure,
                samesite="Lax",
                path="/",
            )
        if refresh_token:
            response.set_cookie(
                "glfs_refresh_token",
                refresh_token,
                httponly=True,
                secure=secure,
                samesite="Lax",
                path="/",
            )
    if getattr(g, "clear_auth_cookies", False):
        for cookie_name in ("glfs_access_token", "glfs_refresh_token"):
            response.delete_cookie(
                cookie_name,
                path="/",
                secure=secure,
                httponly=True,
                samesite="Lax",
            )
    return response


@app.errorhandler(FleetManagementError)
def handle_fleet_error(error: FleetManagementError) -> tuple[Any, int]:
    return jsonify({"error": str(error)}), 503


@app.errorhandler(404)
def handle_not_found(_error: Any) -> tuple[Any, int]:
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def handle_method_not_allowed(_error: Any) -> tuple[Any, int]:
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(413)
def handle_request_too_large(_error: Any) -> tuple[Any, int]:
    return _json_error("The uploaded image exceeds the request size limit.", 413)


@app.route("/")
def index() -> Any:
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/dispatcher/add-trip")
def dispatcher_add_trip() -> Any:
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/login")
def login_page() -> Any:
    if request.args.get("expired") == "1":
        _clear_auth()
        return send_from_directory(STATIC_DIR, "login.html")
    if session.get("user_id"):
        return redirect(url_for("index"))
    return send_from_directory(STATIC_DIR, "login.html")


@app.route("/api/auth/csrf")
def auth_csrf() -> Any:
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return jsonify({"csrf_token": token})


@app.route("/api/auth/login", methods=["POST"])
def auth_login() -> Any:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("Provide your email and password.", 400)
    email = str(payload.get("email", "")).strip()
    password = payload.get("password")
    if not email or not isinstance(password, str) or not password:
        return _json_error("Enter your email and password.", 400)
    try:
        auth_response = get_auth_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except FleetManagementError:
        raise
    except Exception as exc:
        status = getattr(exc, "status", None)
        error_code = getattr(exc, "code", None)
        if status in {400, 401} or error_code == "invalid_credentials":
            return _json_error("Sign-in failed. Check your email and password and try again.", 401)
        logger.warning("Supabase Auth sign-in request failed (status %s).", status)
        return _json_error("Supabase authentication is temporarily unavailable.", 502)

    auth_session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)
    if not auth_session or not user or not getattr(auth_session, "access_token", None):
        return _json_error("Supabase did not return a valid sign-in session.", 502)

    session.clear()
    role = _role_for_auth_user(user)
    session["user_id"] = str(user.id)
    session["email"] = getattr(user, "email", None) or email
    session["user_role"] = role
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["last_activity"] = time.time()
    g.auth_tokens = auth_session
    return jsonify(
        {
            "user": {
                "id": session["user_id"],
                "email": session["email"],
                "role": role,
                "full_name": (
                    (getattr(user, "user_metadata", None) or {}).get("full_name")
                    or (getattr(user, "user_metadata", None) or {}).get("name")
                ),
            },
            "redirect": url_for("index"),
        }
    )


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout() -> Any:
    _clear_auth()
    return jsonify({"redirect": url_for("login_page")})


@app.route("/api/auth/me")
def auth_me() -> Any:
    return jsonify(
        {
            "user": g.current_user,
            "csrf_token": session.get("csrf_token"),
        }
    )


@app.route("/api/bootstrap")
def bootstrap() -> Any:
    fleet = get_manager()
    user_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
    if _is_dispatcher():
        if not user_id:
            return _json_error("Authenticated dispatcher identity is missing.", 403)
        trips = fleet.list_trips(user_id=user_id, include_fuel=False)
        fuel_logs = fleet.list_fuel_logs(user_id=user_id)
        _attach_trip_fuel(trips, fuel_logs)
        maintenance = fleet.list_maintenance(user_id=user_id)
        vehicles = fleet.list_vehicles()
        drivers = fleet.list_drivers()
        today = time.strftime("%Y-%m-%d")
        _add_document_links(trips, "manifest_object_path", "manifest_image_url", "trip_manifest_image")
        _add_document_links(trips, "fuel_invoice_object_path", "fuel_invoice_image_url", "trip_fuel_invoice_image")
        _add_document_links(fuel_logs, "invoice_object_path", "invoice_image_url", "fuel_invoice_image")
        return jsonify(
            {
                "dashboard": {
                    "total_trips": len(trips),
                    "today_trips": sum(
                        str(trip.get("shipment_date") or "")[:10] == today
                        for trip in trips
                    ),
                    "total_fuel_logs": len(fuel_logs),
                    "total_maintenance": len(maintenance),
                },
                "vehicles": [
                    {
                        key: row.get(key)
                        for key in ("id", "plate_number", "make", "model", "status")
                    }
                    for row in vehicles
                ],
                "trailers": fleet.list_trailers(),
                "drivers": [
                    {key: row.get(key) for key in ("id", "name", "status")}
                    for row in drivers
                ],
                "assignments": [],
                "maintenance": maintenance,
                "fuel_logs": fuel_logs,
                "trips": trips,
                "truck_routes": fleet.list_truck_routes(),
                "truck_route_rates": fleet.list_truck_route_rates(),
                "csrf_token": session.get("csrf_token"),
                "user": g.current_user,
            }
        )
    trips = fleet.list_trips(include_fuel=False)
    fuel_logs = fleet.list_fuel_logs()
    _attach_trip_fuel(trips, fuel_logs)
    maintenance = fleet.list_maintenance()
    vehicles = fleet.list_vehicles()
    drivers = fleet.list_drivers()
    assignments = fleet.list_assignments()
    _add_document_links(trips, "manifest_object_path", "manifest_image_url", "trip_manifest_image")
    _add_document_links(trips, "fuel_invoice_object_path", "fuel_invoice_image_url", "trip_fuel_invoice_image")
    _add_document_links(fuel_logs, "invoice_object_path", "invoice_image_url", "fuel_invoice_image")
    dashboard = {
        "total_vehicles": len(vehicles),
        "active_drivers": sum(driver["status"] == "active" for driver in drivers),
        "assigned_vehicles": sum(vehicle["status"] == "assigned" for vehicle in vehicles),
        "total_fuel_spend": sum(float(item["total_cost"] or 0) for item in fuel_logs),
        "total_maintenance": sum(float(item["cost"] or 0) for item in maintenance),
        "recent_trips": len(trips),
    }
    return jsonify(
        {
            "dashboard": dashboard,
            "vehicles": vehicles,
            "trailers": fleet.list_trailers(),
            "drivers": drivers,
            "assignments": assignments,
            "maintenance": maintenance,
            "fuel_logs": fuel_logs,
            "trips": trips,
            "truck_routes": fleet.list_truck_routes(),
            "truck_route_rates": fleet.list_truck_route_rates(),
            "csrf_token": session.get("csrf_token"),
            "user": g.current_user,
        }
    )


def _dispatch_timestamp(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid date and time.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BUSINESS_TIMEZONE)
    return parsed.isoformat()


def _payload_boolean(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be true or false.")
    return value


def _dispatch_error_response(exc: FleetManagementError) -> tuple[Any, int]:
    message = str(exc)
    lowered = message.lower()
    status = 403 if any(
        word in lowered for word in (
            "not authorized", "not have access", "only an administrator",
            "only the originating", "only the verified",
        )
    ) else 400
    if "sign-in expired" in lowered:
        status = 401
    if any(
        marker in lowered
        for marker in (
            "migration", "secure dispatch operation", "permission denied",
            "42501", "database function",
        )
    ):
        status = 503
    return _json_error(message, status)


@app.route("/api/dispatch/movements", methods=["GET", "POST"])
def dispatch_movements() -> Any:
    if request.method == "GET":
        try:
            queue = request.args.get("queue", "departures")
            page = int(request.args.get("page", "1"))
            page_size = int(request.args.get("page_size", "25"))
            if queue not in {"departures", "arrivals", "completed"}:
                return _json_error("Select a valid movement queue.", 400)
            if page < 1 or page_size < 1 or page_size > 100:
                return _json_error("Invalid movement page request.", 400)
            result = _dispatch_rpc("list_dispatch_movements_page_with_load_items", {
                "p_queue": queue,
                "p_page": page,
                "p_page_size": page_size,
                "p_search": request.args.get("search", "")[:120],
            }) or {}
        except FleetManagementError as exc:
            return _dispatch_error_response(exc)
        except ValueError:
            return _json_error("Invalid movement page request.", 400)
        return jsonify({
            "movements": result.get("movements") or [],
            "total": result.get("total") or 0,
            "page": page,
            "page_size": page_size,
        })

    try:
        payload = _body()
        raw_load_items = payload.get("load_items", [])
        if not isinstance(raw_load_items, list) or len(raw_load_items) > 100:
            raise ValueError("Load items must be a list of no more than 100 products")
        load_items: list[dict[str, int]] = []
        product_ids: set[int] = set()
        for item in raw_load_items:
            if not isinstance(item, dict):
                raise ValueError("Each load item must include a product and quantity")
            product_id = _integer(item, "product_id")
            pallet_quantity = _integer(item, "pallet_quantity")
            if product_id < 1 or pallet_quantity < 1:
                raise ValueError("Product IDs and pallet quantities must be positive")
            if product_id in product_ids:
                raise ValueError("A product can only be listed once in the load")
            product_ids.add(product_id)
            load_items.append({
                "product_id": product_id,
                "pallet_quantity": pallet_quantity,
            })

        movement_id = _dispatch_rpc("create_dispatch_movement_with_load", {
            "p_origin_location_id": _required_text(payload, "origin_location_id").upper(),
            "p_destination_location_id": _required_text(payload, "destination_location_id").upper(),
            "p_ism_no": _required_text(payload, "ism_no"),
            "p_truck_id": _integer(payload, "truck_id"),
            "p_driver_id": _integer(payload, "driver_id"),
            "p_trailer_id": _integer(payload, "trailer_id"),
            "p_load_type": _required_text(payload, "load_type").upper(),
            "p_pallet_quantity": _integer(payload, "pallet_quantity"),
            "p_departure_at": _dispatch_timestamp(payload.get("departure_at"), "Departure date and time"),
            "p_fuel_allocation": _optional_number(payload, "fuel_allocation"),
            "p_actual_fuel_expense": _optional_number(payload, "actual_fuel_expense"),
            "p_fuel_remarks": _optional_text(payload, "fuel_remarks"),
            "p_load_items": load_items,
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"id": movement_id}), 201


@app.route("/api/dispatch/load-catalog")
def dispatch_load_catalog() -> Any:
    try:
        products = _dispatch_rpc("list_dispatch_load_catalog") or []
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"products": products})


@app.route("/api/dispatch/movements/<uuid:movement_id>/verify", methods=["POST"])
def verify_dispatch_movement(movement_id: uuid.UUID) -> Any:
    try:
        payload = _body()
        result = _dispatch_rpc("verify_dispatch_ism", {
            "p_movement_id": str(movement_id),
            "p_submitted_ism": _required_text(payload, "ism_no"),
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify(result)


@app.route("/api/dispatch/movements/<uuid:movement_id>/arrival", methods=["POST"])
def submit_dispatch_movement_arrival(movement_id: uuid.UUID) -> Any:
    try:
        payload = _body()
        _dispatch_rpc("submit_dispatch_arrival", {
            "p_movement_id": str(movement_id),
            "p_arrival_at": _dispatch_timestamp(payload.get("arrival_at"), "Arrival date and time"),
            "p_arrival_fuel_expense": _optional_number(payload, "arrival_fuel_expense"),
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"message": "Arrival submitted for admin review."})


@app.route(
    "/api/dispatch/movements/<uuid:movement_id>/documents/<kind>",
    methods=["GET", "POST"],
)
def upload_dispatch_movement_document(movement_id: uuid.UUID, kind: str) -> Any:
    if kind not in {"departure", "arrival", "fuel_invoice"}:
        return _json_error("Unsupported dispatch document type.", 400)
    if request.method == "GET":
        try:
            rows = _dispatch_rpc("list_dispatch_movements") or []
            movement = next(
                (row for row in rows if str(row.get("id")) == str(movement_id)),
                None,
            )
            if movement is None:
                return _json_error("Movement was not found or is not accessible.", 404)
            path_field = {
                "departure": "departure_manifest_path",
                "arrival": "arrival_manifest_path",
                "fuel_invoice": "fuel_invoice_path",
            }[kind]
            object_path = movement.get(path_field)
            if not object_path:
                return _json_error("No document has been uploaded for this movement.", 404)
            image_bytes = get_dispatch_client().storage.from_(
                app.config["DOCUMENT_IMAGE_BUCKET"]
            ).download(object_path)
        except FleetManagementError as exc:
            return _dispatch_error_response(exc)
        except Exception:
            logger.exception("Could not retrieve dispatch document.")
            return _json_error("Could not retrieve the document. Please retry.", 503)
        extension = os.path.splitext(object_path)[1].lower()
        response = send_file(
            BytesIO(image_bytes),
            mimetype={
                ".jpg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(extension, "application/octet-stream"),
            as_attachment=False,
            download_name=f"{kind}-{movement_id}{extension}",
            max_age=0,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
        return response

    image_file = request.files.get("image")
    if image_file is None:
        return _json_error("Attach an image using the 'image' field.", 400)
    try:
        image_bytes, mime_type, extension = _validated_image(image_file)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    object_path = f"{movement_id}/{kind}/{uuid.uuid4().hex}.{extension}"
    client = None
    uploaded = False
    try:
        client = get_dispatch_client()
        client.storage.from_(app.config["DOCUMENT_IMAGE_BUCKET"]).upload(
            object_path, image_bytes, {"content-type": mime_type, "upsert": "false"}
        )
        uploaded = True
        _dispatch_rpc("attach_dispatch_document", {
            "p_movement_id": str(movement_id),
            "p_document_kind": kind,
            "p_object_path": object_path,
        })
    except FleetManagementError as exc:
        if uploaded and client is not None:
            try:
                client.storage.from_(app.config["DOCUMENT_IMAGE_BUCKET"]).remove([object_path])
            except Exception:
                logger.exception("Could not clean up rejected dispatch document %s.", object_path)
        return _dispatch_error_response(exc)
    except Exception:
        if uploaded and client is not None:
            try:
                client.storage.from_(app.config["DOCUMENT_IMAGE_BUCKET"]).remove([object_path])
            except Exception:
                logger.exception("Could not clean up failed dispatch document %s.", object_path)
        logger.exception("Could not upload dispatch document.")
        return _json_error("Could not save the document. Please retry.", 503)
    return jsonify({"message": "Document uploaded successfully."}), 201


@app.route("/api/dispatch/movements/<uuid:movement_id>/finalize", methods=["POST"])
def finalize_dispatch_movement(movement_id: uuid.UUID) -> Any:
    try:
        trip_id = _dispatch_rpc("finalize_dispatch_movement", {
            "p_movement_id": str(movement_id),
        })
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"trip_id": trip_id})


@app.route("/api/dispatch/movements/<uuid:movement_id>", methods=["DELETE"])
def delete_completed_dispatch_movement(movement_id: uuid.UUID) -> Any:
    try:
        result = _dispatch_rpc("delete_completed_dispatch_movement", {
            "p_movement_id": str(movement_id),
        })
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)

    if not isinstance(result, dict) or not result.get("trip_id"):
        logger.error(
            "Completed dispatch deletion returned an invalid response for %s.",
            movement_id,
        )
        return _json_error("The completed trip could not be deleted. Please retry.", 503)

    document_paths = result.get("document_paths") or []
    warning = None
    if document_paths:
        try:
            get_manager().client.storage.from_(
                app.config["DOCUMENT_IMAGE_BUCKET"]
            ).remove(document_paths)
        except Exception:
            logger.exception(
                "Completed trip %s was deleted, but its documents could not be removed.",
                movement_id,
            )
            warning = (
                "The trip was deleted, but its uploaded documents could not be "
                "removed. Contact your system administrator."
            )

    return jsonify({
        "message": "Completed trip deleted.",
        "trip_id": result["trip_id"],
        "warning": warning,
    })


@app.route("/api/dispatch/movements/<uuid:movement_id>/correction", methods=["POST"])
def request_dispatch_correction(movement_id: uuid.UUID) -> Any:
    try:
        payload = _body()
        _dispatch_rpc("request_dispatch_correction", {
            "p_movement_id": str(movement_id),
            "p_reason": _required_text(payload, "reason"),
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"message": "Correction requested."})


@app.route("/api/dispatch/movements/<uuid:movement_id>/history")
def dispatch_movement_history(movement_id: uuid.UUID) -> Any:
    try:
        response = get_dispatch_client().table("dispatch_movement_audit").select(
            "id,actor_id,action,details,created_at"
        ).eq("movement_id", str(movement_id)).order("created_at", desc=True).execute()
    except Exception:
        logger.exception("Could not load dispatch movement audit history.")
        return _json_error("Could not load movement history. Please retry.", 503)
    return jsonify({"history": response.data or []})


@app.route("/api/dispatch/locations", methods=["GET", "POST"])
def dispatch_locations() -> Any:
    try:
        if request.method == "GET":
            locations = _dispatch_rpc("list_dispatch_locations") or []
            return jsonify({"locations": locations})
        payload = _body()
        _dispatch_rpc("manage_dispatch_location", {
            "p_location_id": _required_text(payload, "id").upper(),
            "p_name": _required_text(payload, "name"),
            "p_active": _payload_boolean(payload, "active", True),
        })
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify({"message": "Dispatch location saved."}), 201


@app.route("/api/dispatch/users")
def dispatch_users() -> Any:
    try:
        users = _dispatch_rpc("list_dispatcher_users") or []
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"users": users})


@app.route("/api/dispatch/assignments", methods=["GET", "POST"])
def dispatch_assignments() -> Any:
    try:
        if request.method == "GET":
            assignments = _dispatch_rpc("list_dispatcher_assignments") or []
            return jsonify({"assignments": assignments})
        payload = _body()
        _dispatch_rpc("manage_dispatch_location_assignment", {
            "p_user_id": _required_text(payload, "user_id"),
            "p_location_id": _required_text(payload, "location_id").upper(),
            "p_can_depart": _payload_boolean(payload, "can_depart"),
            "p_can_arrive": _payload_boolean(payload, "can_arrive"),
        })
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _dispatch_error_response(exc)
    return jsonify({"message": "Dispatcher location assignment saved."}), 201


def _add_document_links(
    rows: list[dict[str, Any]], path_field: str, url_field: str, endpoint: str
) -> None:
    for row in rows:
        object_path = row.pop(path_field, None)
        if object_path:
            row[url_field] = url_for(endpoint, **{
                "trip_id" if endpoint in ("trip_manifest_image", "trip_fuel_invoice_image") else "fuel_id": row["id"]
            })


def _attach_trip_fuel(
    trips: list[dict[str, Any]], fuel_logs: list[dict[str, Any]]
) -> None:
    fuel_by_trip = {
        row["trip_id"]: row
        for row in fuel_logs
        if row.get("trip_id") is not None
    }
    for trip in trips:
        fuel = fuel_by_trip.get(trip["id"])
        if fuel is None:
            continue
        trip["fuel_id"] = fuel.get("id")
        trip["fuel_allocation"] = fuel.get("fuel_allocation")
        trip["actual_fuel_expense"] = fuel.get("actual_expense")
        trip["actual_expense"] = fuel.get("actual_expense")
        trip["fuel_remarks"] = fuel.get("remarks")
        trip["fuel_invoice_object_path"] = fuel.get("invoice_object_path")


def _validated_image(file_storage: Any) -> tuple[bytes, str, str]:
    filename = str(file_storage.filename or "").strip()
    if not filename:
        raise ValueError("Choose an image file.")
    max_bytes = app.config["DOCUMENT_IMAGE_MAX_BYTES"]
    image_bytes = file_storage.stream.read(max_bytes + 1)
    if len(image_bytes) > max_bytes:
        raise ValueError(f"Image must be no larger than {max_bytes // (1024 * 1024)} MB.")
    if not image_bytes:
        raise ValueError("The selected image is empty.")

    formats = {
        "JPEG": ("image/jpeg", "jpg"),
        "PNG": ("image/png", "png"),
        "WEBP": ("image/webp", "webp"),
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(image_bytes))
            image_format = image.format
            if image_format not in formats:
                raise ValueError("Use a JPG, PNG, or WEBP image.")
            if image.width < 1 or image.height < 1 or image.width * image.height > 40_000_000:
                raise ValueError("Image dimensions are invalid or too large.")
            image.verify()
    except ValueError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("The selected file is not a valid image.") from exc
    mime_type, extension = formats[image_format]
    return image_bytes, mime_type, extension


def _document_user_id() -> str | None:
    if not _is_dispatcher():
        return None
    return str((g.current_user or {}).get("id") or session.get("user_id") or "")


def _record_for_document(kind: str, record_id: int) -> dict[str, Any]:
    fleet = get_manager()
    user_id = _document_user_id()
    try:
        if kind == "trip":
            return fleet.get_trip(record_id, user_id=user_id)
        if kind == "trip_fuel":
            trip = fleet.get_trip(record_id, user_id=user_id)
            fuel_records = fleet._select_all("fuel_logs", "*", filters=[("trip_id", record_id)])
            if fuel_records:
                return fleet.get_fuel(fuel_records[0]["id"], user_id=user_id)
            return {"_error": f"No fuel record linked to trip {record_id}", "_status": 404, "_trip": trip}
        return fleet.get_fuel(record_id, user_id=user_id)
    except FleetManagementError as exc:
        status = 403 if _is_dispatcher() else 404
        return {"_error": str(exc), "_status": status}


def _handle_document_image(kind: str, record_id: int) -> Any:
    record = _record_for_document(kind, record_id)
    if "_error" in record:
        if request.method == "POST" and kind == "trip_fuel" and "_trip" in record:
            trip = record["_trip"]
            owner = str(trip.get("created_by") or (g.current_user or {}).get("id") or "")
            fuel_log = get_manager().add_fuel(
                vehicle_id=trip.get("vehicle_id") or trip.get("truck_id"),
                fuel_type="diesel",
                trip_id=record_id,
                created_by=owner or None,
            )
            record = fuel_log
        else:
            return _json_error(record["_error"], record["_status"])

    is_trip = kind == "trip"
    path_field = "manifest_object_path" if is_trip else "invoice_object_path"
    actual_record_id = record["id"]
    upload_bucket_folder = "trips" if is_trip else "fuel"
    if request.method == "POST":
        image_file = request.files.get("image")
        if image_file is None:
            return _json_error("Attach an image using the 'image' field.", 400)
        try:
            image_bytes, mime_type, extension = _validated_image(image_file)
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except FleetManagementError as exc:
            validation_error = _tire_database_validation_error(exc)
            if validation_error:
                return _json_error(validation_error, 400)
            raise
        owner_id = str(record.get("created_by") or (g.current_user or {}).get("id") or "admin")
        object_path = f"{upload_bucket_folder}/{actual_record_id}/{owner_id}/{uuid.uuid4().hex}.{extension}"
        storage = get_manager().client.storage.from_(app.config["DOCUMENT_IMAGE_BUCKET"])
        uploaded = False
        try:
            storage.upload(object_path, image_bytes, {"content-type": mime_type})
            uploaded = True
            if is_trip:
                get_manager().set_trip_manifest_path(
                    actual_record_id,
                    object_path,
                    user_id=_document_user_id(),
                    edited_by=str((g.current_user or {}).get("id") or session.get("user_id") or ""),
                    editor_email=(g.current_user or {}).get("email") or session.get("email"),
                )
            else:
                get_manager().set_fuel_invoice_path(
                    actual_record_id, object_path, user_id=_document_user_id()
                )
            if is_trip and _is_dispatcher() and not record.get(path_field):
                _create_dispatcher_notifications(
                    "load_manifest", record, g.current_user or {}
                )
            if record.get(path_field):
                try:
                    storage.remove([record[path_field]])
                except Exception:
                    logger.warning("Could not remove replaced document object.", exc_info=True)
        except Exception:
            if uploaded:
                try:
                    storage.remove([object_path])
                except Exception:
                    logger.exception("Could not clean up an unlinked document object.")
            logger.exception("Could not store a document image.")
            return _json_error("Could not save the image. Please retry.", 503)
        return jsonify({"message": "Image uploaded successfully."}), 201

    object_path = record.get(path_field)
    if not object_path:
        return _json_error("No image has been uploaded for this record.", 404)
    try:
        image_bytes = get_manager().client.storage.from_(
            app.config["DOCUMENT_IMAGE_BUCKET"]
        ).download(object_path)
    except Exception:
        logger.exception("Could not retrieve a document image.")
        return _json_error("Could not retrieve the image. Please retry.", 503)

    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(os.path.splitext(object_path)[1].lower(), "application/octet-stream")
    response = send_file(
        BytesIO(image_bytes),
        mimetype=mime_type,
        as_attachment=False,
        download_name=f"{upload_bucket_folder}-{actual_record_id}{os.path.splitext(object_path)[1].lower()}",
        max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
    return response


@app.route("/api/trips/<int:trip_id>/manifest", methods=["GET", "POST"])
def trip_manifest_image(trip_id: int) -> Any:
    return _handle_document_image("trip", trip_id)


@app.route("/api/trips/<int:trip_id>/fuel-invoice", methods=["GET", "POST"])
def trip_fuel_invoice_image(trip_id: int) -> Any:
    return _handle_document_image("trip_fuel", trip_id)


@app.route("/api/trips/<int:trip_id>/history")
def trip_edit_history(trip_id: int) -> Any:
    user_id = _document_user_id()
    try:
        history = get_manager().list_trip_edit_history(trip_id, user_id=user_id)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        raise
    return jsonify({"history": history})


@app.route("/api/trips/<int:trip_id>/time-out", methods=["POST"])
def record_trip_time_out_endpoint(trip_id: int) -> Any:
    try:
        payload = _body()
        actor = g.current_user or {}
        editor_id = str(actor.get("id") or session.get("user_id") or "")
        record = get_manager().record_trip_time_out(
            trip_id,
            time_value=payload.get("time_value") if "time_value" in payload else payload.get("time_out"),
            location=payload.get("location"),
            edited_by=editor_id,
            editor_email=actor.get("email") or session.get("email"),
            user_id=editor_id if _is_dispatcher() else None,
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        return _json_error(message, 400)
    return jsonify({"data": record})


@app.route("/api/trips/<int:trip_id>/time-in", methods=["POST"])
def record_trip_time_in_endpoint(trip_id: int) -> Any:
    try:
        payload = _body()
        actor = g.current_user or {}
        editor_id = str(actor.get("id") or session.get("user_id") or "")
        record = get_manager().record_trip_time_in(
            trip_id,
            time_value=payload.get("time_value") if "time_value" in payload else payload.get("time_in"),
            location=payload.get("location"),
            edited_by=editor_id,
            editor_email=actor.get("email") or session.get("email"),
            user_id=editor_id if _is_dispatcher() else None,
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        return _json_error(message, 400)
    return jsonify({"data": record})


@app.route("/api/trips/<int:trip_id>", methods=["PATCH"])
def update_trip(trip_id: int) -> Any:
    try:
        payload = _body()
        origin = _required_text(payload, "origin")
        destination = _required_text(payload, "destination")
        actor = g.current_user or {}
        editor_id = str(actor.get("id") or session.get("user_id") or "")
        update_data = {
            "ism_no": _optional_text(payload, "ism_no"),
            "shipment_date": _required_text(payload, "shipment_date"),
            "time_in": _optional_text(payload, "time_in"),
            "time_out": _optional_text(payload, "time_out"),
            "origin": origin,
            "destination": destination,
            "vehicle_id": (
                _integer(payload, "truck_id" if payload.get("truck_id") not in (None, "") else "vehicle_id")
                if payload.get("truck_id", payload.get("vehicle_id")) not in (None, "")
                else None
            ),
            "truck_id": (
                _integer(payload, "truck_id" if payload.get("truck_id") not in (None, "") else "vehicle_id")
                if payload.get("truck_id", payload.get("vehicle_id")) not in (None, "")
                else None
            ),
            "trailer_id": (
                _integer(payload, "trailer_id")
                if payload.get("trailer_id") not in (None, "")
                else None
            ),
            "driver_id": (
                _integer(payload, "driver_id")
                if payload.get("driver_id") not in (None, "")
                else None
            ),
            "load_details": _optional_text(payload, "load_details"),
            "trip_fuel": _optional_text(payload, "trip_fuel"),
            "notes": _optional_text(payload, "notes"),
            "route": f"{origin} to {destination}",
        }
        if "fuel_allocation" in payload:
            update_data["fuel_allocation"] = _optional_number(payload, "fuel_allocation")
        if "actual_fuel_expense" in payload or "actual_expense" in payload:
            exp_field = "actual_fuel_expense" if "actual_fuel_expense" in payload else "actual_expense"
            update_data["actual_fuel_expense"] = _optional_number(payload, exp_field)
        if "fuel_remarks" in payload:
            update_data["fuel_remarks"] = _optional_text(payload, "fuel_remarks")

        record = get_manager().update_trip(
            trip_id,
            update_data,
            edited_by=editor_id,
            editor_email=actor.get("email") or session.get("email"),
            user_id=editor_id if _is_dispatcher() else None,
        )
        if record.get("manifest_object_path"):
            record["manifest_image_url"] = f"/api/trips/{trip_id}/manifest"
        if record.get("fuel_invoice_object_path"):
            record["fuel_invoice_image_url"] = f"/api/trips/{trip_id}/fuel-invoice"
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except TripRateValidationError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        raise
    return jsonify({"data": record})


@app.route("/api/fuel/<int:fuel_id>/invoice", methods=["GET", "POST"])
def fuel_invoice_image(fuel_id: int) -> Any:
    return _handle_document_image("fuel", fuel_id)


@app.route("/api/fuel/<int:fuel_id>", methods=["PATCH"])
def update_fuel_log(fuel_id: int) -> Any:
    try:
        payload = _body()
        actor = g.current_user or {}
        editor_id = str(actor.get("id") or session.get("user_id") or "")
        editor_email = actor.get("email") or session.get("email")
        record = get_manager().update_fuel(
            fuel_id,
            payload,
            edited_by=editor_id,
            editor_email=editor_email,
            user_id=editor_id if _is_dispatcher() else None,
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        return _json_error(message, 400)
    return jsonify({"data": record})


@app.route("/api/fuel/<int:fuel_id>/history")
def fuel_edit_history(fuel_id: int) -> Any:
    user_id = _document_user_id()
    try:
        history = get_manager().list_fuel_edit_history(fuel_id, user_id=user_id)
    except FleetManagementError as exc:
        message = str(exc)
        if "not found" in message.lower():
            return _json_error(message, 403 if _is_dispatcher() else 404)
        if "do not have access" in message.lower():
            return _json_error(message, 403)
        raise
    return jsonify({"history": history})


def _body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} is required")
    return value


def _integer(payload: dict[str, Any], field: str, default: int | None = None) -> int:
    value = payload.get(field, default)
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a whole number")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a whole number") from exc


def _number(payload: dict[str, Any], field: str, default: float | None = None) -> float:
    value = payload.get(field, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a number") from exc


def _optional_number(payload: dict[str, Any], field: str, default: float | None = None) -> float | None:
    value = payload.get(field, default)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a number") from exc


def _optional_text(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value).strip() or None if value is not None else None


def _tire_date(value: Any, field: str, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValueError(f"{field.replace('_', ' ').capitalize()} is required")
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be a valid date") from exc


def _tire_text(payload: dict[str, Any], field: str, required: bool = False) -> str | None:
    value = _optional_text(payload, field)
    if required and not value:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} is required")
    if value and len(value) > 240:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be 240 characters or fewer")
    return value


def _tire_lifespan_percent(payload: dict[str, Any]) -> float:
    value = _optional_number(payload, "remaining_lifespan_pct", 100.0)
    if value is None or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("Life span must be a percentage between 0 and 100")
    return round(value, 2)


def _tire_asset(payload: dict[str, Any]) -> tuple[str, int]:
    asset_type = str(payload.get("asset_type") or "").strip().lower()
    if asset_type not in {"truck", "trailer"}:
        raise ValueError("Asset type must be Truck or Trailer")
    field = "vehicle_id" if asset_type == "truck" else "trailer_id"
    asset_id = _integer(payload, field)
    if asset_id <= 0:
        raise ValueError("Select a valid truck or trailer")
    manager = get_manager()
    table = "vehicles" if asset_type == "truck" else "trailers"
    response = manager._execute(
        manager.client.table(table).select("id").eq("id", asset_id).limit(1)
    )
    if not response.data:
        raise ValueError(f"The selected {asset_type} was not found")
    return asset_type, asset_id


def _tire_record_payload(payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    if any(key in payload for key in ("created_by", "updated_by", "reference_no", "status")):
        raise ValueError("Ownership, reference number, and tire status are assigned by the system.")

    installed = _tire_date(payload.get("date_installed"), "date_installed", required=True)
    replaced = _tire_date(payload.get("date_replaced"), "date_replaced")
    reason = _tire_text(payload, "reason")
    if replaced and replaced < installed:
        raise ValueError("Replacement date cannot be before the installation date")
    if replaced and not reason:
        raise ValueError("A reason is required when recording a replaced tire")

    values: dict[str, Any] = {
        "brand": _tire_text(payload, "brand", required=True),
        "size": _tire_text(payload, "size", required=True),
        "tire_type": _tire_text(payload, "tire_type", required=True),
        "serial_no": _tire_text(payload, "serial_no"),
        "supplier": _tire_text(payload, "supplier"),
        "date_installed": installed,
        "remaining_lifespan_pct": _tire_lifespan_percent(payload),
        "reason": reason,
        "remarks": _tire_text(payload, "remarks"),
        "created_by": actor_id,
        "updated_by": actor_id,
    }
    asset_type, asset_id = _tire_asset(payload)
    wrong_asset_field = "trailer_id" if asset_type == "truck" else "vehicle_id"
    if payload.get(wrong_asset_field) not in (None, ""):
        raise ValueError(f"A {asset_type} tire record cannot also reference a different asset type")
    values["asset_type"] = asset_type
    values["vehicle_id"] = asset_id if asset_type == "truck" else None
    values["trailer_id"] = asset_id if asset_type == "trailer" else None
    values["date_replaced"] = replaced
    values["status"] = "replaced" if replaced else "installed"
    return values


def _tire_query_from_request():
    args = request.args
    manager = get_manager()
    query = manager.client.table("tire_monitoring_sheet").select("*", count="exact")
    if _is_dispatcher():
        query = query.eq(
            "created_by",
            str((g.current_user or {}).get("id") or session.get("user_id") or ""),
        )

    search = args.get("search", "").strip()
    safe_search = "".join(
        character if character.isalnum() or character in " -" else " "
        for character in search
    ).strip()
    if safe_search:
        term = f"%{safe_search}%"
        query = query.or_(
            ",".join(
                f"{field}.ilike.{term}"
                for field in (
                    "reference_no", "brand", "size", "serial_no", "supplier", "plate_number"
                )
            )
        )

    asset_type = args.get("asset_type", "").strip().lower()
    if asset_type:
        if asset_type not in {"truck", "trailer"}:
            raise ValueError("Asset type filter must be Truck or Trailer")
        query = query.eq("asset_type", asset_type)
    asset_value = args.get("asset_id", "").strip()
    if asset_value:
        asset_id = _integer({"asset_id": asset_value}, "asset_id")
        if asset_id <= 0 or asset_type not in {"truck", "trailer"}:
            raise ValueError("Choose an asset type and a valid plate number")
        query = query.eq("vehicle_id" if asset_type == "truck" else "trailer_id", asset_id)

    status = args.get("status", "").strip().lower()
    if status:
        if status not in {"installed", "replaced", "removed"}:
            raise ValueError("Status filter must be Installed, Replaced, or Removed")
        query = query.eq("status", status)

    installed_from = _tire_date(args.get("date_from"), "date_from")
    installed_to = _tire_date(args.get("date_to"), "date_to")
    if installed_from and installed_to and installed_from > installed_to:
        raise ValueError("Installation date range is invalid")
    if installed_from:
        query = query.gte("date_installed", installed_from)
    if installed_to:
        query = query.lte("date_installed", installed_to)

    minimum = args.get("lifespan_min", "").strip()
    maximum = args.get("lifespan_max", "").strip()
    try:
        minimum_value = float(minimum) if minimum else None
        maximum_value = float(maximum) if maximum else None
        if any(
            value is not None and not 0 <= value <= 100
            for value in (minimum_value, maximum_value)
        ):
            raise ValueError
    except ValueError as exc:
        raise ValueError("Lifespan filters must be percentages between 0 and 100") from exc
    if minimum_value is not None and maximum_value is not None:
        if minimum_value > maximum_value:
            raise ValueError("Lifespan range is invalid")
    if minimum_value is not None:
        query = query.gte("remaining_lifespan_pct", minimum_value)
    if maximum_value is not None:
        query = query.lte("remaining_lifespan_pct", maximum_value)

    condition = args.get("condition", "").strip().lower()
    if condition == "near_end":
        query = query.lte(
            "remaining_lifespan_pct", app.config["TIRE_LIFESPAN_WARNING_PERCENT"]
        )
    elif condition == "above_warning":
        query = query.gt(
            "remaining_lifespan_pct", app.config["TIRE_LIFESPAN_WARNING_PERCENT"]
        )
    elif condition:
        raise ValueError("Condition filter is invalid")
    return query


def _tire_visible_record(tire_id: int) -> dict[str, Any] | None:
    manager = get_manager()
    query = manager.client.table("tire_monitoring_sheet").select("*").eq("id", tire_id)
    if _is_dispatcher():
        query = query.eq(
            "created_by",
            str((g.current_user or {}).get("id") or session.get("user_id") or ""),
        )
    response = manager._execute(query.limit(1))
    return dict(response.data[0]) if response.data else None


def _tire_database_validation_error(error: FleetManagementError) -> str | None:
    message = str(error)
    normalized = message.lower()
    if "duplicate key" in normalized or "unique constraint" in normalized:
        return "That tire serial number or reference number is already in use."
    for expected in (
        "only an installed tire can be replaced",
        "only an installed tire can be removed",
        "replacement date cannot be before the installation date",
        "removal date cannot be before the installation date",
        "a replacement reason is required",
        "a removal reason is required",
        "life span must be a percentage between 0 and 100",
        "was not found",
    ):
        if expected in normalized:
            return message.removeprefix("Supabase request failed: ")
    return None


def _tire_csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def _tire_csv_response() -> Response:
    query = _tire_query_from_request()
    sort_fields = {
        "date_installed": "date_installed",
        "lifespan": "remaining_lifespan_pct",
        "brand": "brand",
        "plate": "plate_number",
    }
    sort_by = request.args.get("sort_by", "date_installed")
    sort_dir = request.args.get("sort_dir", "desc").lower()
    if sort_by not in sort_fields or sort_dir not in {"asc", "desc"}:
        raise ValueError("Sort field or direction is invalid")
    columns = (
        "reference_no", "brand", "size", "tire_type", "serial_no", "supplier",
        "date_installed", "date_replaced", "remaining_lifespan_pct", "reason",
        "remarks", "plate_number", "asset_type", "status",
    )

    @stream_with_context
    def rows():
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Reference No.", "Brand", "Size", "Type", "Serial No.", "Supplier",
                "Date Installed", "Date Replaced", "Life Span (%)", "Reason",
                "Remarks", "Plate Number", "Asset Type", "Status",
            ]
        )
        yield buffer.getvalue()
        offset = 0
        while True:
            page = get_manager()._execute(
                _tire_query_from_request()
                .order(sort_fields[sort_by], desc=sort_dir == "desc")
                .order("id", desc=True)
                .range(offset, offset + 999)
            ).data or []
            for record in page:
                buffer.seek(0)
                buffer.truncate(0)
                writer.writerow([_tire_csv_value(record.get(column)) for column in columns])
                yield buffer.getvalue()
            if len(page) < 1000:
                break
            offset += 1000

    return Response(
        rows(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tire-monitoring.csv"'},
    )


def _payroll_period_from_request(payload: dict[str, Any]) -> tuple[str, str]:
    start_date = _required_text(payload, "start_date")
    end_date = _required_text(payload, "end_date")
    return start_date, end_date


@app.route("/api/tires", methods=["GET", "POST"])
def tire_monitoring_records() -> Any:
    manager = get_manager()
    if request.method == "POST":
        try:
            payload = _body()
            actor_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
            if not actor_id:
                return _json_error("Authenticated user identity is missing.", 403)
            values = _tire_record_payload(payload, actor_id)
            inserted = manager._execute(
                manager.client.table("tire_monitoring").insert(values).select("id")
            )
            record_id = inserted.data[0]["id"]
            record = _tire_visible_record(int(record_id))
            if record is None:
                raise FleetManagementError("Supabase did not return the inserted tire record")
            return jsonify({"data": record}), 201
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except FleetManagementError as exc:
            validation_error = _tire_database_validation_error(exc)
            if validation_error:
                return _json_error(validation_error, 400)
            raise

    try:
        if request.args.get("export", "").lower() == "csv":
            return _tire_csv_response()
        page = _integer({"page": request.args.get("page", "1")}, "page")
        page_size = _integer({"page_size": request.args.get("page_size", "25")}, "page_size")
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("Page must be positive and page size must be between 1 and 100")
        sort_fields = {
            "date_installed": "date_installed",
            "lifespan": "remaining_lifespan_pct",
            "brand": "brand",
            "plate": "plate_number",
        }
        sort_by = request.args.get("sort_by", "date_installed")
        if sort_by not in sort_fields:
            raise ValueError("Sort field is invalid")
        sort_dir = request.args.get("sort_dir", "desc").lower()
        if sort_dir not in {"asc", "desc"}:
            raise ValueError("Sort direction must be asc or desc")

        query = _tire_query_from_request()
        query = query.order(sort_fields[sort_by], desc=sort_dir == "desc").order("id", desc=True)
        offset = (page - 1) * page_size
        response = manager._execute(query.range(offset, offset + page_size - 1))
        summary_response = manager._execute(
            manager.client.rpc(
                "get_tire_monitoring_summary",
                {
                    "p_user_id": (
                        str((g.current_user or {}).get("id") or session.get("user_id") or "")
                        if _is_dispatcher()
                        else None
                    ),
                    "p_warning_percent": app.config["TIRE_LIFESPAN_WARNING_PERCENT"],
                },
            )
        )
        summary_rows = summary_response.data or []
        summary = dict(summary_rows[0]) if summary_rows else {}
        return jsonify(
            {
                "data": response.data or [],
                "page": page,
                "page_size": page_size,
                "total": response.count or 0,
                "summary": summary,
                "warning_percent": app.config["TIRE_LIFESPAN_WARNING_PERCENT"],
            }
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        validation_error = _tire_database_validation_error(exc)
        if validation_error:
            return _json_error(validation_error, 400)
        raise


@app.route("/api/tires/<int:tire_id>", methods=["GET", "PATCH"])
def tire_monitoring_record(tire_id: int) -> Any:
    manager = get_manager()
    record = _tire_visible_record(tire_id)
    if record is None:
        return _json_error("Tire record not found or you do not have access.", 404)
    if request.method == "GET":
        history_response = manager._execute(
            manager.client.table("tire_monitoring_history")
            .select("id,action,actor_id,old_values,new_values,created_at")
            .eq("tire_id", tire_id)
            .order("created_at", desc=True)
            .limit(100)
        )
        replaces = None
        replaces_tire_id = record.get("replaces_tire_id")
        if replaces_tire_id is not None:
            replaces = _tire_visible_record(int(replaces_tire_id))

        replacement_query = (
            manager.client.table("tire_monitoring")
            .select("id")
            .eq("replaces_tire_id", tire_id)
            .limit(1)
        )
        if _is_dispatcher():
            replacement_query = replacement_query.eq(
                "created_by",
                str((g.current_user or {}).get("id") or session.get("user_id") or ""),
            )
        replacement_rows = manager._execute(replacement_query).data or []
        replacement = (
            _tire_visible_record(int(replacement_rows[0]["id"]))
            if replacement_rows
            else None
        )
        return jsonify(
            {
                "data": record,
                "history": history_response.data or [],
                "replaces": replaces,
                "replacement": replacement,
            }
        )
    if _is_dispatcher():
        return _json_error("Dispatchers cannot edit submitted tire records.", 403)

    try:
        payload = _body()
        if any(
            key in payload
            for key in (
                "id", "reference_no", "asset_type", "vehicle_id", "trailer_id",
                "date_installed", "date_replaced", "status", "created_by",
            )
        ):
            raise ValueError("Asset assignment and lifecycle history cannot be changed by editing.")
        actor_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
        values = {
            "brand": _tire_text(payload, "brand", required=True),
            "size": _tire_text(payload, "size", required=True),
            "tire_type": _tire_text(payload, "tire_type", required=True),
            "serial_no": _tire_text(payload, "serial_no"),
            "supplier": _tire_text(payload, "supplier"),
            "remaining_lifespan_pct": _tire_lifespan_percent(payload),
            "reason": _tire_text(payload, "reason"),
            "remarks": _tire_text(payload, "remarks"),
            "updated_by": actor_id,
        }
        updated = manager._execute(
            manager.client.table("tire_monitoring")
            .update(values)
            .eq("id", tire_id)
            .select("id")
        )
        if not updated.data:
            return _json_error("Tire record not found.", 404)
        return jsonify({"data": _tire_visible_record(tire_id)})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        validation_error = _tire_database_validation_error(exc)
        if validation_error:
            return _json_error(validation_error, 400)
        raise


@app.route("/api/tires/<int:tire_id>/replace", methods=["POST"])
def replace_tire_monitoring_record(tire_id: int) -> Any:
    if _is_dispatcher():
        return _json_error("Only administrators can replace installed tire records.", 403)
    try:
        payload = _body()
        forbidden = {
            "id", "reference_no", "asset_type", "vehicle_id", "trailer_id",
            "date_installed", "date_replaced", "status", "created_by", "updated_by",
        }
        if forbidden.intersection(payload):
            raise ValueError("Replacement identity and assignment are managed by the system.")
        replaced_on = _tire_date(payload.get("date_replaced"), "date_replaced", required=True)
        reason = _tire_text(payload, "reason", required=True)
        actor_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
        result = get_manager()._execute(
            get_manager().client.rpc(
                "replace_tire_monitoring",
                {
                    "p_tire_id": tire_id,
                    "p_date_replaced": replaced_on,
                    "p_reason": reason,
                    "p_brand": _tire_text(payload, "brand", required=True),
                    "p_size": _tire_text(payload, "size", required=True),
                    "p_tire_type": _tire_text(payload, "tire_type", required=True),
                    "p_serial_no": _tire_text(payload, "serial_no"),
                    "p_supplier": _tire_text(payload, "supplier"),
                    "p_remaining_lifespan_pct": _tire_lifespan_percent(payload),
                    "p_remarks": _tire_text(payload, "remarks"),
                    "p_actor_id": actor_id,
                },
            )
        )
        rows = result.data or []
        if not rows:
            raise FleetManagementError("Supabase did not return the replacement tire records")
        old_record = _tire_visible_record(tire_id)
        new_id = (rows[0].get("new_record") or {}).get("id")
        new_record = _tire_visible_record(int(new_id)) if new_id is not None else None
        if old_record is None or new_record is None:
            raise FleetManagementError("Supabase did not return the completed replacement history")
        return jsonify({"old_record": old_record, "new_record": new_record})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        validation_error = _tire_database_validation_error(exc)
        if validation_error:
            return _json_error(validation_error, 400)
        raise


@app.route("/api/tires/<int:tire_id>/remove", methods=["POST"])
def remove_tire_monitoring_record(tire_id: int) -> Any:
    if _is_dispatcher():
        return _json_error("Only administrators can remove installed tire records.", 403)
    try:
        payload = _body()
        if any(
            key in payload
            for key in ("id", "reference_no", "asset_type", "vehicle_id", "trailer_id", "status")
        ):
            raise ValueError("Tire assignment and status are managed by the system.")
        actor_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
        rows = get_manager()._execute(
            get_manager().client.rpc(
                "remove_tire_monitoring",
                {
                    "p_tire_id": tire_id,
                    "p_date_replaced": _tire_date(
                        payload.get("date_replaced"), "date_replaced", required=True
                    ),
                    "p_reason": _tire_text(payload, "reason", required=True),
                    "p_actor_id": actor_id,
                },
            )
        ).data or []
        if not rows:
            raise FleetManagementError("Supabase did not return the removed tire record")
        return jsonify({"data": _tire_visible_record(tire_id)})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        validation_error = _tire_database_validation_error(exc)
        if validation_error:
            return _json_error(validation_error, 400)
        raise


@app.route("/api/payroll")
def payroll_report() -> Any:
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    try:
        return jsonify(get_manager().payroll_report(start_date, end_date))
    except ValueError as exc:
        return _json_error(str(exc), 400)


def _revenue_management_request() -> tuple[dict[str, Any] | None, Any | None]:
    if _is_dispatcher() or _user_role() != "administrator":
        return None, _json_error("Revenue reporting is only available to administrators.", 403)
    current_user = g.current_user or {}
    actor_id = str(current_user.get("id") or "")
    if not actor_id:
        return None, _json_error("Authenticated administrator identity is missing.", 403)
    return current_user, None


def _revenue_date_parameter(value: str, field: str) -> date:
    if len(value) != 10:
        raise ValueError(f"{field} must use YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use YYYY-MM-DD.")
    return parsed


def _optional_revenue_integer(value: str, field: str) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a whole number.") from exc
    if parsed < 1:
        raise ValueError(f"{field} must be a positive number.")
    return parsed


@app.route("/api/revenue")
def revenue_dashboard() -> Any:
    _, error = _revenue_management_request()
    if error:
        return error
    today = datetime.now(BUSINESS_TIMEZONE).date()
    try:
        start_date = _revenue_date_parameter(
            request.args.get("start_date", today.replace(day=1).isoformat()),
            "Start date",
        )
        end_date = _revenue_date_parameter(
            request.args.get("end_date", today.isoformat()),
            "End date",
        )
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "25"))
        search = request.args.get("search", "").strip()
        bucket = request.args.get("bucket", "day")
        sort_by = request.args.get("sort_by", "shipment_date")
        sort_dir = request.args.get("sort_dir", "desc")
        if len(search) > 120:
            raise ValueError("Search text must be 120 characters or fewer.")
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("Choose a valid ledger page.")
        if bucket not in {"day", "week", "month"}:
            raise ValueError("Trend bucket must be day, week, or month.")
        if sort_by not in {"shipment_date", "id", "revenue", "route"}:
            raise ValueError("Choose a valid ledger sort column.")
        if sort_dir not in {"asc", "desc"}:
            raise ValueError("Ledger sort direction must be asc or desc.")
        filters = {
            "p_start_date": start_date.isoformat(),
            "p_end_date": end_date.isoformat(),
            "p_origin": request.args.get("origin") or None,
            "p_destination": request.args.get("destination") or None,
            "p_route_number": _optional_revenue_integer(
                request.args.get("route_number", ""), "Route number"
            ),
            "p_driver_id": _optional_revenue_integer(
                request.args.get("driver_id", ""), "Driver"
            ),
            "p_truck_id": _optional_revenue_integer(
                request.args.get("truck_id", ""), "Truck"
            ),
            "p_trailer_id": _optional_revenue_integer(
                request.args.get("trailer_id", ""), "Trailer"
            ),
            "p_pallet_capacity": _optional_revenue_integer(
                request.args.get("pallet_capacity", ""), "Pallet capacity"
            ),
            "p_search": search or None,
            "p_page": page,
            "p_page_size": page_size,
            "p_sort_by": sort_by,
            "p_sort_dir": sort_dir,
            "p_bucket": bucket,
        }
        if start_date > end_date:
            raise ValueError("Start date must be on or before end date.")
        report = get_manager().revenue_dashboard(filters)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        logger.warning("Could not load Revenue dashboard: %s", exc)
        return _json_error(str(exc), 503)
    return jsonify(report)


@app.route("/api/revenue/trips/<int:trip_id>/status", methods=["POST"])
def update_trip_revenue_status(trip_id: int) -> Any:
    actor, error = _revenue_management_request()
    if error:
        return error
    payload = _body()
    status = _required_text(payload, "status").lower()
    reason = _required_text(payload, "reason")
    if status not in {"pending", "eligible", "cancelled"}:
        return _json_error("Choose a supported revenue status.", 400)
    if len(reason) > 1000:
        return _json_error("Reason must be 1,000 characters or fewer.", 400)
    try:
        trip = get_manager().set_trip_revenue_status(
            trip_id,
            status,
            reason,
            str(actor["id"]),
            str(actor.get("email") or ""),
        )
    except FleetManagementError as exc:
        logger.warning("Could not update revenue status for trip %s: %s", trip_id, exc)
        return _json_error(str(exc), 400)
    return jsonify({"trip": trip})


@app.route("/api/revenue/trips/<int:trip_id>/adjustments", methods=["POST"])
def create_revenue_adjustment(trip_id: int) -> Any:
    actor, error = _revenue_management_request()
    if error:
        return error
    payload = _body()
    try:
        amount = Decimal(str(payload.get("amount", "")).strip())
        if not amount.is_finite() or amount.quantize(Decimal("0.01")) != amount:
            raise ValueError("Adjustment must be a finite amount with no more than two decimal places.")
    except (InvalidOperation, ValueError) as exc:
        return _json_error(str(exc) or "Enter a valid adjustment amount.", 400)
    if amount == 0:
        return _json_error("Adjustment must be non-zero.", 400)
    reason = _required_text(payload, "reason")
    if len(reason) > 1000:
        return _json_error("Reason must be 1,000 characters or fewer.", 400)
    try:
        request_id = str(uuid.UUID(str(payload.get("idempotency_key", ""))))
    except (ValueError, AttributeError) as exc:
        return _json_error("Adjustment request identifier is invalid.", 400)
    try:
        adjustment = get_manager().add_revenue_adjustment(
            trip_id,
            amount,
            reason,
            str(actor["id"]),
            request_id,
        )
    except FleetManagementError as exc:
        logger.warning("Could not record revenue adjustment for trip %s: %s", trip_id, exc)
        return _json_error(str(exc), 400)
    return jsonify({"adjustment": adjustment}), 201


@app.route("/api/payroll/export")
def export_payroll_report() -> Any:
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    try:
        report = get_manager().payroll_report(start_date, end_date)
    except ValueError as exc:
        return _json_error(str(exc), 400)

    filters = {
        "driver_id": request.args.get("driver_id", "").strip(),
        "ism_no": request.args.get("ism_no", "").strip(),
        "origin": request.args.get("origin", "").strip(),
        "destination": request.args.get("destination", "").strip(),
    }
    search = filters["ism_no"].casefold()
    trips = [
        trip for trip in report.get("trips", [])
        if (not filters["driver_id"] or str(trip.get("driver_id")) == filters["driver_id"])
        and (not search or search in str(trip.get("ism_no") or "").casefold())
        and (not filters["origin"] or trip.get("origin") == filters["origin"])
        and (not filters["destination"] or trip.get("destination") == filters["destination"])
    ]
    drivers = [
        driver for driver in report.get("drivers", [])
        if not filters["driver_id"] or str(driver.get("driver_id")) == filters["driver_id"]
    ]
    selected_driver = next(
        (driver.get("driver_name") for driver in drivers
         if str(driver.get("driver_id")) == filters["driver_id"]),
        None,
    )
    if selected_driver:
        filters["driver_id"] = selected_driver
    return send_file(
        build_payroll_excel_report(
            report, trips, drivers, start_date, end_date, filters
        ),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"payroll-{start_date}-to-{end_date}.xlsx",
    )


@app.route("/api/payroll/review", methods=["POST"])
def payroll_review() -> Any:
    try:
        payload = _body()
        start_date, end_date = _payroll_period_from_request(payload)
        result = get_manager().review_payroll(
            start_date, end_date, str(g.current_user["id"])
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(result)


@app.route("/api/payroll/cash-advances", methods=["POST"])
def payroll_cash_advance() -> Any:
    try:
        payload = _body()
        start_date, end_date = _payroll_period_from_request(payload)
        result = get_manager().add_cash_advance(
            start_date=start_date,
            end_date=end_date,
            driver_id=_integer(payload, "driver_id"),
            advance_date=_required_text(payload, "advance_date"),
            amount=payload.get("amount"),
            remarks=_optional_text(payload, "remarks"),
            reference=_optional_text(payload, "reference"),
            actor_id=str(g.current_user["id"]),
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify({"data": result}), 201


@app.route("/api/payroll/overdrafts", methods=["POST"])
def payroll_overdraft() -> Any:
    try:
        payload = _body()
        result = get_manager().add_overdraft(
            driver_id=_integer(payload, "driver_id"),
            transaction_type=_required_text(payload, "transaction_type"),
            amount=payload.get("amount"),
            effective_date=_required_text(payload, "effective_date"),
            remarks=_optional_text(payload, "remarks"),
            actor_id=str(g.current_user["id"]),
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify({"data": result}), 201


@app.route("/api/payroll/finalize", methods=["POST"])
def payroll_finalize() -> Any:
    try:
        payload = _body()
        start_date, end_date = _payroll_period_from_request(payload)
        settle_overdraft = payload.get("settle_overdraft", False)
        if not isinstance(settle_overdraft, bool):
            raise ValueError("settle_overdraft must be true or false")
        result = get_manager().finalize_payroll(
            start_date,
            end_date,
            settle_overdraft,
            str(g.current_user["id"]),
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(result)


def _create_record(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    fleet = get_manager()
    if any(key in payload for key in ("created_by", "dispatcher_id", "user_id")):
        raise ValueError("Ownership is assigned automatically by the authenticated user.")
    if resource == "vehicles":
        return fleet.add_vehicle(
            plate_number=_required_text(payload, "plate_number"),
            make=_required_text(payload, "make"),
            model=_required_text(payload, "model"),
            year=_integer(payload, "year"),
            color=_optional_text(payload, "color"),
            status=_optional_text(payload, "status") or "active",
            odometer=_integer(payload, "odometer", 0),
            registration_expiry=_optional_text(payload, "registration_expiry"),
            insurance_expiry=_optional_text(payload, "insurance_expiry"),
        )
    if resource == "trailers":
        return fleet.add_trailer(
            plate_number=_required_text(payload, "plate_number"),
            pallet_capacity=(
                _integer(payload, "pallet_capacity")
                if payload.get("pallet_capacity") not in (None, "")
                else None
            ),
            trailer_type=_optional_text(payload, "trailer_type"),
            status=_optional_text(payload, "status") or "active",
            remarks=_optional_text(payload, "remarks"),
            year_model=(
                _integer(payload, "year_model")
                if payload.get("year_model") not in (None, "")
                else None
            ),
            make_model=_optional_text(payload, "make_model"),
            mv_file_no=_optional_text(payload, "mv_file_no"),
            engine_no=_optional_text(payload, "engine_no"),
            chassis_no=_optional_text(payload, "chassis_no"),
        )
    if resource == "drivers":
        return fleet.add_driver(
            name=_required_text(payload, "name"),
            license_number=_required_text(payload, "license_number"),
            phone=_optional_text(payload, "phone"),
            email=_optional_text(payload, "email"),
            status=_optional_text(payload, "status") or "active",
        )
    if resource == "assignments":
        return fleet.assign_vehicle(
            driver_id=_integer(payload, "driver_id"),
            vehicle_id=_integer(payload, "vehicle_id"),
            assigned_date=_optional_text(payload, "assigned_date"),
            notes=_optional_text(payload, "notes"),
        )
    if resource == "maintenance":
        created_by = str(g.current_user["id"]) if _is_dispatcher() else None
        return fleet.add_maintenance(
            vehicle_id=_integer(payload, "vehicle_id"),
            service_type=_required_text(payload, "service_type"),
            description=_optional_text(payload, "description"),
            cost=_number(payload, "cost", 0),
            performed_on=_optional_text(payload, "performed_on"),
            created_by=created_by,
        )
    if resource == "fuel":
        created_by = str(g.current_user["id"]) if _is_dispatcher() else None
        return fleet.add_fuel(
            vehicle_id=_integer(payload, "vehicle_id"),
            fuel_type=_optional_text(payload, "fuel_type") or "diesel",
            quantity=_optional_number(payload, "quantity"),
            price_per_liter=_optional_number(payload, "price_per_liter"),
            total_cost=_optional_number(payload, "total_cost"),
            logged_on=_optional_text(payload, "logged_on"),
            created_by=created_by,
            trip_id=_integer(payload, "trip_id") if payload.get("trip_id") not in (None, "") else None,
            fuel_allocation=_optional_number(payload, "fuel_allocation"),
            actual_expense=_optional_number(payload, "actual_expense") or _optional_number(payload, "actual_fuel_expense"),
            remarks=_optional_text(payload, "remarks") or _optional_text(payload, "fuel_remarks"),
        )
    if resource == "trips":
        origin = _required_text(payload, "origin")
        destination = _required_text(payload, "destination")
        shipment_date = _optional_text(payload, "shipment_date")
        created_by = str(g.current_user["id"]) if _is_dispatcher() else None
        truck_field = "truck_id" if payload.get("truck_id") not in (None, "") else "vehicle_id"
        created_trip = fleet.add_trip(
            vehicle_id=_integer(payload, truck_field),
            driver_id=_integer(payload, "driver_id"),
            route=f"{origin} to {destination}",
            start_odometer=0,
            end_odometer=0,
            trip_date=shipment_date,
            ism_no=_optional_text(payload, "ism_no"),
            shipment_date=shipment_date,
            time_in=_optional_text(payload, "time_in"),
            time_out=_optional_text(payload, "time_out"),
            origin=origin,
            destination=destination,
            load_details=_optional_text(payload, "load_details"),
            trip_fuel=_optional_text(payload, "trip_fuel"),
            notes=_optional_text(payload, "notes"),
            created_by=created_by,
            require_truck_rate=True,
            trailer_id=_integer(payload, "trailer_id"),
            fuel_allocation=_optional_number(payload, "fuel_allocation"),
            actual_fuel_expense=(
                _optional_number(payload, "actual_fuel_expense")
                if payload.get("actual_fuel_expense") not in (None, "")
                else _optional_number(payload, "actual_expense")
            ),
            fuel_remarks=_optional_text(payload, "fuel_remarks") or _optional_text(payload, "remarks"),
            create_fuel_log=bool(payload.get("create_fuel_log")),
        )
        if created_trip.get("manifest_object_path"):
            created_trip["manifest_image_url"] = f"/api/trips/{created_trip['id']}/manifest"
        if created_trip.get("fuel_invoice_object_path"):
            created_trip["fuel_invoice_image_url"] = f"/api/trips/{created_trip['id']}/fuel-invoice"
        return created_trip
    raise ValueError("Unknown resource")


def _admin_recipient_ids() -> list[str]:
    admin_api = get_manager().client.auth.admin
    recipient_ids: list[str] = []
    page = 1
    per_page = 1000
    while True:
        response = admin_api.list_users(page=page, per_page=per_page)
        users = getattr(response, "users", response)
        if not isinstance(users, list):
            raise FleetManagementError("Supabase Auth returned an invalid user list.")
        recipient_ids.extend(
            str(user.id)
            for user in users
            if getattr(user, "id", None) and _role_for_auth_user(user) == "administrator"
        )
        if len(users) < per_page:
            return recipient_ids
        page += 1


def _notification_message(resource: str, record: dict[str, Any]) -> tuple[str, str]:
    if resource in {"trips", "load_manifest"}:
        title = "New Load Manifest Added" if resource == "load_manifest" else "New Trip Added"
        route = " → ".join(
            str(record.get(field) or "").strip()
            for field in ("origin", "destination")
            if record.get(field)
        )
        details = [route] if route else []
        if record.get("ism_no"):
            details.append(f"ISM Number: {record['ism_no']}")
        if resource == "load_manifest":
            details.insert(0, "Load manifest uploaded")
        return title, " · ".join(details) or f"Trip record #{record['id']}"
    if resource == "fuel":
        title = "New Fuel Log Added"
        details = []
        if record.get("plate_number"):
            details.append(f"Vehicle: {record['plate_number']}")
        if record.get("total_cost") is not None:
            details.append(f"Fuel amount: ₱{record['total_cost']}")
        elif record.get("quantity") is not None:
            details.append(f"Fuel quantity: {record['quantity']} L")
        return title, " · ".join(details) or f"Fuel log record #{record['id']}"
    if resource == "maintenance":
        title = "New Maintenance Log Added"
        details = [
            str(record.get("service_type") or "").strip(),
            str(record.get("description") or "").strip(),
        ]
        if record.get("plate_number"):
            details.insert(0, f"Vehicle: {record['plate_number']}")
        return title, " · ".join(detail for detail in details if detail) or f"Maintenance record #{record['id']}"
    raise ValueError(f"Notifications are not configured for {resource}.")


def _create_dispatcher_notifications(
    resource: str, record: dict[str, Any], actor: dict[str, Any]
) -> None:
    module_details = {
        "trips": ("NEW_TRIP", "trips"),
        "fuel": ("NEW_FUEL_LOG", "fuel"),
        "maintenance": ("NEW_MAINTENANCE_LOG", "maintenance"),
        "load_manifest": ("NEW_LOAD_MANIFEST", "trips"),
    }
    notification_type, module = module_details[resource]
    actor_id = str(actor["id"])
    actor_name = str(actor.get("full_name") or actor.get("email") or "Dispatcher")
    actor_email = str(actor.get("email") or "")
    try:
        notification_record = dict(record)
        if resource in {"fuel", "maintenance"} and record.get("vehicle_id"):
            try:
                vehicle = get_manager().get_vehicle(int(record["vehicle_id"]))
                notification_record["plate_number"] = vehicle.get("plate_number")
            except Exception:
                logger.warning(
                    "Could not load vehicle details for %s notification record %s.",
                    resource,
                    record.get("id"),
                    exc_info=True,
                )
        title, details = _notification_message(resource, notification_record)
        message = f"Dispatcher: {actor_name}"
        if actor_email:
            message += f" ({actor_email})"
        message += f" · {details}"
        recipients = _admin_recipient_ids()
        if not recipients:
            logger.warning("No Admin recipients found for dispatcher notification.")
            return

        notifications = get_manager().client.table("notifications")
        for recipient_id in recipients:
            try:
                existing = (
                    notifications.select("id")
                    .eq("recipient_user_id", recipient_id)
                    .eq("notification_type", notification_type)
                    .eq("module", module)
                    .eq("record_id", str(record["id"]))
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    continue
                notifications.insert({
                    "recipient_user_id": recipient_id,
                    "actor_user_id": actor_id,
                    "actor_name": actor_name,
                    "actor_email": actor_email,
                    "notification_type": notification_type,
                    "module": module,
                    "record_id": str(record["id"]),
                    "title": title,
                    "message": message,
                    "is_read": False,
                }).execute()
            except Exception:
                logger.exception(
                    "Could not persist notification for Admin %s (%s record %s).",
                    recipient_id,
                    resource,
                    record.get("id"),
                )
    except Exception:
        logger.exception(
            "Could not create notification for dispatcher %s %s record %s.",
            resource,
            actor_id,
            record.get("id"),
        )


def _admin_notification_request() -> tuple[str | None, Any | None]:
    if _is_dispatcher() or _user_role() != "administrator":
        return None, _json_error("Notifications are only available to administrators.", 403)
    recipient_id = str((g.current_user or {}).get("id") or "")
    if not recipient_id:
        return None, _json_error("Authenticated Admin identity is missing.", 403)
    return recipient_id, None


@app.route("/api/notifications")
def list_notifications() -> Any:
    recipient_id, error = _admin_notification_request()
    if error:
        return error
    try:
        notifications = get_manager()._select_all(
            "notifications",
            "*",
            order=("created_at", "desc"),
            filters=[("recipient_user_id", recipient_id)],
        )
    except FleetManagementError as exc:
        logger.warning("Could not load Admin notifications: %s", exc)
        return _json_error(str(exc), 503)
    except Exception:
        logger.exception("Could not load Admin notifications.")
        return _json_error("Could not load notifications. Please retry.", 503)

    dispatcher = request.args.get("dispatcher", "").strip().lower()
    data_type = request.args.get("type", "").strip().lower()
    created_date = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip().lower()
    if created_date:
        try:
            datetime.strptime(created_date, "%Y-%m-%d")
        except ValueError:
            return _json_error("Date filter must use YYYY-MM-DD.", 400)
    if status and status not in {"read", "unread"}:
        return _json_error("Status filter must be read or unread.", 400)
    notifications = [
        row for row in notifications
        if (not dispatcher or dispatcher in (
            f"{row.get('actor_name', '')} {row.get('actor_email', '')}".lower()
        ))
        and (not data_type or row.get("notification_type", "").lower() == data_type)
        and (not created_date or str(row.get("created_at", ""))[:10] == created_date)
        and (not status or bool(row.get("is_read")) == (status == "read"))
    ]
    return jsonify({"notifications": notifications})


@app.route("/api/notifications/unread-count")
def unread_notification_count() -> Any:
    recipient_id, error = _admin_notification_request()
    if error:
        return error
    try:
        unread = get_manager()._select_all(
            "notifications",
            "id",
            filters=[("recipient_user_id", recipient_id), ("is_read", False)],
        )
    except FleetManagementError as exc:
        logger.warning("Could not load the Admin unread notification count: %s", exc)
        return _json_error(str(exc), 503)
    except Exception:
        logger.exception("Could not load the Admin unread notification count.")
        return _json_error("Could not load unread notifications. Please retry.", 503)
    return jsonify({"unread_count": len(unread)})


@app.route("/api/notifications/<int:notification_id>/read", methods=["PATCH"])
def mark_notification_read(notification_id: int) -> Any:
    recipient_id, error = _admin_notification_request()
    if error:
        return error
    notifications = get_manager().client.table("notifications")
    try:
        result = (
            notifications.update({
                "is_read": True,
                "read_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", notification_id)
            .eq("recipient_user_id", recipient_id)
            .eq("is_read", False)
            .execute()
        )
        rows = result.data or []
        if not rows:
            existing = (
                notifications.select("*")
                .eq("id", notification_id)
                .eq("recipient_user_id", recipient_id)
                .limit(1)
                .execute()
            )
            rows = existing.data or []
        if not rows:
            return _json_error("Notification not found.", 404)
    except FleetManagementError as exc:
        logger.warning("Could not mark Admin notification %s as read: %s", notification_id, exc)
        return _json_error(str(exc), 503)
    except Exception:
        logger.exception("Could not mark Admin notification %s as read.", notification_id)
        return _json_error("Could not update the notification. Please retry.", 503)
    return jsonify({"notification": rows[0]})


@app.route("/api/notifications/read-all", methods=["PATCH"])
def mark_all_notifications_read() -> Any:
    recipient_id, error = _admin_notification_request()
    if error:
        return error
    try:
        result = (
            get_manager().client.table("notifications")
            .update({
                "is_read": True,
                "read_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("recipient_user_id", recipient_id)
            .eq("is_read", False)
            .execute()
        )
    except FleetManagementError as exc:
        logger.warning("Could not mark all Admin notifications as read: %s", exc)
        return _json_error(str(exc), 503)
    except Exception:
        logger.exception("Could not mark all Admin notifications as read.")
        return _json_error("Could not update notifications. Please retry.", 503)
    return jsonify({"updated": len(result.data or [])})


@app.route("/api/trips/scan-manifest", methods=["POST"])
def scan_manifest_route() -> Any:
    file_storage = request.files.get("image") or request.files.get("manifest_image")
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return _json_error("Attach a load-manifest image to scan.", 400)
    try:
        content = file_storage.read()
        if not content:
            raise ValueError("The selected manifest image is empty.")
        result = scan_manifest_image(content, file_storage.filename)
        return jsonify({"data": result})
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception:
        logger.exception("Could not process a load manifest image.")
        return _json_error("The manifest image could not be processed. Please retry or enter the details manually.", 503)


@app.route(
    "/api/<any(vehicles,trailers,drivers,assignments,maintenance,fuel,trips):resource>",
    methods=["POST"],
)
def create_record(resource: str) -> Any:
    if resource not in {"vehicles", "trailers", "drivers", "assignments", "maintenance", "fuel", "trips"}:
        return jsonify({"error": "Unknown resource"}), 404
    try:
        record = _create_record(resource, _body())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except TripRateValidationError as exc:
        return _json_error(str(exc), 400)
    if _is_dispatcher() and resource in {"trips", "fuel", "maintenance"}:
        _create_dispatcher_notifications(resource, record, g.current_user or {})
    return jsonify({"data": record}), 201


@app.route("/api/<any(vehicles,trailers):resource>/<int:record_id>", methods=["PATCH"])
def update_fleet_asset(resource: str, record_id: int) -> Any:
    if _is_dispatcher():
        return _json_error("Dispatchers cannot modify fleet assets.", 403)
    try:
        payload = _body()
        if resource == "vehicles":
            values = {
                "plate_number": _required_text(payload, "plate_number"),
                "make": _required_text(payload, "make"),
                "model": _required_text(payload, "model"),
                "year": _integer(payload, "year"),
                "color": _optional_text(payload, "color"),
                "status": _required_text(payload, "status"),
                "odometer": _integer(payload, "odometer", 0),
                "registration_expiry": _optional_text(payload, "registration_expiry"),
                "insurance_expiry": _optional_text(payload, "insurance_expiry"),
            }
            record = get_manager().update_vehicle(record_id, values)
        else:
            values = {
                "plate_number": _required_text(payload, "plate_number"),
                "pallet_capacity": (
                    _integer(payload, "pallet_capacity")
                    if payload.get("pallet_capacity") not in (None, "")
                    else None
                ),
                "year_model": (
                    _integer(payload, "year_model")
                    if payload.get("year_model") not in (None, "")
                    else None
                ),
                "make_model": _optional_text(payload, "make_model"),
                "mv_file_no": _optional_text(payload, "mv_file_no"),
                "engine_no": _optional_text(payload, "engine_no"),
                "chassis_no": _optional_text(payload, "chassis_no"),
                "trailer_type": _optional_text(payload, "trailer_type"),
                "status": _required_text(payload, "status"),
                "remarks": _optional_text(payload, "remarks"),
            }
            record = get_manager().update_trailer(record_id, values)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except FleetManagementError as exc:
        return _json_error(str(exc), 400)
    return jsonify({"data": record})


@app.route(
    "/api/<any(vehicles,trailers,drivers,assignments,maintenance,fuel,trips):resource>/<int:record_id>",
    methods=["DELETE"],
)
def delete_record(resource: str, record_id: int) -> Any:
    method_names = {
        "vehicles": "delete_vehicle",
        "trailers": "delete_trailer",
        "drivers": "delete_driver",
        "assignments": "delete_assignment",
        "maintenance": "delete_maintenance",
        "fuel": "delete_fuel_log",
        "trips": "delete_trip",
    }
    method_name = method_names.get(resource)
    if method_name is None:
        return jsonify({"error": "Unknown resource"}), 404
    try:
        manager = get_manager()
        if _is_dispatcher():
            return _json_error("Dispatchers cannot delete this record type.", 403)
        getattr(manager, method_name)(record_id)
        return jsonify({"message": "Record deleted"})
    except FleetManagementError as exc:
        return _json_error(str(exc), 403 if _is_dispatcher() else 400)


@app.route("/api/export")
def export_report() -> Any:
    fleet = get_manager()
    user_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
    if _is_dispatcher() and user_id:
        report = {
            "vehicles": fleet.list_vehicles(),
            "trailers": fleet.list_trailers(),
            "drivers": fleet.list_drivers(),
            "assignments": fleet.list_assignments(),
            "trips": fleet.list_trips(user_id=user_id),
            "maintenance": fleet.list_maintenance(user_id=user_id),
            "fuel_logs": fleet.list_fuel_logs(user_id=user_id),
            "dashboard": fleet.dashboard(user_id=user_id),
        }
    else:
        report = {
            "vehicles": fleet.list_vehicles(),
            "trailers": fleet.list_trailers(),
            "drivers": fleet.list_drivers(),
            "assignments": fleet.list_assignments(),
            "trips": fleet.list_trips(),
            "maintenance": fleet.list_maintenance(),
            "fuel_logs": fleet.list_fuel_logs(),
            "dashboard": fleet.dashboard(),
        }
    return send_file(
        build_excel_report(report),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="fleet_system_report.xlsx",
    )


@app.route("/api/export/trips")
def export_trip_history() -> Any:
    group_by = request.args.get("group_by", "")
    valid_group_fields = {"", "driver_name", "plate_number", "truck_plate_number", "origin", "destination"}
    if group_by not in valid_group_fields:
        return _json_error("Choose a valid trip grouping.", 400)

    user_id = str((g.current_user or {}).get("id") or session.get("user_id") or "")
    trips = get_manager().list_trips(user_id=user_id if _is_dispatcher() and user_id else None)
    search_term = request.args.get("search", "").strip().casefold()
    if search_term:
        searchable_fields = (
            "ism_no", "shipment_date", "time_in", "time_out", "origin",
            "destination", "plate_number", "load_details", "driver_name", "trip_fuel",
        )
        trips = [
            trip for trip in trips
            if any(
                search_term in str(trip.get(field) or "").casefold()
                for field in searchable_fields
            )
        ]

    return send_file(
        build_trip_excel_report(trips, group_by or None),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="trip_history.xlsx",
    )


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
