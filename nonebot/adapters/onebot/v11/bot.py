import re
from typing import TYPE_CHECKING, Any, Union

from nonebot.typing import overrides
from nonebot.message import handle_event

from nonebot.adapters import Bot as BaseBot

from .utils import log, escape
from .message import Message, MessageSegment
from .event import Event, Reply, MessageEvent


async def _check_reply(bot: "Bot", event: MessageEvent):
    """
    :说明:

      检查消息中存在的回复，去除并赋值 ``event.reply``, ``event.to_me``

    :参数:

      * ``bot: Bot``: Bot 对象
      * ``event: Event``: Event 对象
    """
    try:
        index = list(map(lambda x: x.type == "reply", event.message)).index(True)
    except ValueError:
        return
    msg_seg = event.message[index]
    try:
        event.reply = Reply.parse_obj(await bot.get_msg(message_id=msg_seg.data["id"]))
    except Exception as e:
        log("WARNING", f"Error when getting message reply info: {repr(e)}", e)
        return
    # ensure string comparation
    if str(event.reply.sender.user_id) == str(event.self_id):
        event.to_me = True
    del event.message[index]
    if len(event.message) > index and event.message[index].type == "at":
        del event.message[index]
    if len(event.message) > index and event.message[index].type == "text":
        event.message[index].data["text"] = event.message[index].data["text"].lstrip()
        if not event.message[index].data["text"]:
            del event.message[index]
    if not event.message:
        event.message.append(MessageSegment.text(""))


def _check_at_me(bot: "Bot", event: MessageEvent):
    """
    :说明:

      检查消息开头或结尾是否存在 @机器人，去除并赋值 ``event.to_me``

    :参数:

      * ``bot: Bot``: Bot 对象
      * ``event: Event``: Event 对象
    """
    if not isinstance(event, MessageEvent):
        return

    # ensure message not empty
    if not event.message:
        event.message.append(MessageSegment.text(""))

    if event.message_type == "private":
        event.to_me = True
    else:

        def _is_at_me_seg(segment: MessageSegment):
            return segment.type == "at" and str(segment.data.get("qq", "")) == str(
                event.self_id
            )

        # check the first segment
        if _is_at_me_seg(event.message[0]):
            event.to_me = True
            event.message.pop(0)
            if event.message and event.message[0].type == "text":
                event.message[0].data["text"] = event.message[0].data["text"].lstrip()
                if not event.message[0].data["text"]:
                    del event.message[0]
            if event.message and _is_at_me_seg(event.message[0]):
                event.message.pop(0)
                if event.message and event.message[0].type == "text":
                    event.message[0].data["text"] = (
                        event.message[0].data["text"].lstrip()
                    )
                    if not event.message[0].data["text"]:
                        del event.message[0]

        if not event.to_me:
            # check the last segment
            i = -1
            last_msg_seg = event.message[i]
            if (
                last_msg_seg.type == "text"
                and not last_msg_seg.data["text"].strip()
                and len(event.message) >= 2
            ):
                i -= 1
                last_msg_seg = event.message[i]

            if _is_at_me_seg(last_msg_seg):
                event.to_me = True
                del event.message[i:]

        if not event.message:
            event.message.append(MessageSegment.text(""))


def _check_nickname(bot: "Bot", event: MessageEvent):
    """
    :说明:

      检查消息开头是否存在昵称，去除并赋值 ``event.to_me``

    :参数:

      * ``bot: Bot``: Bot 对象
      * ``event: Event``: Event 对象
    """
    first_msg_seg = event.message[0]
    if first_msg_seg.type != "text":
        return

    first_text = first_msg_seg.data["text"]

    nicknames = set(filter(lambda n: n, bot.config.nickname))
    if nicknames:
        # check if the user is calling me with my nickname
        nickname_regex = "|".join(nicknames)
        m = re.search(rf"^({nickname_regex})([\s,，]*|$)", first_text, re.IGNORECASE)
        if m:
            nickname = m.group(1)
            log("DEBUG", f"User is calling me {nickname}")
            event.to_me = True
            first_msg_seg.data["text"] = first_text[m.end() :]


class Bot(BaseBot):
    """
    OneBot v11 协议 Bot 适配。
    """

    # @overrides(BaseBot)
    # async def _call_api(self, api: str, **data) -> Any:
    #     log("DEBUG", f"Calling API <y>{api}</y>")
    #     if isinstance(self.request, WebSocket):
    #         seq = ResultStore.get_seq()
    #         json_data = json.dumps(
    #             {"action": api, "params": data, "echo": {"seq": seq}},
    #             cls=DataclassEncoder,
    #         )
    #         await self.request.send(json_data)
    #         return _handle_api_result(
    #             await ResultStore.fetch(seq, self.config.api_timeout)
    #         )

    #     elif isinstance(self.request, HTTPRequest):
    #         api_root = self.config.api_root.get(self.self_id)
    #         if not api_root:
    #             raise ApiNotAvailable
    #         elif not api_root.endswith("/"):
    #             api_root += "/"

    #         headers = {"Content-Type": "application/json"}
    #         if self.onebot_config.access_token is not None:
    #             headers["Authorization"] = "Bearer " + self.onebot_config.access_token

    #         try:
    #             async with httpx.AsyncClient(
    #                 headers=headers, follow_redirects=True
    #             ) as client:
    #                 response = await client.post(
    #                     api_root + api,
    #                     content=json.dumps(data, cls=DataclassEncoder),
    #                     timeout=self.config.api_timeout,
    #                 )

    #             if 200 <= response.status_code < 300:
    #                 result = response.json()
    #                 return _handle_api_result(result)
    #             raise NetworkError(
    #                 f"HTTP request received unexpected "
    #                 f"status code: {response.status_code}"
    #             )
    #         except httpx.InvalidURL:
    #             raise NetworkError("API root url invalid")
    #         except httpx.HTTPError:
    #             raise NetworkError("HTTP request failed")

    # @overrides(BaseBot)
    # async def call_api(self, api: str, **data) -> Any:
    #     """
    #     :说明:

    #       调用 OneBot 协议 API

    #     :参数:

    #       * ``api: str``: API 名称
    #       * ``**data: Any``: API 参数

    #     :返回:

    #       - ``Any``: API 调用返回数据

    #     :异常:

    #       - ``NetworkError``: 网络错误
    #       - ``ActionFailed``: API 调用失败
    #     """
    #     return await super().call_api(api, **data)

    async def handle_event(self, event: Event) -> None:
        if isinstance(event, MessageEvent):
            await _check_reply(self, event)
            _check_at_me(self, event)
            _check_nickname(self, event)

        await handle_event(self, event)

    @overrides(BaseBot)
    async def send(
        self,
        event: Event,
        message: Union[str, Message, MessageSegment],
        at_sender: bool = False,
        **kwargs,
    ) -> Any:
        """
        :说明:

          根据 ``event``  向触发事件的主体发送消息。

        :参数:

          * ``event: Event``: Event 对象
          * ``message: Union[str, Message, MessageSegment]``: 要发送的消息
          * ``at_sender: bool``: 是否 @ 事件主体
          * ``**kwargs``: 覆盖默认参数

        :返回:

          - ``Any``: API 调用返回数据

        :异常:

          - ``ValueError``: 缺少 ``user_id``, ``group_id``
          - ``NetworkError``: 网络错误
          - ``ActionFailed``: API 调用失败
        """
        message = (
            escape(message, escape_comma=False) if isinstance(message, str) else message
        )
        msg = message if isinstance(message, Message) else Message(message)

        at_sender = at_sender and bool(getattr(event, "user_id", None))

        params = {}
        if getattr(event, "user_id", None):
            params["user_id"] = getattr(event, "user_id")
        if getattr(event, "group_id", None):
            params["group_id"] = getattr(event, "group_id")
        params.update(kwargs)

        if "message_type" not in params:
            if params.get("group_id", None):
                params["message_type"] = "group"
            elif params.get("user_id", None):
                params["message_type"] = "private"
            else:
                raise ValueError("Cannot guess message type to reply!")

        if at_sender and params["message_type"] != "private":
            params["message"] = MessageSegment.at(params["user_id"]) + " " + msg
        else:
            params["message"] = msg
        return await self.send_msg(**params)
