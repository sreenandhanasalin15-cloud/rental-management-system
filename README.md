# Rental Management System

A web-based Rental Management System built using Python and Django.
This platform allows owners to list rental items and users to browse, book, and rent equipment online.

## Project Description

The Rental Management System is designed to simplify the process of renting tools, electronics, and other equipment.
Owners can upload items with details, while users can search, book, and make payments through the platform.

## Features

* User registration and login
* Owner registration with document verification
* Add, edit, and delete rental items
* Item booking system
* Online payment integration
* Rental agreement generation
* Location-based item search
* Booking management
* Review and rating system

## Technologies Used

* Python
* Django
* HTML
* CSS
* Bootstrap
* SQLite
* Razorpay (for payments)

## Project Structure

```
rental_project/
│
├── accounts/        # User and owner authentication
├── rentals/         # Rental item and booking management
├── templates/       # HTML templates
├── media/           # Uploaded files and images
├── manage.py
└── db.sqlite3
```

## Installation Steps

1. Clone the repository

```
git clone https://github.com/sreenandhanasalin15-cloud/rental-management-system.git
```

2. Navigate to the project folder

```
cd rental-management-system
```

3. Install dependencies

```
pip install -r requirements.txt
```

4. Run migrations

```
python manage.py migrate
```

5. Start the development server

```
python manage.py runserver
```

6. Open in browser

```
http://127.0.0.1:8000/
```

## Author

Sree Nandhana
MCA Student

## License

This project is created for educational purposes.
