from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.utils.models import BaseModel


class MessageTypes(models.TextChoices):
    HUMAN = "HUMAN", _("Human")
    AI = "AI", _("AI")
    SYSTEM = "SYSTEM", _("System")


class Chat(BaseModel):
    """
    A chat (session) instance.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="chats"
    )
    name = models.CharField(max_length=100, default="Unnamed Chat")

    def __str__(self):
        return f"{self.name} ({self.user})"

    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE, null=True, blank=True, related_name="chats"
    )

    def get_openai_messages(self) -> list[dict]:
        """
        Return a list of messages ready to pass to the OpenAI ChatCompletion API.
        """
        return [m.to_openai_dict() for m in self.messages.all()]


class ChatMessage(BaseModel):
    """
    A message in a Chat.
    """

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    message_type = models.CharField(max_length=10, choices=MessageTypes.choices)
    content = models.TextField()

    class Meta:
        ordering = ["created_at"]

    @property
    def is_ai_message(self) -> bool:
        return self.message_type == MessageTypes.AI

    @property
    def is_human_message(self) -> bool:
        return self.message_type == MessageTypes.HUMAN

    def to_openai_dict(self) -> dict:
        return {
            "role": self.get_openai_role(),
            "content": self.content,
        }

    def get_openai_role(self):
        if self.message_type == MessageTypes.HUMAN:
            return "user"
        elif self.message_type == MessageTypes.AI:
            return "assistant"
        else:
            return "system"


class ChatUsage(BaseModel):
    """
    Track chat usage per team.
    """

    team = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="chat_usage")
    year = models.IntegerField()
    month = models.IntegerField()
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ("team", "year", "month")

    def __str__(self):
        return f"{self.team.name} - {self.year}/{self.month}: {self.count}"

    @classmethod
    def get_count_for_team(cls, team):
        now = timezone.now()
        usage, _ = cls.objects.get_or_create(team=team, year=now.year, month=now.month)
        return usage.count

    @classmethod
    def increment_count_for_team(cls, team):
        now = timezone.now()
        usage, _ = cls.objects.get_or_create(team=team, year=now.year, month=now.month)
        usage.count += 1
        usage.save()
