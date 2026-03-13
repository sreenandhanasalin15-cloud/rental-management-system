from django.urls import path
from . import views

app_name = "rentals"

urlpatterns = [
    # Owner Dashboard URLs
    path('owner/dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/add-item/', views.add_item, name='add_item'),
    path('owner/items/', views.owner_items, name='owner_items'),
    path('owner/edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('owner/delete-item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('owner/bookings/', views.owner_bookings, name='owner_bookings'),
    path('toggle-availability/<int:item_id>/', views.toggle_item_availability, name='toggle_availability'),
    
    # User Dashboard URLs
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('nearby/', views.search_nearby_items, name='nearby_items'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    
    # Notification URLs (single instance)
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/unread-count/', views.get_unread_notification_count, name='unread_notification_count'),
    
    # Booking Flow URLs
    path('book/<int:item_id>/', views.book_item, name='book_item'),
    
    # Payment URLs - Advance Payment (30%)
    path('payment/advance/<int:item_id>/', views.process_advance_payment, name='process_advance_payment'),
    path('payment-callback/', views.payment_callback, name='payment_callback'),
    
    # Payment URLs - Balance Payment (70%)
    path('payment/balance/<int:booking_id>/', views.process_balance_payment, name='process_balance_payment'),
    path('payment/balance-callback/', views.balance_payment_callback, name='balance_payment_callback'),
    
    # Legacy payment URL (keeping for backward compatibility)
    # path('payment/<int:item_id>/', views.process_payment, name='process_payment'),
    
    # Booking Status URLs
    path('booking/pending/<int:booking_id>/', views.booking_pending, name='booking_pending'),
    path('booking/confirmed/<int:booking_id>/', views.booking_confirmed, name='booking_confirmed'),
    
    # Owner Approval URLs
    path('approve-booking/<int:booking_id>/', views.approve_booking, name='approve_booking'),
    path('reject-booking/<int:booking_id>/', views.reject_booking, name='reject_booking'),
    path('mark-completed/<int:booking_id>/', views.mark_booking_completed, name='mark_completed'),
    
    # User Actions
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('return-item/<int:booking_id>/', views.return_item, name='return_item'),
    path('submit-review/<int:booking_id>/', views.submit_review, name='submit_review'),
    
    # Agreement URLs
    path('agreement/<int:booking_id>/', views.agreement_page, name='agreement_page'),
    path('agreement/<int:booking_id>/accept/', views.accept_agreement, name='accept_agreement'),
    path('agreement-pdf/<int:booking_id>/', views.agreement_pdf, name='agreement_pdf'),
    
    # Update Booking Status (Legacy - keeping for compatibility)
    path('update-booking-status/<int:booking_id>/', views.update_booking_status, name='update_booking_status'),
]