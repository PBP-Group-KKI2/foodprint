from django.db.models import F
from main.models import Profile, POINTS_PER_POST


def award_points(user, amount=POINTS_PER_POST):
    """Add points to a user's profile. Safe if the user has no profile."""
    Profile.objects.filter(user=user).update(points=F('points') + amount)