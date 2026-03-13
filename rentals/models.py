from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# Helper function for specifications default
def get_default_specifications():
    return {
        "Platform Height": "",
        "Platform Capacity": "",
        "Platform Size": "",
        "Weight": ""
    }

# ----------------------------
# Rental Item Model
# ----------------------------
class RentalItem(models.Model):

    CATEGORY_CHOICES = [
        ('construction_power_tools', '🔧 Construction & Power Tools'),
        ('home_improvement', '🏡 Home Improvement Tools'),
        ('garden_outdoor', '🌿 Garden & Outdoor Equipment'),
        ('electrical_electronics', '⚡ Electrical & Electronics'),
        ('event_party', '🎉 Event & Party Equipment'),
        ('cameras_media', '📷 Cameras & Media Equipment'),
        ('heavy_machinery', '🚜 Heavy Machinery'),
        ('hand_tools', '🛠 Hand Tools'),
        ('camping_outdoor', '🏕 Camping & Outdoor Gear'),
        ('vehicle_transport', '🚗 Vehicle & Transport Rentals'),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    description = models.TextField()

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    price_per_day = models.DecimalField(max_digits=8, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    image = models.ImageField(upload_to='items/', blank=True, null=True)

    location_name = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Fixed specifications field with callable default
    specifications = models.JSONField(
        default=get_default_specifications,
        blank=True, 
        help_text="Store item specifications as JSON"
    )
    
    quantity = models.PositiveIntegerField(default=1, help_text="Number of units available")
    
    # NEW: Average rating field
    average_rating = models.FloatField(default=0, help_text="Average rating from user reviews")
    total_ratings = models.PositiveIntegerField(default=0, help_text="Total number of ratings received")

    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def update_rating(self):
        """Update average rating when new rating is added"""
        ratings = self.ratings.all()
        self.total_ratings = ratings.count()
        if self.total_ratings > 0:
            self.average_rating = ratings.aggregate(models.Avg('stars'))['stars__avg']
        else:
            self.average_rating = 0
        self.save()

    def __str__(self):
        return self.name

# ----------------------------
# Booking Model
# ----------------------------
class Booking(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    item = models.ForeignKey(
        RentalItem,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    start_date = models.DateField()
    end_date = models.DateField()

    quantity = models.PositiveIntegerField(default=1)

    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # 30% advance
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Remaining amount
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Payment status choices
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('ADVANCE_PAID', 'Advance Paid'),
            ('BALANCE_PAID', 'Balance Paid'),
            ('FULLY_PAID', 'Fully Paid'),
            ('FAILED', 'Failed'),
            ('REFUNDED', 'Refunded')
        ],
        default='PENDING'
    )
    
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    
    # Separate transaction IDs for advance and balance
    advance_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    balance_transaction_id = models.CharField(max_length=100, blank=True, null=True)

    # Refund tracking
    refund_status = models.CharField(
        max_length=20,
        choices=[
            ('NOT_APPLICABLE', 'Not Applicable'),
            ('PENDING', 'Refund Pending'),
            ('PROCESSED', 'Refund Processed'),
            ('FAILED', 'Refund Failed')
        ],
        default='NOT_APPLICABLE'
    )
    refund_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    refund_processed_at = models.DateTimeField(null=True, blank=True)

    # Agreement tracking
    agreement_accepted = models.BooleanField(default=False)
    agreement_accepted_at = models.DateTimeField(null=True, blank=True)
    agreement_pdf = models.FileField(upload_to='agreements/', null=True, blank=True)

    # Return tracking fields
    actual_return_date = models.DateField(null=True, blank=True)
    return_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('RETURNED_ON_TIME', 'Returned on Time'),
            ('RETURNED_LATE', 'Returned Late'),
            ('NOT_RETURNED', 'Not Returned')
        ],
        default='PENDING'
    )
    
    # Late fee tracking
    late_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    late_fee_paid = models.BooleanField(default=False)
    
    # Review tracking
    review_submitted = models.BooleanField(default=False)
    
    # Return reminder tracking
    return_reminder_sent = models.BooleanField(default=False)

    # Updated status choices
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),                    # Waiting for owner approval
        ('APPROVED', 'Approved'),                   # Owner approved, waiting for agreement
        ('AGREEMENT_PENDING', 'Agreement Pending'), # Agreement signed, waiting for balance payment
        ('CONFIRMED', 'Confirmed'),                  # Full payment done, rental active
        ('REJECTED', 'Rejected'),                   # Owner rejected
        ('CANCELLED', 'Cancelled'),                  # Cancelled by user/owner
        ('RETURNED', 'Returned'),                    # Item returned
        ('COMPLETED', 'Completed'),                  # Review submitted, all done
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_days(self):
        """Calculate number of rental days"""
        return (self.end_date - self.start_date).days

    def is_overdue(self):
        """Check if rental is overdue"""
        from django.utils import timezone
        return self.status == 'CONFIRMED' and self.end_date < timezone.now().date()

    def calculate_late_fee(self):
        """Calculate late fee if returned after end date"""
        if self.actual_return_date and self.actual_return_date > self.end_date:
            days_late = (self.actual_return_date - self.end_date).days
            # Late fee: 10% of daily rate per day
            self.late_fee = days_late * (float(self.item.price_per_day) * 0.1)
            self.return_status = 'RETURNED_LATE'
        elif self.actual_return_date and self.actual_return_date <= self.end_date:
            self.return_status = 'RETURNED_ON_TIME'
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.item.name}"

#-------------------------------------------------------
#               NOTIFICATION MODEL
#--------------------------------------------------------
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('BOOKING_APPROVED', 'Booking Approved'),
        ('BOOKING_REJECTED', 'Booking Rejected'),
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('AGREEMENT_SIGNED', 'Agreement Signed'),
        ('RETURN_REMINDER', 'Return Reminder'),
        ('RETURN_OVERDUE', 'Return Overdue'),
        ('ITEM_RETURNED', 'Item Returned'),
        ('REVIEW_REQUEST', 'Review Request'),
        ('REFUND_PROCESSED', 'Refund Processed'),
        ('DAMAGE_REPORTED', 'Damage Reported'),
        ('LATE_FEE_CHARGED', 'Late Fee Charged'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

#-------------------------------------------------------
#               DAMAGE REPORT 
#--------------------------------------------------------
class DamageReport(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='damage_report'
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_damages'
    )

    description = models.TextField()

    fine_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )
    
    # NEW: Damage image evidence
    evidence_image = models.ImageField(upload_to='damage_evidence/', blank=True, null=True)
    
    # NEW: Resolution status
    resolution_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Review'),
            ('APPROVED', 'Approved'),
            ('DISPUTED', 'Disputed'),
            ('RESOLVED', 'Resolved')
        ],
        default='PENDING'
    )
    
    fine_paid = models.BooleanField(default=False)
    fine_paid_at = models.DateTimeField(null=True, blank=True)

    reported_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Damage Report - {self.booking.item.name}"
    
#---------------------------------------
#      RATING MODEL
#----------------------------------------------
class Rating(models.Model):

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='rating'
    )

    item = models.ForeignKey(
        RentalItem,
        on_delete=models.CASCADE,
        related_name='ratings'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_given'
    )

    stars = models.IntegerField()  # 1 to 5
    review = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Override save to update item's average rating"""
        super().save(*args, **kwargs)
        self.item.update_rating()

    def __str__(self):
        return f"{self.item.name} - {self.stars} stars"

#---------------------------------------
#      USER PROFILE EXTENSION
#----------------------------------------------
# If you want to extend the user model with additional fields
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Profile fields
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Verification status
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    
    # Statistics
    total_rentals = models.PositiveIntegerField(default=0)
    total_listings = models.PositiveIntegerField(default=0)
    average_rating_as_renter = models.FloatField(default=0)
    average_rating_as_owner = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"