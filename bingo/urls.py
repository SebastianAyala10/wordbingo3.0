from django.urls import path
from . import views

app_name = "bingo"

urlpatterns = [
    path("", views.home, name="home"),
    path("lobby/", views.lobby, name="lobby"),
    path("rooms/<int:room_id>/bingo/", views.claim_bingo, name="claim_bingo"),
    path("rooms/create/", views.create_room, name="create_room"),
    path("rooms/", views.room_list, name="room_list"),
    path("rooms/<int:room_id>/waiting/", views.waiting_room_view, name="waiting_room"),
    path("rooms/<int:room_id>/status/", views.room_status_api, name="room_status_api"),
    path("rooms/<int:room_id>/start/", views.start_game, name="start_game"),
    path("rooms/<int:room_id>/game/", views.game_view, name="game"),
    path("rooms/<int:room_id>/state/", views.game_state_api, name="game_state_api"),
    path("rooms/<int:room_id>/call-next/", views.call_next_word, name="call_next_word"),
    path("rooms/<int:room_id>/finish/", views.finish_game, name="finish_game"),
]
