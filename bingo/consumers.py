import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async
from .models import Room, RoomPlayer

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"room_{self.room_id}"

        user = self.scope["user"]
        if isinstance(user, AnonymousUser):
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Registrar jugador en la sala (si no está)
        await self.add_player(user.id, self.room_id)

        # Enviar estado inicial
        await self.send_room_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Si necesitas manejar mensajes desde el cliente (por ahora no es obligatorio)
        pass

    async def send_room_state(self):
        room = await self.get_room(self.room_id)
        players = await self.get_players(self.room_id)

        now = timezone.now()
        remaining = max(0, int((room.wait_end_time - now).total_seconds()))
        if remaining == 0 and room.status == "waiting":
            # Cambiar a running solo una vez
            await self.set_room_running(room.id)
            # Avisar a todos que empieza la partida
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "start_game_event"}
            )

        data = {
            "type": "room_state",
            "players": players,
            "remaining_seconds": remaining,
            "status": room.status,
        }
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "room_state_event", "data": data}
        )

    async def room_state_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def start_game_event(self, event):
        await self.send(text_data=json.dumps({"type": "start_game"}))

    @sync_to_async
    def get_room(self, room_id):
        return Room.objects.get(pk=room_id)

    @sync_to_async
    def get_players(self, room_id):
        qs = RoomPlayer.objects.filter(room_id=room_id).select_related("user")
        return [rp.user.username for rp in qs]

    @sync_to_async
    def add_player(self, user_id, room_id):
        RoomPlayer.objects.get_or_create(user_id=user_id, room_id=room_id)

    @sync_to_async
    def set_room_running(self, room_id):
        room = Room.objects.get(pk=room_id)
        if room.status == "waiting":
            room.status = "running"
            room.save()
