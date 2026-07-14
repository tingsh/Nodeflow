from allauth.account.models import EmailAddress
from allauth.account.views import SignupView
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.users.models import CustomUser

from ..invitations import clear_invite_from_session, process_invitation
from ..models import Invitation, Team
from ..roles import is_member


def accept_invitation(request, invitation_id):
    invitation = get_object_or_404(Invitation, id=invitation_id)
    if not invitation.team.is_active:
        clear_invite_from_session(request)
        raise Http404
    if not invitation.is_accepted:
        # set invitation in the session in case needed later - e.g. to redirect after login
        request.session["invitation_id"] = invitation_id
    else:
        clear_invite_from_session(request)
    if request.user.is_authenticated and is_member(request.user, invitation.team):
        messages.info(
            request,
            _("It looks like you're already a member of {team}. You've been redirected.").format(
                team=invitation.team.name
            ),
        )
        return HttpResponseRedirect(reverse("web_team:home", args=[invitation.team.slug]))

    if request.method == "POST":
        # accept invitation workflow
        if not request.user.is_authenticated:
            messages.error(request, _("Please log in again to accept your invitation."))
            return HttpResponseRedirect(reverse("account_login"))
        else:
            if invitation.is_accepted:
                messages.error(request, _("Sorry, it looks like that invitation link has expired."))
                return HttpResponseRedirect(reverse("web:home"))
            else:
                try:
                    from django.db import IntegrityError
                    process_invitation(invitation, request.user)
                    messages.success(request, _("You successfully joined {}").format(invitation.team.name))
                except IntegrityError:
                    messages.info(request, _("You are already a member of {}.").format(invitation.team.name))
                clear_invite_from_session(request)
                return HttpResponseRedirect(reverse("web_team:home", args=[invitation.team.slug]))

    account_exists = CustomUser.objects.filter(email=invitation.email).exists()
    owned_email_address = None
    user_team_count = 0
    if request.user.is_authenticated:
        owned_email_address = EmailAddress.objects.filter(email=invitation.email, user=request.user).first()
        user_team_count = request.user.teams.filter(status=Team.Status.ACTIVE).count()
    return render(
        request,
        "teams/accept_invite.html",
        {
            "invitation": invitation,
            "account_exists": account_exists,
            "user_owns_email": bool(owned_email_address),
            "email_verified": owned_email_address and owned_email_address.verified,
            "user_team_count": user_team_count,
        },
    )


class SignupAfterInvite(SignupView):
    @cached_property
    def invitation(self) -> Invitation:
        from ..models import Invitation

        invitation_id = self.kwargs["invitation_id"]

        invitation = get_object_or_404(Invitation, id=invitation_id)
        if invitation.is_accepted:
            messages.error(self.request, _("Sorry, it looks like that invitation link has expired."))
            raise Http404
        return invitation

    def get_form_class(self):
        from allauth.account.forms import SignupForm
        return SignupForm

    def get_initial(self):
        initial = super().get_initial()
        if self.invitation:
            initial["email"] = self.invitation.email
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.invitation:
            context["invitation"] = self.invitation
        return context
