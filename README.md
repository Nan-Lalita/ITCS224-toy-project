# ITCS224-toy-project

Hotel reservation web app built with Flask and local JSON storage.

## Features

- Search for available rooms by check-in and check-out date
- View Standard, Deluxe, and Suite room types with pricing
- Reserve a room by entering guest name and email
- Receive a booking confirmation with a reference number
- Cancel an existing booking by reference number
- Mobile-friendly layout with a clean blue-accent design

## Setup

1. Create and activate a Python 3.10+ virtual environment.
2. Install dependencies:

	```bash
	pip install -r requirements.txt
	```

3. Run the app:

	```bash
	flask --app app run --debug
	```

4. Open the local server shown by Flask in your browser.

## Data Storage

- Booking data is stored in `bookings.json` in the project root.
- The file is created automatically the first time the app writes a booking.
- Each booking is stored as one JSON record with the reference number, guest info, room type, dates, and status.
- Cancelled bookings are retained with `status: cancelled` so availability checks stay accurate.

## Routes

- `/` - search rooms and view availability
- `/book/<room_type>` - reserve a selected room type
- `/confirmation/<reference_number>` - view a completed booking summary
- `/cancel` - cancel a booking by reference number

## Notes

- Availability is calculated from a fixed room inventory for each room type.
- The app uses a simple file lock around JSON reads and writes for local development.
- `bookings.json` is ignored by git because it contains runtime user data.
