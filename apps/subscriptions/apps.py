from django.apps import AppConfig


class SubscriptionConfig(AppConfig):
    name = "apps.subscriptions"
    label = "subscriptions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import webhooks  # noqa F401
        from . import signals  # noqa F401

        # Monkey-patch djstripe StripeModel._attach_objects_post_save_hook to fix a ValueError
        # bug when syncing Products that have default_price containing a Plan object ID instead of a Price object.
        import djstripe.models.base
        from django.db import models
        from djstripe.settings import djstripe_settings

        def patched_post_save_hook(
            self, cls, data, api_key=djstripe_settings.STRIPE_SECRET_KEY, pending_relations=None
        ):
            unprocessed_pending_relations = []
            if pending_relations is not None:
                for post_save_relation in pending_relations:
                    object_id, field, id_ = post_save_relation

                    if self.id == id_ and isinstance(self, field.related_model):
                        target = field.model.objects.get(id=object_id)
                        setattr(target, field.name, self)
                        if isinstance(field, models.OneToOneRel):
                            self.save()
                        else:
                            target.save()
                            self.refresh_from_db()
                    else:
                        unprocessed_pending_relations.append(post_save_relation)

                if len(pending_relations) != len(unprocessed_pending_relations):
                    pending_relations[:] = unprocessed_pending_relations

        djstripe.models.base.StripeModel._attach_objects_post_save_hook = patched_post_save_hook
