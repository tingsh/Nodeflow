from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

from apps.subscriptions.helpers import (
    get_subscription_urls,
    provision_subscription,
)
from apps.subscriptions.wrappers import SubscriptionWrapper
from apps.teams.decorators import login_and_team_required
from apps.utils.billing import get_stripe_module


@login_required
def subscription_confirm(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        messages.error(
            request,
            "Couldn't find a Stripe session for your payment. If you think this is an error, please get in touch.",
        )
        return TemplateResponse(request, "400.html", status=400)

    session = get_stripe_module().checkout.Session.retrieve(session_id)
    payment_status = session["payment_status"]
    if payment_status != "paid":
        messages.error(
            request,
            "Sorry, it looks like your payment didn't go through. If you think this is an error, please get in touch.",
        )
        return TemplateResponse(request, "400.html", status=400)
    client_reference_id = int(session.client_reference_id)
    subscription_holder = request.user.teams.select_related("subscription", "customer").get(id=client_reference_id)
    if not subscription_holder.subscription or subscription_holder.subscription.id != session.subscription:
        # provision subscription
        djstripe_subscription = provision_subscription(subscription_holder, session.subscription)
    else:
        # already provisioned (likely by webhook)
        djstripe_subscription = subscription_holder.subscription

    subscription_name = SubscriptionWrapper(djstripe_subscription).display_name
    messages.success(request, f"You've successfully signed up for {subscription_name}. Thanks for the support!")
    return HttpResponseRedirect(get_subscription_urls(subscription_holder)["subscription_details"])


@login_and_team_required
def checkout_canceled(request, team_slug):
    subscription_holder = request.team
    messages.info(request, "Your upgrade was canceled.")
    return HttpResponseRedirect(get_subscription_urls(subscription_holder)["subscription_details"])


@login_required
def checkout(request, plan_slug):
    from django.urls import reverse

    from apps.subscriptions.helpers import create_stripe_checkout_session
    from apps.subscriptions.metadata import get_active_products_with_metadata

    subscription_holder = request.team
    if not subscription_holder:
        messages.error(request, "Please create a team before subscribing.")
        return HttpResponseRedirect("/")

    # Find active product matching the slug
    active_products = get_active_products_with_metadata()
    target_product = None
    for p in active_products:
        if p.metadata.slug == plan_slug:
            target_product = p
            break

    if not target_product:
        messages.error(request, f"Plan '{plan_slug}' not found.")
        return HttpResponseRedirect(reverse("web:home"))

    # Get the active price (defaulting to monthly or first available)
    price = None
    for interval in ["month", "year"]:
        price = target_product._get_price(interval, fail_hard=False)
        if price:
            break

    if not price:
        # Offline simulation fallback
        messages.warning(request, f"Stripe price not configured for '{plan_slug}'. Simulating checkout locally.")

        from apps.subscriptions.enforcement import get_latency_limit_for_team

        previous_interval = get_latency_limit_for_team(subscription_holder)

        # Provision the mock subscription
        mock_sub_id = f"sub_mock_{plan_slug}"

        if not subscription_holder.customer:
            from djstripe.models import Customer

            customer = Customer.objects.create(subscriber=subscription_holder, id=f"cus_mock_{subscription_holder.id}")
            subscription_holder.customer = customer
            subscription_holder.save()

        from djstripe.models import Price as StripePrice
        from djstripe.models import Product as StripeProduct
        from djstripe.models import Subscription

        prod, _ = StripeProduct.objects.get_or_create(
            id=target_product.metadata.stripe_id, defaults={"name": target_product.metadata.name}
        )
        pr, _ = StripePrice.objects.get_or_create(
            id=f"price_mock_{plan_slug}", defaults={"product": prod, "unit_amount": 9900, "currency": "usd"}
        )

        sub, _ = Subscription.objects.get_or_create(
            id=mock_sub_id,
            defaults={
                "customer": subscription_holder.customer,
                "price": pr,
                "status": "active",
            },
        )
        subscription_holder.subscription = sub
        subscription_holder.save()
        subscription_holder.clear_cached_subscription()
        new_interval = get_latency_limit_for_team(subscription_holder)

        from apps.devices.plan_reconciliation import queue_team_plan_reconciliation

        queue_team_plan_reconciliation(
            subscription_holder,
            previous_interval,
            new_interval,
            f"local-checkout:{mock_sub_id}:{new_interval}",
        )

        messages.success(request, f"Successfully simulated subscription to {target_product.metadata.name}!")
        return HttpResponseRedirect(reverse("web_team:home", args=[subscription_holder.slug]))

    try:
        checkout_session = create_stripe_checkout_session(
            subscription_holder,
            price.id,
            request.user,
        )
        return HttpResponseRedirect(checkout_session.url)
    except Exception as e:
        messages.error(request, f"Failed to start checkout session: {e}")
        return HttpResponseRedirect(reverse("web_team:home", args=[subscription_holder.slug]))
