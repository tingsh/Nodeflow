import logging

from django.core.mail import mail_admins
from django.db import transaction
from djstripe.event_handlers import djstripe_receiver
from djstripe.models import Customer, Price, Subscription

from apps.teams.models import Team

from .helpers import provision_subscription

log = logging.getLogger("novena_hub.subscription")


def _event_key(event, fallback):
    return str(getattr(event, "id", None) or getattr(event, "pk", None) or fallback)


@djstripe_receiver("checkout.session.completed")
def checkout_session_completed(event, **kwargs):
    """
    This webhook is called when a customer signs up for a subscription via Stripe Checkout.

    We must then provision the subscription and assign it to the appropriate user/team.
    """
    session = event.data["object"]
    # only process subscriptions created by this module or that have a subscription set
    if session["metadata"].get("source") == "subscriptions" or session.get("subscription"):
        client_reference_id = session.get("client_reference_id")
        subscription_id = session.get("subscription")
        subscription_holder = Team.objects.get(id=client_reference_id)
        provision_subscription(
            subscription_holder,
            subscription_id,
            source_key=f"stripe:{_event_key(event, subscription_id)}",
        )


@djstripe_receiver("customer.subscription.updated")
def update_customer_subscription(event, **kwargs):
    """
    This webhook is called when a customer updates their subscription via the Stripe
    billing portal.

    There are a few scenarios this can happen - if they are upgrading, downgrading
    cancelling (at the period end) or renewing after a cancellation.

    We update the subscription in place based on the possible fields, and
    these updates automatically trickle down to the user/team that holds the subscription.

    Stripe docs: https://stripe.com/docs/customer-management/integrate-customer-portal#webhooks
    """
    # check if we can handle this change
    if has_multiple_items(event.data):
        logging.warning("Not processing changes to Stripe subscription because it has multiple products.")
        return

    new_price = get_price_data(event.data)
    subscription_id = get_subscription_id(event.data)

    # find associated subscription and change the price details accordingly
    dj_subscription = Subscription.objects.get(id=subscription_id)
    team = Team.objects.filter(subscription=dj_subscription).first()
    previous_interval = None
    if team:
        from apps.subscriptions.enforcement import get_latency_limit_for_team

        previous_interval = get_latency_limit_for_team(team)
    subscription_item = dj_subscription.items.get()
    subscription_item.price = Price.objects.get(id=new_price["id"])
    subscription_item.save()
    dj_subscription.cancel_at_period_end = get_cancel_at_period_end(event.data)
    dj_subscription.save()
    if team:
        team.clear_cached_subscription()
        new_interval = get_latency_limit_for_team(team)

        transaction.on_commit(
            lambda: __import__(
                "apps.devices.plan_reconciliation",
                fromlist=["queue_team_plan_reconciliation"],
            ).queue_team_plan_reconciliation(
                Team.objects.get(pk=team.pk),
                previous_interval,
                new_interval,
                f"stripe:{_event_key(event, subscription_id)}",
            )
        )


@djstripe_receiver("customer.subscription.deleted")
def email_admins_when_subscriptions_canceled(event, **kwargs):
    # example webhook handler to notify admins when a subscription is deleted/canceled
    try:
        customer_email = Customer.objects.get(id=event.data["object"]["customer"]).email
    except Customer.DoesNotExist:
        customer_email = "unavailable"

    subscription_id = event.data["object"].get("id")
    team = Team.objects.filter(subscription_id=subscription_id).first()
    if team:
        from apps.subscriptions.enforcement import DEFAULT_LATENCY_LIMIT, get_latency_limit_for_team

        previous_interval = get_latency_limit_for_team(team)
        transaction.on_commit(
            lambda: __import__(
                "apps.devices.plan_reconciliation",
                fromlist=["queue_team_plan_reconciliation"],
            ).queue_team_plan_reconciliation(
                Team.objects.get(pk=team.pk),
                previous_interval,
                DEFAULT_LATENCY_LIMIT,
                f"stripe:{_event_key(event, subscription_id)}",
            )
        )

    mail_admins(
        "Someone just canceled their subscription!",
        f"Their email was {customer_email}",
        fail_silently=True,
    )


def has_multiple_items(stripe_event_data):
    return len(stripe_event_data["object"]["items"]["data"]) > 1


def get_price_data(stripe_event_data):
    return stripe_event_data["object"]["items"]["data"][0]["price"]


def get_subscription_id(stripe_event_data):
    return stripe_event_data["object"]["items"]["data"][0]["subscription"]


def get_cancel_at_period_end(stripe_event_data):
    return stripe_event_data["object"]["cancel_at_period_end"]
