from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserLoginForm, RentalItemForm, BookingForm
from .models import RentalItem, Booking, Notification, Rating, DamageReport, UserProfile
import math
import json
from django.db.models import Q, Sum, Count, Avg, F, ExpressionWrapper, fields
from django.contrib import messages
from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncMonth
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest, JsonResponse
from reportlab.pdfgen import canvas
from django.http import HttpResponse
import io

import razorpay
from django.conf import settings

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# -------------------------
# Helper Functions
# -------------------------
def create_notification(user, notification_type, title, message, booking=None):
    """Helper function to create notifications"""
    Notification.objects.create(
        user=user,
        booking=booking,
        notification_type=notification_type,
        title=title,
        message=message
    )

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

# -------------------------
# Registration View
# -------------------------
def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            login(request, user)
            # Redirect based on role
            if user.role == 'owner':
                return redirect('rentals:owner_dashboard')
            else:
                return redirect('rentals:user_dashboard')
    else:
        form = UserRegisterForm()
    return render(request, 'rentals/register.html', {'form': form})

# -------------------------
# Login View
# -------------------------
def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Redirect based on role
            if user.role == 'owner':
                return redirect('rentals:owner_dashboard')
            else:
                return redirect('rentals:user_dashboard')
    else:
        form = UserLoginForm()
    return render(request, 'rentals/login.html', {'form': form})

# -------------------------
# Logout View
# -------------------------
@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# -------------------------
# Notifications View
# -------------------------
@login_required
def notifications_view(request):
    """View all notifications for the user"""
    notifications = Notification.objects.filter(user=request.user)
    
    # Mark all as read
    notifications.filter(is_read=False).update(is_read=True)
    
    return render(request, 'rentals/notifications.html', {
        'notifications': notifications
    })

@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@login_required
def get_unread_notification_count(request):
    """Get count of unread notifications"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

# -------------------------
# Owner Dashboard
# -------------------------
@login_required
def owner_dashboard(request):
    """Enhanced owner dashboard with all features"""
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')

    now = timezone.now()
    today = now.date()

    # Get owner's items with booking counts
    items = RentalItem.objects.filter(owner=request.user).annotate(
        total_bookings=Count('bookings'),
        completed_bookings=Count('bookings', filter=Q(bookings__status='COMPLETED')),
        active_rentals_count=Count('bookings', filter=Q(bookings__status='CONFIRMED', bookings__end_date__gte=today)),
        pending_requests_count=Count('bookings', filter=Q(bookings__status='PENDING'))
    )
    
    # Get all bookings for owner's items
    all_bookings = Booking.objects.filter(
        item__owner=request.user
    ).select_related('user', 'item').order_by('-created_at')
    
    # Filter bookings by status
    pending_bookings = all_bookings.filter(status='PENDING')
    approved_bookings = all_bookings.filter(status='APPROVED')
    agreement_pending_bookings = all_bookings.filter(status='AGREEMENT_PENDING')
    confirmed_bookings = all_bookings.filter(status='CONFIRMED')
    completed_bookings = all_bookings.filter(status='COMPLETED')
    rejected_bookings = all_bookings.filter(status='REJECTED')
    cancelled_bookings = all_bookings.filter(status='CANCELLED')
    returned_bookings = all_bookings.filter(status='RETURNED')
    
    # Calculate statistics
    total_items = items.count()
    active_bookings = confirmed_bookings.filter(end_date__gte=today).count()
    completed_count = completed_bookings.count()
    pending_count = pending_bookings.count()
    approved_count = approved_bookings.count()
    agreement_pending_count = agreement_pending_bookings.count()
    returned_count = returned_bookings.count()
    
    # Calculate overdue rentals
    overdue_rentals = confirmed_bookings.filter(end_date__lt=today).count()
    
    # Calculate earnings
    total_earnings = all_bookings.filter(
        status__in=['COMPLETED', 'RETURNED']
    ).aggregate(total=Sum('total_price'))['total'] or 0
    
    # Monthly earnings for graph
    last_6_months = timezone.now() - timedelta(days=180)
    monthly_earnings = all_bookings.filter(
        status__in=['COMPLETED', 'RETURNED'],
        created_at__gte=last_6_months
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('total_price')
    ).order_by('month')
    
    # Format monthly data for chart
    months_data = []
    earnings_data = []
    for item in monthly_earnings:
        months_data.append(item['month'].strftime('%b %Y') if item['month'] else 'N/A')
        earnings_data.append(float(item['total']) if item['total'] else 0)
    
    # Most booked item
    most_booked_item = items.order_by('-total_bookings').first()
    
    # Low stock alerts (quantity < 3)
    low_stock_items = items.filter(quantity__lt=3, quantity__gt=0)
    low_stock_count = low_stock_items.count()
    
    # Recent notifications
    recent_notifications = []
    
    # New booking requests in last 24 hours
    new_requests = pending_bookings.filter(created_at__date=today).count()
    if new_requests > 0:
        recent_notifications.append({
            'type': 'new_booking',
            'message': f'{new_requests} new booking request(s) today',
            'icon': 'bi-calendar-plus',
            'color': 'primary'
        })
    
    # Low stock alerts
    if low_stock_count > 0:
        recent_notifications.append({
            'type': 'low_stock',
            'message': f'{low_stock_count} item(s) have low quantity',
            'icon': 'bi-exclamation-triangle',
            'color': 'warning'
        })
    
    # Overdue alerts
    if overdue_rentals > 0:
        recent_notifications.append({
            'type': 'overdue',
            'message': f'{overdue_rentals} rental(s) are overdue',
            'icon': 'bi-exclamation-circle',
            'color': 'danger'
        })
    
    # Recent completed bookings
    recent_completed = completed_bookings.filter(created_at__date=today).count()
    if recent_completed > 0:
        recent_notifications.append({
            'type': 'completed',
            'message': f'{recent_completed} booking(s) completed today',
            'icon': 'bi-check-circle',
            'color': 'success'
        })
    
    # Get status counts for filter
    status_counts = {
        'PENDING': pending_count,
        'APPROVED': approved_count,
        'AGREEMENT_PENDING': agreement_pending_count,
        'CONFIRMED': active_bookings,
        'COMPLETED': completed_count,
        'REJECTED': rejected_bookings.count(),
        'CANCELLED': cancelled_bookings.count(),
        'RETURNED': returned_count,
    }
    
    # Calculate days for each confirmed booking
    for booking in confirmed_bookings:
        booking.days_until_return = (booking.end_date - today).days
        booking.is_overdue = booking.end_date < today
        booking.return_status = 'overdue' if booking.is_overdue else 'active'
    
    # Calculate days for each pending booking
    for booking in pending_bookings:
        booking.days = (booking.end_date - booking.start_date).days
    
    # Prepare months data as JSON for the template
    months_data_json = json.dumps(months_data)
    earnings_data_json = json.dumps(earnings_data)
    
    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        # Items
        'items': items,
        'total_items': total_items,
        'most_booked_item': most_booked_item,
        'low_stock_items': low_stock_items,
        'low_stock_count': low_stock_count,
        
        # Bookings
        'all_bookings': all_bookings,
        'pending_bookings': pending_bookings,
        'approved_bookings': approved_bookings,
        'agreement_pending_bookings': agreement_pending_bookings,
        'confirmed_bookings': confirmed_bookings,
        'completed_bookings': completed_bookings,
        'rejected_bookings': rejected_bookings,
        'cancelled_bookings': cancelled_bookings,
        'returned_bookings': returned_bookings,
        
        # Stats
        'active_bookings': active_bookings,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'agreement_pending_count': agreement_pending_count,
        'returned_count': returned_count,
        'total_earnings': total_earnings,
        'overdue_rentals': overdue_rentals,
        
        # Chart data
        'months_data': months_data_json,
        'earnings_data': earnings_data_json,
        
        # Notifications
        'notifications': recent_notifications,
        'unread_notifications': unread_notifications,
        
        # Status counts
        'status_counts': status_counts,
        
        # Current date for template
        'now': today,
    }
    
    return render(request, 'rentals/owner_dashboard.html', context)

# -------------------------
# Book Item View - Step 1: Initial Booking Request
# -------------------------
@login_required
def book_item(request, item_id):
    """Step 1: Create booking request with advance payment"""
    item = get_object_or_404(RentalItem, id=item_id)
    
    if not item.is_available:
        messages.error(request, "This item is not available for rent.")
        return redirect('rentals:item_detail', item_id=item.id)

    if request.method == "POST":
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")
        
        try:
            quantity = int(request.POST.get("quantity", 1))
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            min_allowed_date = today + timedelta(days=2)

            # Validation
            if start_date >= end_date:
                messages.error(request, "End date must be after start date.")
                return redirect('rentals:item_detail', item_id=item.id)

            if start_date < min_allowed_date:
                messages.error(request, f"Bookings must be made at least 2 days in advance.")
                return redirect('rentals:item_detail', item_id=item.id)

            if quantity > item.quantity:
                messages.error(request, f"Only {item.quantity} units available.")
                return redirect('rentals:item_detail', item_id=item.id)

            # Check for overlapping bookings
            existing_bookings = Booking.objects.filter(
                item=item,
                status__in=['PENDING', 'APPROVED', 'AGREEMENT_PENDING', 'CONFIRMED'],
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exists()
            
            if existing_bookings:
                messages.error(request, "Item is already booked for these dates.")
                return redirect('rentals:item_detail', item_id=item.id)

            # Calculate days and total price
            days = (end_date - start_date).days
            total_price = days * float(item.price_per_day) * quantity
            advance_paid = total_price * 0.3  # 30% advance
            balance_amount = total_price - advance_paid

            # Store booking data in session for payment
            request.session['pending_booking'] = {
                'item_id': item.id,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'quantity': quantity,
                'total_price': float(total_price),
                'advance_paid': float(advance_paid),
                'days': days,
                'balance_amount': float(balance_amount)
            }
            
            # Redirect to advance payment page
            return redirect('rentals:process_advance_payment', item_id=item.id)

        except ValueError as e:
            messages.error(request, "Invalid date format.")
            return redirect('rentals:item_detail', item_id=item.id)

    return redirect('rentals:item_detail', item_id=item.id)

# -------------------------
# Process Advance Payment - Step 2
# -------------------------
@login_required
def process_advance_payment(request, item_id):
    """Step 2: Process advance payment (30%)"""
    item = get_object_or_404(RentalItem, id=item_id)
    
    pending_booking = request.session.get('pending_booking')
    
    if not pending_booking or pending_booking['item_id'] != item.id:
        messages.error(request, "No pending booking found.")
        return redirect('rentals:item_detail', item_id=item.id)
    
    # Create Razorpay order for advance payment
    amount_in_paise = int(pending_booking['advance_paid'] * 100)
    
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'advance_{request.user.id}_{item.id}',
        'payment_capture': 1,
        'notes': {
            'booking_type': 'advance',
            'item_name': item.name,
            'user_email': request.user.email
        }
    }
    
    try:
        razorpay_order = razorpay_client.order.create(data=order_data)
        request.session['razorpay_order_id'] = razorpay_order['id']
        
    except Exception as e:
        messages.error(request, f"Error creating payment: {str(e)}")
        return redirect('rentals:item_detail', item_id=item.id)
    
    context = {
        'item': item,
        'booking': pending_booking,
        'advance_amount': pending_booking['advance_paid'],
        'total_amount': pending_booking['total_price'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': razorpay_order['id'],
        'amount_in_paise': amount_in_paise,
        'currency': 'INR',
        'callback_url': request.build_absolute_uri(reverse('rentals:payment_callback')),
        'payment_type': 'advance'
    }
    
    return render(request, 'rentals/razorpay_payment.html', context)

# -------------------------
# Payment Callback - Step 3
# -------------------------
@csrf_exempt
def payment_callback(request):
    """Step 3: Handle advance payment callback and create booking"""
    if request.method == "POST":
        try:
            payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')
            
            pending_booking = request.session.get('pending_booking')
            stored_order_id = request.session.get('razorpay_order_id')
            
            if not pending_booking or razorpay_order_id != stored_order_id:
                return render(request, 'rentals/payment_failed.html', {
                    'error': 'Invalid payment session'
                })
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params_dict)
                
                # Create booking with transaction
                with transaction.atomic():
                    item = get_object_or_404(RentalItem, id=pending_booking['item_id'])
                    
                    booking = Booking.objects.create(
                        user=request.user,
                        item=item,
                        start_date=datetime.strptime(pending_booking['start_date'], "%Y-%m-%d").date(),
                        end_date=datetime.strptime(pending_booking['end_date'], "%Y-%m-%d").date(),
                        quantity=pending_booking['quantity'],
                        total_price=pending_booking['total_price'],
                        advance_paid=pending_booking['advance_paid'],
                        balance_amount=pending_booking['balance_amount'],
                        payment_status='ADVANCE_PAID',
                        payment_method='razorpay',
                        advance_transaction_id=payment_id,
                        status='PENDING'  # Waiting for owner approval
                    )
                    
                    # Update user profile stats
                    profile, created = UserProfile.objects.get_or_create(user=request.user)
                    profile.total_rentals += 1
                    profile.save()
                    
                    # Create notification for owner
                    create_notification(
                        user=item.owner,
                        notification_type='BOOKING_APPROVED',
                        title='New Booking Request',
                        message=f'{request.user.username} has requested to rent {item.name}. Advance payment of ₹{pending_booking["advance_paid"]} received.',
                        booking=booking
                    )
                
                # Clear session data
                del request.session['pending_booking']
                del request.session['razorpay_order_id']
                
                messages.success(
                    request, 
                    f"Advance payment successful! Your booking request has been sent to {item.owner.username}."
                )
                
                return redirect('rentals:booking_pending', booking_id=booking.id)
                
            except razorpay.errors.SignatureVerificationError:
                return render(request, 'rentals/payment_failed.html', {
                    'error': 'Payment signature verification failed'
                })
                
        except Exception as e:
            return render(request, 'rentals/payment_failed.html', {
                'error': str(e)
            })
    
    return HttpResponseBadRequest()

# -------------------------
# Booking Pending - Step 4
# -------------------------
@login_required
def booking_pending(request, booking_id):
    """Step 4: Show booking pending page (waiting for owner approval)"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Calculate days
    days = (booking.end_date - booking.start_date).days
    refund_deadline = booking.created_at + timedelta(hours=24)
    
    context = {
        'booking': booking,
        'owner': booking.item.owner,
        'advance_paid': booking.advance_paid,
        'total_price': booking.total_price,
        'balance_amount': booking.balance_amount,
        'days': days,
        'refund_deadline': refund_deadline,
    }
    
    return render(request, 'rentals/booking_pending.html', context)

# -------------------------
# Owner Approve Booking - Step 5a
# -------------------------
@login_required
def approve_booking(request, booking_id):
    """Step 5a: Owner approves the booking request"""
    if request.user.role != 'owner':
        messages.error(request, "Access denied. Owner privileges required.")
        return redirect('rentals:user_dashboard')
    
    booking = get_object_or_404(Booking, id=booking_id, item__owner=request.user)
    
    if booking.status != 'PENDING':
        messages.warning(request, "This booking cannot be approved.")
        return redirect('rentals:owner_bookings')
    
    # Update booking status
    booking.status = 'APPROVED'
    booking.save()
    
    # Update item availability if quantity becomes 0
    if booking.item.quantity <= booking.quantity:
        booking.item.is_available = False
        booking.item.save()
    
    # Create notification for user
    create_notification(
        user=booking.user,
        notification_type='BOOKING_APPROVED',
        title='Booking Approved',
        message=f'Your booking request for {booking.item.name} has been approved. Please sign the agreement and complete the payment.',
        booking=booking
    )
    
    messages.success(
        request, 
        f"Booking for {booking.item.name} has been approved. The user can now complete the remaining payment."
    )
    
    return redirect('rentals:owner_bookings')

# -------------------------
# Owner Reject Booking - Step 5b
# -------------------------
@login_required
def reject_booking(request, booking_id):
    """Step 5b: Owner rejects the booking request"""
    if request.user.role != 'owner':
        messages.error(request, "Access denied. Owner privileges required.")
        return redirect('rentals:user_dashboard')
    
    booking = get_object_or_404(Booking, id=booking_id, item__owner=request.user)
    
    if booking.status != 'PENDING':
        messages.warning(request, "This booking cannot be rejected.")
        return redirect('rentals:owner_bookings')
    
    with transaction.atomic():
        # Update booking status
        booking.status = 'REJECTED'
        booking.payment_status = 'REFUNDED'
        booking.refund_status = 'PENDING'
        booking.save()
        
        # Initiate refund
        try:
            refund = razorpay_client.payment.refund(booking.advance_transaction_id, {
                'amount': int(booking.advance_paid * 100),
                'notes': {
                    'reason': 'Booking rejected by owner',
                    'booking_id': booking.id
                }
            })
            booking.refund_transaction_id = refund['id']
            booking.refund_status = 'PROCESSED'
            booking.refund_processed_at = timezone.now()
            booking.save()
            
            # Create notification for user
            create_notification(
                user=booking.user,
                notification_type='BOOKING_REJECTED',
                title='Booking Rejected',
                message=f'Your booking request for {booking.item.name} has been rejected. Refund of ₹{booking.advance_paid} has been initiated.',
                booking=booking
            )
            
            messages.success(request, f"Booking rejected and refund initiated successfully.")
        except Exception as e:
            booking.refund_status = 'FAILED'
            booking.save()
            messages.warning(request, f"Booking rejected but refund failed. Please process manually.")
    
    return redirect('rentals:owner_bookings')

# -------------------------
# Revised Agreement Flow - Step 6
# -------------------------
@login_required
def agreement_page(request, booking_id):
    """Show rental agreement for user to accept"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # Only show agreement if booking is approved
    if booking.status != 'APPROVED' or booking.payment_status != 'ADVANCE_PAID':
        messages.warning(request, "Please wait for owner approval first.")
        return redirect('rentals:my_bookings')

    return render(request, 'rentals/agreement.html', {
        'booking': booking
    })

@login_required
def accept_agreement(request, booking_id):
    """User accepts the rental agreement - redirects to balance payment"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == "POST":
        if booking.status == 'APPROVED' and booking.payment_status == 'ADVANCE_PAID':
            booking.agreement_accepted = True
            booking.agreement_accepted_at = timezone.now()
            booking.save()
            
            # Create notification for owner
            create_notification(
                user=booking.item.owner,
                notification_type='AGREEMENT_SIGNED',
                title='Agreement Signed',
                message=f'{booking.user.username} has signed the agreement for {booking.item.name}.',
                booking=booking
            )
            
            messages.success(request, "Agreement accepted! Please complete the remaining payment.")
            # Redirect to balance payment page
            return redirect('rentals:process_balance_payment', booking_id=booking.id)
        else:
            messages.error(request, "Cannot accept agreement at this stage.")

    return redirect('rentals:agreement_page', booking_id=booking.id)

# -------------------------
# Process Balance Payment - Step 7
# -------------------------
@login_required
def process_balance_payment(request, booking_id):
    """User pays the remaining balance after accepting agreement"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    if booking.status != 'APPROVED' or not booking.agreement_accepted:
        messages.error(request, "Please accept the agreement first.")
        return redirect('rentals:agreement_page', booking_id=booking.id)
    
    if booking.payment_status in ['BALANCE_PAID', 'FULLY_PAID']:
        messages.warning(request, "Payment already completed for this booking.")
        return redirect('rentals:booking_confirmed', booking_id=booking.id)
    
    # Create Razorpay order for balance payment
    amount_in_paise = int(booking.balance_amount * 100)
    
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'balance_{booking.id}',
        'payment_capture': 1,
        'notes': {
            'booking_type': 'balance',
            'booking_id': booking.id,
            'item_name': booking.item.name
        }
    }
    
    try:
        razorpay_order = razorpay_client.order.create(data=order_data)
        request.session['balance_payment_order'] = {
            'order_id': razorpay_order['id'],
            'booking_id': booking.id
        }
        
    except Exception as e:
        messages.error(request, f"Error creating payment: {str(e)}")
        return redirect('rentals:my_bookings')
    
    context = {
        'booking': booking,
        'item': booking.item,
        'balance_amount': booking.balance_amount,
        'total_amount': booking.total_price,
        'advance_paid': booking.advance_paid,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': razorpay_order['id'],
        'amount_in_paise': amount_in_paise,
        'currency': 'INR',
        'callback_url': request.build_absolute_uri(reverse('rentals:balance_payment_callback')),
        'payment_type': 'balance'
    }
    
    return render(request, 'rentals/balance_payment.html', context)

# -------------------------
# Balance Payment Callback - Step 8
# -------------------------
@csrf_exempt
def balance_payment_callback(request):
    """Handle balance payment callback - Final success page"""
    if request.method == "POST":
        try:
            payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')
            
            payment_data = request.session.get('balance_payment_order')
            
            if not payment_data or razorpay_order_id != payment_data['order_id']:
                return render(request, 'rentals/payment_failed.html', {
                    'error': 'Invalid payment session'
                })
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params_dict)
                
                with transaction.atomic():
                    booking = Booking.objects.get(id=payment_data['booking_id'])
                    
                    # Update booking with balance payment
                    booking.payment_status = 'FULLY_PAID'
                    booking.balance_transaction_id = payment_id
                    booking.status = 'CONFIRMED'  # Rental active
                    booking.save()
                    
                    # Update owner profile stats
                    owner_profile, created = UserProfile.objects.get_or_create(user=booking.item.owner)
                    owner_profile.total_listings += 1
                    owner_profile.save()
                    
                    # Create notification for user
                    create_notification(
                        user=booking.user,
                        notification_type='PAYMENT_RECEIVED',
                        title='Payment Successful',
                        message=f'Your payment of ₹{booking.balance_amount} for {booking.item.name} has been received. Your booking is confirmed!',
                        booking=booking
                    )
                    
                    # Create notification for owner
                    create_notification(
                        user=booking.item.owner,
                        notification_type='PAYMENT_RECEIVED',
                        title='Payment Received',
                        message=f'{booking.user.username} has completed the payment for {booking.item.name}.',
                        booking=booking
                    )
                
                # Clear session data
                del request.session['balance_payment_order']
                
                # Redirect to final success page
                return redirect('rentals:booking_confirmed', booking_id=booking.id)
                
            except razorpay.errors.SignatureVerificationError:
                return render(request, 'rentals/payment_failed.html', {
                    'error': 'Payment signature verification failed'
                })
                
        except Exception as e:
            return render(request, 'rentals/payment_failed.html', {
                'error': str(e)
            })
    
    return HttpResponseBadRequest()

# -------------------------
# Booking Confirmed - Step 9 (Final Success Page)
# -------------------------
@login_required
def booking_confirmed(request, booking_id):
    """Final booking confirmation page after full payment"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    days = (booking.end_date - booking.start_date).days
    today = timezone.now().date()
    
    context = {
        'booking': booking,
        'item': booking.item,
        'total_days': days,
        'total_price': booking.total_price,
        'advance_paid': booking.advance_paid,
        'balance_paid': booking.balance_amount,
        'start_date': booking.start_date,
        'end_date': booking.end_date,
        'days_until_return': (booking.end_date - today).days if booking.end_date > today else 0,
    }
    
    return render(request, 'rentals/booking_confirmed.html', context)

# -------------------------
# Return Item (Owner marks as returned with damage inspection)
# -------------------------
@login_required
def return_item(request, booking_id):
    """Owner marks item as returned after inspection (with damage reporting)"""
    # Only owners can access this view
    if request.user.role != 'owner':
        messages.error(request, "Only the owner can mark items as returned.")
        return redirect('rentals:user_dashboard')
    
    booking = get_object_or_404(Booking, id=booking_id, item__owner=request.user)
    
    # Only confirmed bookings can be returned
    if booking.status != 'CONFIRMED':
        messages.error(request, "This booking cannot be returned.")
        return redirect('rentals:owner_bookings')
    
    if request.method == "POST":
        with transaction.atomic():
            # Get form data with proper error handling
            has_damage = request.POST.get('has_damage') == 'on'
            damage_description = request.POST.get('damage_description', '').strip()
            
            # Handle fine_amount - convert to float only if it's not empty
            fine_amount_str = request.POST.get('fine_amount', '0')
            try:
                fine_amount = float(fine_amount_str) if fine_amount_str else 0
            except ValueError:
                fine_amount = 0
            
            # Handle actual return date
            actual_return_date_str = request.POST.get('actual_return_date')
            if actual_return_date_str:
                actual_return_date = datetime.strptime(actual_return_date_str, "%Y-%m-%d").date()
            else:
                actual_return_date = timezone.now().date()
            
            booking.actual_return_date = actual_return_date
            
            # Calculate days late
            days_late = 0
            late_fee = 0
            
            # Check if returned late
            if booking.actual_return_date > booking.end_date:
                days_late = (booking.actual_return_date - booking.end_date).days
                booking.return_status = 'RETURNED_LATE'
                
                # Calculate late fee: 10% of daily rate per day late
                daily_rate = float(booking.item.price_per_day)
                late_fee_per_day = daily_rate * 0.1
                late_fee = days_late * late_fee_per_day
                
                booking.late_fee = late_fee
                booking.total_fine = late_fee
                
                # Create notification for user about late fee
                create_notification(
                    user=booking.user,
                    notification_type='LATE_FEE_CHARGED',
                    title='Late Fee Charged',
                    message=f'You have been charged a late fee of ₹{late_fee:.2f} for returning {booking.item.name} {days_late} day(s) late.',
                    booking=booking
                )
            else:
                booking.return_status = 'RETURNED_ON_TIME'
                booking.late_fee = 0
                booking.total_fine = 0
            
            # Handle damage report
            if has_damage and fine_amount > 0 and damage_description:
                DamageReport.objects.create(
                    booking=booking,
                    reported_by=request.user,
                    description=damage_description,
                    fine_amount=fine_amount
                )
                booking.damage_reported = True
                booking.damage_description = damage_description
                booking.total_fine = (booking.total_fine or 0) + fine_amount
                
                # Create notification for user about damage fine
                create_notification(
                    user=booking.user,
                    notification_type='DAMAGE_FINE',
                    title='Damage Fine Charged',
                    message=f'A fine of ₹{fine_amount:.2f} has been charged for damage to {booking.item.name}. Description: {damage_description}',
                    booking=booking
                )
            
            booking.status = 'RETURNED'
            booking.save()
            
            # Make item available again
            booking.item.is_available = True
            booking.item.save()
            
            # Create notification for user that item is returned
            create_notification(
                user=booking.user,
                notification_type='ITEM_RETURNED',
                title='Item Returned',
                message=f'Your rental of {booking.item.name} has been marked as returned by the owner. Total fine: ₹{booking.total_fine:.2f}',
                booking=booking
            )
            
            # Create notification for review
            create_notification(
                user=booking.user,
                notification_type='REVIEW_REQUEST',
                title='Rate Your Rental Experience',
                message=f'How was your experience with {booking.item.name}? Please leave a review.',
                booking=booking
            )
        
        # Success message with total fine
        if booking.total_fine > 0:
            messages.success(request, f"Item marked as returned successfully. Total fine charged: ₹{booking.total_fine:.2f}")
        else:
            messages.success(request, "Item marked as returned successfully. No fines charged.")
            
        return redirect('rentals:owner_bookings')
    
    # GET request - show return form with calculated values
    today = timezone.now().date()
    is_overdue = booking.end_date < today
    days_overdue = (today - booking.end_date).days if is_overdue else 0
    
    # Calculate estimated late fee for display
    estimated_late_fee = 0
    if is_overdue:
        daily_rate = float(booking.item.price_per_day)
        late_fee_per_day = daily_rate * 0.1
        estimated_late_fee = days_overdue * late_fee_per_day
    
    context = {
        'booking': booking,
        'now': today,
        'is_overdue': is_overdue,
        'days_overdue': days_overdue,
        'daily_rate': float(booking.item.price_per_day),
        'late_fee_per_day': float(booking.item.price_per_day) * 0.1,
        'estimated_late_fee': estimated_late_fee,
    }
    return render(request, 'rentals/return_item.html', context)

# -------------------------
# Submit Review (User only)
# -------------------------
@login_required
def submit_review(request, booking_id):
    """User submits a review after owner has marked item as returned"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Only returned bookings can be reviewed
    if booking.status != 'RETURNED':
        messages.error(request, "You can only review items that have been returned.")
        return redirect('rentals:my_bookings')
    
    # Check if review already submitted
    if booking.review_submitted:
        messages.warning(request, "You have already submitted a review for this item.")
        return redirect('rentals:my_bookings')
    
    if request.method == "POST":
        stars = int(request.POST.get('stars', 5))
        review_text = request.POST.get('review', '')
        
        with transaction.atomic():
            # Create rating
            rating = Rating.objects.create(
                booking=booking,
                item=booking.item,
                user=request.user,
                stars=stars,
                review=review_text
            )
            
            booking.review_submitted = True
            booking.review_text = review_text
            booking.review_stars = stars
            booking.status = 'COMPLETED'
            booking.save()
            
            # Update item's average rating
            booking.item.update_rating()
            
            # Update user profile stats
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.average_rating_as_renter = Rating.objects.filter(user=request.user).aggregate(Avg('stars'))['stars__avg']
            profile.save()
            
            # Update owner profile stats
            owner_profile, created = UserProfile.objects.get_or_create(user=booking.item.owner)
            owner_profile.average_rating_as_owner = Rating.objects.filter(item__owner=booking.item.owner).aggregate(Avg('stars'))['stars__avg']
            owner_profile.save()
            
            # Create notification for owner
            create_notification(
                user=booking.item.owner,
                notification_type='REVIEW_REQUEST',
                title='New Review Received',
                message=f'{booking.user.username} has rated your item {booking.item.name} {stars} stars.',
                booking=booking
            )
        
        messages.success(request, "Thank you for your review!")
        return redirect('rentals:my_bookings')
    
    return render(request, 'rentals/submit_review.html', {'booking': booking})

# -------------------------
# Agreement PDF
# -------------------------
@login_required
def agreement_pdf(request, booking_id):
    """Generate PDF of rental agreement"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Create HttpResponse with PDF header
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="agreement_{booking.id}.pdf"'
    
    # Create PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    
    # Add content
    p.setFont("Helvetica", 16)
    p.drawString(100, 800, "RENTAL AGREEMENT")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, 750, f"Booking ID: #{booking.id}")
    p.drawString(100, 730, f"Item: {booking.item.name}")
    p.drawString(100, 710, f"Customer: {booking.user.username}")
    p.drawString(100, 690, f"Owner: {booking.item.owner.username}")
    p.drawString(100, 670, f"Start Date: {booking.start_date}")
    p.drawString(100, 650, f"End Date: {booking.end_date}")
    p.drawString(100, 630, f"Quantity: {booking.quantity}")
    p.drawString(100, 610, f"Total Price: ₹{booking.total_price}")
    p.drawString(100, 590, f"Advance Paid: ₹{booking.advance_paid}")
    p.drawString(100, 570, f"Balance Paid: ₹{booking.balance_amount}")
    p.drawString(100, 550, f"Payment Status: {booking.payment_status}")
    p.drawString(100, 530, f"Agreement Accepted: {'Yes' if booking.agreement_accepted else 'No'}")
    if booking.agreement_accepted_at:
        p.drawString(100, 510, f"Accepted At: {booking.agreement_accepted_at.strftime('%Y-%m-%d %H:%M')}")
    
    p.showPage()
    p.save()
    
    # Get PDF from buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    response.write(pdf)
    return response

# -------------------------
# My Bookings View (User)
# -------------------------
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(
        user=request.user
    ).select_related('item').order_by('-created_at')
    
    # Add current date/time for template comparison
    now = timezone.now()

    return render(request, 'rentals/my_bookings.html', {
        'bookings': bookings,
        'now': now  # This enables date comparison in the template
    })

# -------------------------
# Owner Bookings View
# -------------------------
@login_required
def owner_bookings(request):
    """Enhanced owner bookings view with approval controls"""
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')
    
    status_filter = request.GET.get('status', None)
    today = timezone.now().date()
    
    bookings = Booking.objects.filter(
        item__owner=request.user
    ).select_related('user', 'item').order_by('-created_at')
    
    if status_filter:
        bookings = bookings.filter(status=status_filter)
        current_status = status_filter
    else:
        current_status = None
    
    # Add computed fields
    for booking in bookings:
        booking.days = (booking.end_date - booking.start_date).days
        booking.is_overdue = booking.status == 'CONFIRMED' and booking.end_date < today
        if booking.status == 'CONFIRMED':
            booking.days_until_return = (booking.end_date - today).days
    
    # Get counts for each status
    pending_count = Booking.objects.filter(item__owner=request.user, status='PENDING').count()
    approved_count = Booking.objects.filter(item__owner=request.user, status='APPROVED').count()
    agreement_pending_count = Booking.objects.filter(item__owner=request.user, status='AGREEMENT_PENDING').count()
    confirmed_count = Booking.objects.filter(item__owner=request.user, status='CONFIRMED').count()
    completed_count = Booking.objects.filter(item__owner=request.user, status='COMPLETED').count()
    rejected_count = Booking.objects.filter(item__owner=request.user, status='REJECTED').count()
    cancelled_count = Booking.objects.filter(item__owner=request.user, status='CANCELLED').count()
    returned_count = Booking.objects.filter(item__owner=request.user, status='RETURNED').count()
    total_count = bookings.count()
    
    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        'bookings': bookings,
        'current_status': current_status,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'agreement_pending_count': agreement_pending_count,
        'confirmed_count': confirmed_count,
        'completed_count': completed_count,
        'rejected_count': rejected_count,
        'cancelled_count': cancelled_count,
        'returned_count': returned_count,
        'total_count': total_count,
        'unread_notifications': unread_notifications,
        'now': today,
    }
    
    return render(request, 'rentals/owner_bookings.html', context)

# -------------------------
# Mark Booking Completed (Owner)
# -------------------------
@login_required
def mark_booking_completed(request, booking_id):
    """Mark a booking as completed (owner only)"""
    if request.user.role != 'owner':
        messages.error(request, "Access denied. Owner privileges required.")
        return redirect('rentals:user_dashboard')
    
    booking = get_object_or_404(Booking, id=booking_id, item__owner=request.user)
    
    if booking.status in ['CONFIRMED', 'RETURNED']:
        booking.status = 'COMPLETED'
        booking.save()
        
        # Make item available again if not already
        booking.item.is_available = True
        booking.item.save()
        
        # Create notification for user
        create_notification(
            user=booking.user,
            notification_type='BOOKING_APPROVED',
            title='Booking Completed',
            message=f'Your booking for {booking.item.name} has been marked as completed.',
            booking=booking
        )
        
        messages.success(request, f"Booking for {booking.item.name} marked as completed.")
    else:
        messages.warning(request, "This booking cannot be marked as completed.")
    
    return redirect('rentals:owner_bookings')

# -------------------------
# Update Booking Status (Legacy - Kept for compatibility)
# -------------------------
@login_required
def update_booking_status(request, booking_id):
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')
    
    booking = get_object_or_404(Booking, id=booking_id, item__owner=request.user)
    
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ['approved', 'rejected', 'completed', 'cancelled']:
            booking.status = new_status.upper()
            booking.save()
            
            # Update item availability
            if new_status == 'approved':
                booking.item.is_available = False
                booking.item.save()
            elif new_status in ['rejected', 'completed', 'cancelled']:
                booking.item.is_available = True
                booking.item.save()
            
            messages.success(request, f"Booking {new_status} successfully!")
    
    return redirect('rentals:owner_bookings')

# -------------------------
# Cancel Booking (User initiated)
# -------------------------
@login_required
def cancel_booking(request, booking_id):
    """User cancels a booking before owner approval"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    if booking.status == 'PENDING':
        with transaction.atomic():
            booking.status = 'CANCELLED'
            booking.payment_status = 'REFUNDED'
            booking.refund_status = 'PENDING'
            booking.save()
            
            # Initiate refund
            try:
                refund = razorpay_client.payment.refund(booking.advance_transaction_id, {
                    'amount': int(booking.advance_paid * 100),
                    'notes': {
                        'reason': 'Cancelled by user',
                        'booking_id': booking.id
                    }
                })
                booking.refund_transaction_id = refund['id']
                booking.refund_status = 'PROCESSED'
                booking.refund_processed_at = timezone.now()
                booking.save()
                
                # Create notification
                create_notification(
                    user=booking.user,
                    notification_type='REFUND_PROCESSED',
                    title='Refund Processed',
                    message=f'Your refund of ₹{booking.advance_paid} for {booking.item.name} has been processed.',
                    booking=booking
                )
                
                messages.success(request, "Booking cancelled and refund initiated.")
            except Exception as e:
                booking.refund_status = 'FAILED'
                booking.save()
                messages.warning(request, "Booking cancelled but refund failed. Contact support.")
    else:
        messages.error(request, "Cannot cancel this booking.")
    
    return redirect('rentals:my_bookings')

# -------------------------
# Toggle Item Availability
# -------------------------
@login_required
def toggle_item_availability(request, item_id):
    """Toggle item availability status"""
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')
    
    item = get_object_or_404(RentalItem, id=item_id, owner=request.user)
    item.is_available = not item.is_available
    item.save()
    
    status = "available" if item.is_available else "unavailable"
    messages.success(request, f"{item.name} is now {status}.")
    
    return redirect('rentals:owner_dashboard')

# -------------------------
# Item Management Views
# -------------------------
@login_required
def add_item(request):
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')

    if request.method == 'POST':
        form = RentalItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, "Item added successfully ✅")
            return redirect('rentals:owner_items')
    else:
        form = RentalItemForm()

    return render(request, 'rentals/add_item.html', {'form': form})

@login_required
def owner_items(request):
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')

    items = RentalItem.objects.filter(owner=request.user)
    return render(request, 'rentals/owner_items.html', {'items': items})

@login_required
def edit_item(request, item_id):
    """Edit an existing rental item"""
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')
    
    item = get_object_or_404(RentalItem, id=item_id, owner=request.user)
    
    if request.method == 'POST':
        form = RentalItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated successfully!")
            return redirect('rentals:owner_dashboard')
    else:
        form = RentalItemForm(instance=item)
    
    return render(request, 'rentals/edit_item.html', {'form': form, 'item': item})

@login_required
def delete_item(request, item_id):
    """Delete an item"""
    if request.user.role != 'owner':
        return redirect('rentals:user_dashboard')
    
    item = get_object_or_404(RentalItem, id=item_id, owner=request.user)
    
    # Check if item has active bookings
    active_bookings = Booking.objects.filter(
        item=item,
        status__in=['PENDING', 'APPROVED', 'AGREEMENT_PENDING', 'CONFIRMED']
    ).exists()
    
    if active_bookings:
        messages.error(request, "Cannot delete item with active bookings.")
    else:
        item.delete()
        messages.success(request, "Item deleted successfully!")
    
    return redirect('rentals:owner_dashboard')

# -------------------------
# User Dashboard
# -------------------------
@login_required
def user_dashboard(request):
    # Get search query and filters
    search_query = request.GET.get('q', '')
    selected_category = request.GET.get('category', '')
    radius = request.GET.get('radius', '')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    # Base queryset → only available items
    available_items = RentalItem.objects.filter(is_available=True)

    # Apply search filter
    if search_query:
        available_items = available_items.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) | 
            Q(category__icontains=search_query)
        )

    # Apply category filter
    if selected_category:
        available_items = available_items.filter(category=selected_category)

    # Get items with location data for map
    map_items_qs = available_items.exclude(
        Q(latitude__isnull=True) | Q(longitude__isnull=True)
    )
    
    # Prepare map items as JSON with category display
    map_items = []
    for item in map_items_qs:
        if item.latitude and item.longitude:
            # Calculate distance if user location provided
            distance = None
            if user_lat and user_lng:
                try:
                    distance = calculate_distance(
                        float(user_lat), 
                        float(user_lng), 
                        float(item.latitude), 
                        float(item.longitude)
                    )
                    # Apply radius filter
                    if radius and distance > float(radius):
                        continue
                except (ValueError, TypeError):
                    pass
            
            map_items.append({
                'id': item.id,
                'name': item.name,
                'lat': float(item.latitude),
                'lng': float(item.longitude),
                'price': float(item.price_per_day),
                'shop_name': item.owner.username,
                'category': item.category,
                'category_display': item.get_category_display(),
                'description': item.description[:100] if item.description else '',
                'distance': round(distance, 2) if distance else None,
                'average_rating': item.average_rating,
                'total_ratings': item.total_ratings,
            })
    
    # Get categories that have available items
    categories = RentalItem.objects.filter(
        is_available=True
    ).values_list('category', flat=True).distinct()

    # Apply distance calculation and radius filter to available_items for display
    items_for_display = []
    if user_lat and user_lng and radius:
        for item in available_items:
            if item.latitude and item.longitude:
                distance = calculate_distance(
                    float(user_lat), 
                    float(user_lng), 
                    float(item.latitude), 
                    float(item.longitude)
                )
                if distance <= float(radius):
                    item.distance = round(distance, 2)
                    items_for_display.append(item)
    else:
        items_for_display = available_items

    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    context = {
        'available_items': items_for_display,
        'map_items': map_items,
        'items': items_for_display if (search_query or radius) else [],
        'query': search_query,
        'radius': radius,
        'selected_category': selected_category,
        'categories': categories,
        'total_items_count': RentalItem.objects.filter(is_available=True).count(),
        'nearby_items_count': len(map_items) if user_lat and user_lng else 0,
        'categories_count': categories.count(),
        'has_more_items': len(items_for_display) > 12,
        'unread_notifications': unread_notifications,
    }

    return render(request, 'rentals/user_dashboard.html', context)

# -------------------------
# Item Detail View
# -------------------------
@login_required
def item_detail(request, item_id):
    item = get_object_or_404(RentalItem, id=item_id)
    
    from datetime import date, timedelta
    min_date = date.today() + timedelta(days=2)
    
    similar_items = RentalItem.objects.filter(
        category=item.category,
        is_available=True
    ).exclude(id=item.id)[:4]
    
    # Get user's bookings for this item
    user_bookings = Booking.objects.filter(
        user=request.user,
        item=item
    ).order_by('-created_at')
    
    # Get active bookings by other users
    active_bookings = Booking.objects.filter(
        item=item,
        status__in=['CONFIRMED', 'APPROVED', 'AGREEMENT_PENDING'],
        end_date__gte=date.today()
    ).exclude(user=request.user)
    
    # Get pending bookings by other users
    pending_bookings = Booking.objects.filter(
        item=item,
        status='PENDING'
    ).exclude(user=request.user)
    
    # Get reviews
    reviews = Rating.objects.filter(item=item).select_related('user').order_by('-created_at')[:5]
    
    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    context = {
        "item": item,
        "similar_items": similar_items,
        "reviews": reviews,
        "min_date": min_date.strftime('%Y-%m-%d'),
        "average_rating": item.average_rating,
        "total_ratings": item.total_ratings,
        "user_bookings": user_bookings,
        "active_bookings": active_bookings,
        "pending_bookings": pending_bookings,
        "unread_notifications": unread_notifications,
        "now": date.today(),
    }

    return render(request, "rentals/item_detail.html", context)

# -------------------------
# Search Nearby Items
# -------------------------
@login_required
def search_nearby_items(request):
    user_lat = request.GET.get('lat')
    user_lon = request.GET.get('lng')
    radius = float(request.GET.get('radius', 5))

    items = RentalItem.objects.filter(
        is_available=True,
        latitude__isnull=False,
        longitude__isnull=False
    )

    nearby_items = []
    items_json = []  # For map markers

    if user_lat and user_lon:
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)

            for item in items:
                distance = calculate_distance(
                    user_lat,
                    user_lon,
                    item.latitude,
                    item.longitude
                )

                if distance <= radius:
                    item.distance = round(distance, 2)
                    nearby_items.append(item)
                    
                    # Add to JSON list for map
                    items_json.append({
                        'id': item.id,
                        'name': item.name,
                        'lat': float(item.latitude),
                        'lng': float(item.longitude),
                        'price': float(item.price_per_day),
                        'distance': round(distance, 2),
                        'category_display': item.get_category_display(),
                        'average_rating': item.average_rating,
                    })

            nearby_items.sort(key=lambda x: x.distance)

        except (ValueError, TypeError):
            nearby_items = []
            items_json = []

    return render(request, "rentals/nearby_items.html", {
        "items": nearby_items,
        "items_json": json.dumps(items_json),
        "radius": radius,
        "user_lat": user_lat,
        "user_lng": user_lon
    })

# -------------------------
# Management Command to Check Return Reminders
# -------------------------
def check_return_reminders():
    """Check for bookings that need return reminders (to be called by cron job)"""
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # Bookings ending tomorrow
    upcoming_returns = Booking.objects.filter(
        status='CONFIRMED',
        end_date=tomorrow,
        return_reminder_sent=False
    )
    
    for booking in upcoming_returns:
        create_notification(
            user=booking.user,
            notification_type='RETURN_REMINDER',
            title='Return Reminder',
            message=f'Your rental of {booking.item.name} is due tomorrow. Please arrange for return.',
            booking=booking
        )
        booking.return_reminder_sent = True
        booking.save()
    
    # Overdue bookings
    overdue_bookings = Booking.objects.filter(
        status='CONFIRMED',
        end_date__lt=timezone.now().date()
    )
    
    for booking in overdue_bookings:
        days_overdue = (timezone.now().date() - booking.end_date).days
        create_notification(
            user=booking.user,
            notification_type='RETURN_OVERDUE',
            title='Item Overdue',
            message=f'Your rental of {booking.item.name} is {days_overdue} day(s) overdue. Please return immediately.',
            booking=booking
        )