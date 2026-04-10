from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
BOOKINGS_FILE = BASE_DIR / "bookings.json"
DATE_FORMAT = "%Y-%m-%d"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ROOM_TYPES = {
	"standard": {
		"name": "Standard",
		"price": 120,
		"inventory": 5,
		"description": "Comfortable room with essential amenities for a simple stay.",
	},
	"deluxe": {
		"name": "Deluxe",
		"price": 180,
		"inventory": 3,
		"description": "More space and upgraded features for extra comfort.",
	},
	"suite": {
		"name": "Suite",
		"price": 260,
		"inventory": 2,
		"description": "Premium space with a separate living area for longer stays.",
	},
}

FILE_LOCK = threading.RLock()

app = Flask(__name__)
app.secret_key = "hotel-reservation-dev-secret"


@dataclass
class ValidationResult:
	valid: bool
	value: date | None = None
	error: str | None = None


def load_bookings() -> list[dict]:
	with FILE_LOCK:
		if not BOOKINGS_FILE.exists():
			BOOKINGS_FILE.write_text("[]", encoding="utf-8")
			return []

		try:
			raw_data = BOOKINGS_FILE.read_text(encoding="utf-8").strip()
			if not raw_data:
				return []
			bookings = json.loads(raw_data)
			if isinstance(bookings, list):
				return bookings
		except json.JSONDecodeError:
			pass

	return []


def save_bookings(bookings: list[dict]) -> None:
	with FILE_LOCK:
		BOOKINGS_FILE.write_text(json.dumps(bookings, indent=2), encoding="utf-8")


def parse_date(date_text: str | None, field_name: str) -> ValidationResult:
	if not date_text:
		return ValidationResult(False, error=f"{field_name} is required.")

	try:
		return ValidationResult(True, value=datetime.strptime(date_text, DATE_FORMAT).date())
	except ValueError:
		return ValidationResult(False, error=f"{field_name} must be in YYYY-MM-DD format.")


def validate_email(email: str | None) -> str | None:
	if not email:
		return "Email is required."
	if not EMAIL_PATTERN.match(email.strip()):
		return "Enter a valid email address."
	return None


def normalize_room_key(room_key: str | None) -> str | None:
	if not room_key:
		return None
	return room_key.strip().lower()


def is_valid_date_range(check_in: date, check_out: date) -> bool:
	return check_out > check_in


def booking_overlaps(existing_booking: dict, check_in: date, check_out: date) -> bool:
	existing_check_in = datetime.strptime(existing_booking["check_in"], DATE_FORMAT).date()
	existing_check_out = datetime.strptime(existing_booking["check_out"], DATE_FORMAT).date()
	return check_in < existing_check_out and check_out > existing_check_in


def count_overlapping_bookings(bookings: list[dict], room_key: str, check_in: date, check_out: date) -> int:
	return sum(
		1
		for booking in bookings
		if booking.get("status", "confirmed") == "confirmed"
		and booking.get("room_type") == room_key
		and booking_overlaps(booking, check_in, check_out)
	)


def get_room_catalog() -> list[dict]:
	return [
		{
			"key": key,
			"name": data["name"],
			"price": data["price"],
			"inventory": data["inventory"],
			"description": data["description"],
		}
		for key, data in ROOM_TYPES.items()
	]


def get_available_rooms(check_in: date, check_out: date, bookings: list[dict] | None = None) -> list[dict]:
	active_bookings = bookings if bookings is not None else load_bookings()
	available_rooms: list[dict] = []

	for room_key, room_data in ROOM_TYPES.items():
		overlaps = count_overlapping_bookings(active_bookings, room_key, check_in, check_out)
		remaining = room_data["inventory"] - overlaps
		available_rooms.append(
			{
				"key": room_key,
				"name": room_data["name"],
				"price": room_data["price"],
				"inventory": room_data["inventory"],
				"description": room_data["description"],
				"available": remaining > 0,
				"remaining": remaining if remaining > 0 else 0,
			}
		)

	return available_rooms


def find_booking(reference_number: str, bookings: list[dict] | None = None) -> dict | None:
	active_bookings = bookings if bookings is not None else load_bookings()
	for booking in active_bookings:
		if booking.get("reference_number") == reference_number:
			return booking
	return None


def generate_reference_number(bookings: list[dict]) -> str:
	existing_references = {booking.get("reference_number") for booking in bookings}
	while True:
		reference_number = uuid.uuid4().hex[:8].upper()
		if reference_number not in existing_references:
			return reference_number


def validate_booking_request(room_key: str, check_in_text: str | None, check_out_text: str | None) -> tuple[date | None, date | None, list[str]]:
	errors: list[str] = []

	if room_key not in ROOM_TYPES:
		errors.append("Select a valid room type.")

	check_in_result = parse_date(check_in_text, "Check-in date")
	check_out_result = parse_date(check_out_text, "Check-out date")

	if not check_in_result.valid and check_in_result.error:
		errors.append(check_in_result.error)
	if not check_out_result.valid and check_out_result.error:
		errors.append(check_out_result.error)

	if check_in_result.valid and check_out_result.valid and check_in_result.value and check_out_result.value:
		if not is_valid_date_range(check_in_result.value, check_out_result.value):
			errors.append("Check-out date must be after check-in date.")

	return check_in_result.value, check_out_result.value, errors


@app.route("/", methods=["GET", "POST"])
def index():
	form_data = {
		"check_in": request.values.get("check_in", ""),
		"check_out": request.values.get("check_out", ""),
	}
	errors: list[str] = []
	search_results: list[dict] = []

	if request.method == "POST":
		check_in, check_out, errors = validate_booking_request(
			"standard",
			request.form.get("check_in"),
			request.form.get("check_out"),
		)
		form_data["check_in"] = request.form.get("check_in", "")
		form_data["check_out"] = request.form.get("check_out", "")

		if not errors and check_in and check_out:
			search_results = get_available_rooms(check_in, check_out)
	else:
		check_in_text = request.args.get("check_in")
		check_out_text = request.args.get("check_out")

		if check_in_text or check_out_text:
			check_in, check_out, errors = validate_booking_request("standard", check_in_text, check_out_text)
			form_data["check_in"] = check_in_text or ""
			form_data["check_out"] = check_out_text or ""
			if not errors and check_in and check_out:
				search_results = get_available_rooms(check_in, check_out)

	return render_template(
		"index.html",
		form_data=form_data,
		errors=errors,
		room_types=get_room_catalog(),
		search_results=search_results,
	)


@app.route("/book/<room_key>", methods=["GET", "POST"])
def book(room_key: str):
	normalized_room_key = normalize_room_key(room_key)
	room_info = ROOM_TYPES.get(normalized_room_key or "")
	check_in_text = request.values.get("check_in", "")
	check_out_text = request.values.get("check_out", "")
	errors: list[str] = []
	check_in = None
	check_out = None

	if room_info is None:
		flash("Please choose a valid room type.", "error")
		return redirect(url_for("index"))

	if request.method == "POST":
		check_in, check_out, errors = validate_booking_request(
			normalized_room_key or "",
			request.form.get("check_in"),
			request.form.get("check_out"),
		)
		guest_name = (request.form.get("guest_name") or "").strip()
		guest_email = (request.form.get("guest_email") or "").strip()

		if not guest_name:
			errors.append("Guest name is required.")

		email_error = validate_email(guest_email)
		if email_error:
			errors.append(email_error)

		if not errors and check_in and check_out:
			with FILE_LOCK:
				bookings = load_bookings()
				available_rooms = get_available_rooms(check_in, check_out, bookings)
				selected_room = next((room for room in available_rooms if room["key"] == normalized_room_key), None)

				if not selected_room or not selected_room["available"]:
					errors.append("That room type is no longer available for the selected dates.")
				else:
					reference_number = generate_reference_number(bookings)
					booking = {
						"reference_number": reference_number,
						"guest_name": guest_name,
						"guest_email": guest_email,
						"room_type": normalized_room_key,
						"room_type_label": room_info["name"],
						"price_per_night": room_info["price"],
						"check_in": check_in.strftime(DATE_FORMAT),
						"check_out": check_out.strftime(DATE_FORMAT),
						"status": "confirmed",
						"created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
						"total_nights": (check_out - check_in).days,
						"total_price": (check_out - check_in).days * room_info["price"],
					}
					bookings.append(booking)
					save_bookings(bookings)
					flash("Your booking has been confirmed.", "success")
					return redirect(url_for("confirmation", reference_number=reference_number))

		check_in_text = request.form.get("check_in", check_in_text)
		check_out_text = request.form.get("check_out", check_out_text)
	else:
		check_in, check_out, errors = validate_booking_request(normalized_room_key or "", check_in_text, check_out_text)
		if errors:
			flash("Select dates first before booking a room.", "error")
			return redirect(url_for("index"))

	return render_template(
		"booking.html",
		room=room_info,
		room_key=normalized_room_key,
		check_in=check_in_text,
		check_out=check_out_text,
		errors=errors,
	)


@app.route("/confirmation/<reference_number>")
def confirmation(reference_number: str):
	booking = find_booking(reference_number)
	if booking is None:
		flash("We could not find that booking reference.", "error")
		return redirect(url_for("index"))

	room_info = ROOM_TYPES.get(booking["room_type"], {})
	return render_template("confirmation.html", booking=booking, room=room_info)


@app.route("/cancel", methods=["GET", "POST"])
def cancel_booking():
	reference_number = ""
	message = None
	booking = None

	if request.method == "POST":
		reference_number = (request.form.get("reference_number") or "").strip().upper()
		confirm_cancel = request.form.get("confirm_cancel") == "1"
		if not reference_number:
			message = "Enter a booking reference number."
		else:
			with FILE_LOCK:
				bookings = load_bookings()
				booking = find_booking(reference_number, bookings)

				if booking is None:
					message = "No booking was found for that reference number."
				elif booking.get("status") == "cancelled":
					message = "That booking has already been cancelled."
				elif not confirm_cancel:
					message = "Review the reservation details below, then confirm cancellation if this is the correct booking."
				else:
					booking["status"] = "cancelled"
					booking["cancelled_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
					save_bookings(bookings)
					flash("Your booking has been cancelled.", "success")
					return redirect(url_for("cancel_booking"))

	return render_template("cancel.html", reference_number=reference_number, message=message, booking=booking)


@app.route("/bookings/<reference_number>")
def booking_lookup(reference_number: str):
	booking = find_booking(reference_number.upper())
	if booking is None:
		flash("We could not find that booking reference.", "error")
		return redirect(url_for("index"))
	return redirect(url_for("confirmation", reference_number=booking["reference_number"]))


if __name__ == "__main__":
	app.run(debug=True)
