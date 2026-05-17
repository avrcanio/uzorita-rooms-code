from reception.models import EvisitorGuestStatus, Guest, Reservation


def evisitor_status_for_guest(guest: Guest) -> str:
    status = (guest.evisitor_status or "").strip()
    if status in {c[0] for c in EvisitorGuestStatus.choices}:
        return status
    return EvisitorGuestStatus.NOT_SENT


def evisitor_summary_for_guests(guests) -> str:
    guest_list = list(guests)
    if not guest_list:
        return "none"
    statuses = [evisitor_status_for_guest(g) for g in guest_list]
    if all(s == EvisitorGuestStatus.CHECKED_OUT for s in statuses):
        return "checked_out"
    if all(s in (EvisitorGuestStatus.SENT, EvisitorGuestStatus.CHECKED_OUT) for s in statuses):
        return "complete"
    if all(s == EvisitorGuestStatus.SENT for s in statuses):
        return "complete"
    return "incomplete"


def evisitor_summary_for_reservation(reservation: Reservation) -> str:
    if hasattr(reservation, "_prefetched_objects_cache") and "guests" in getattr(
        reservation, "_prefetched_objects_cache", {}
    ):
        return evisitor_summary_for_guests(reservation.guests.all())
    return evisitor_summary_for_guests(
        Guest.objects.filter(reservation_id=reservation.pk)
    )
