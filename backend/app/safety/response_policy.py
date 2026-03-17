from app.schemas.chat import AssistantReply, ModerationResult


class ResponsePolicy:
    def apply(
        self,
        moderation: ModerationResult,
        reply: AssistantReply | None = None,
    ) -> AssistantReply:
        if not moderation.allowed:
            return AssistantReply(
                text="I can’t help with that request, but I can help with a safer alternative.",
                emotion="concerned",
                should_speak=True,
            )

        if reply is None:
            return AssistantReply(
                text="I might have missed that. Could you rephrase your message?",
                emotion="neutral",
                should_speak=True,
            )

        return reply
