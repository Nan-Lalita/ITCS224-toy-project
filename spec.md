# Project Specification: Hotel Reservation App

## What
A hotel reservation web app that lets users search for available rooms, 
select a room type, and complete a booking online.

## Who
Hotel guests who want to reserve a room without calling the front desk.

## Why
To make the booking process fast and convenient from any device at any time.

## Features
1. Search for available rooms by check-in date and check-out date
2. View room types (Standard, Deluxe, Suite) with price per night
3. Enter guest name and email to reserve a room
4. Confirm the booking and receive a booking summary with a reference number
5. Cancel an existing booking using the reference number
6. Mobile-friendly layout that works on a phone screen

## Look
- Clean, minimal design
- White background with a blue accent color
- Large buttons and readable text for easy use on small screens

## How
- Language: Python 3.10+
- Framework: Flask
- Data storage: Local JSON file (no external database)
- Bookings stored in bookings.json, one record per booking
