REQUEST_STATUS_INITIAL = 0
REQUEST_STATUS_ACCEPTED = 1
REQUEST_STATUS_REJECTED = 2

REQUEST_STATUS_CHOICES = (
    (REQUEST_STATUS_INITIAL, 'Sent'),
    (REQUEST_STATUS_ACCEPTED, 'Accepted'),
    (REQUEST_STATUS_REJECTED, 'Rejected')
)
