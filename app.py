from datetime import datetime
import json
import os
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Настройка страницы
st.set_page_config(
    page_title="Twitch Clips Hub", page_icon="🟣", layout="wide"
)

# --- КАСТОМНЫЕ CSS-СТИЛИ ДЛЯ СОВРЕМЕННОГО ДИЗАЙНА ---
st.markdown(
    """
    <style>
    /* Главный фон и отступы */
    .stApp {
        background-color: #0e0e10;
    }
    
    /* Стилизация боковой панели */
    [data-testid="stSidebar"] {
        background-color: #18181b;
        border-right: 1px solid #27272a;
    }
    
    /* Карточка клипа */
    div[data-testid="stColumn"] {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 12px;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    
    div[data-testid="stColumn"]:hover {
        transform: translateY(-4px);
        border-color: #9146ff;
        box-shadow: 0 8px 20px rgba(145, 70, 255, 0.2);
    }

    /* Изображение превью */
    div[data-testid="stColumn"] img {
        border-radius: 8px;
    }

    /* Кнопка Смотреть */
    a[kind="primary"], .stLinkButton > a {
        background-color: #9146ff !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        text-align: center;
        border: none !important;
    }
    
    a[kind="primary"]:hover, .stLinkButton > a:hover {
        background-color: #772ce8 !important;
    }
    
    /* Бейджи и метки */
    .clip-tag {
        display: inline-block;
        background: #27272a;
        color: #adadb8;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 4px;
        margin-top: 4px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

CONFIG_FILE = "twitch_config.json"


def load_config():
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except:
      pass
  return {"client_id": "", "client_secret": "", "streamers": "dangerlyoha"}


def save_config(data):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
  except:
    pass


config = load_config()

# --- БОКОВАЯ ПАНЕЛЬ НАСТРОЕК ---
with st.sidebar:
  st.title("⚙️ Управление")

  client_id = st.text_input("Client ID", value=config.get("client_id", ""))
  client_secret = st.text_input(
      "Client Secret", value=config.get("client_secret", ""), type="password"
  )
  streamers_input = st.text_input(
      "Стримеры (через запятую)", value=config.get("streamers", "")
  )

  st.divider()

  # Автообновление
  auto_refresh = st.checkbox("🔄 Автообновление (каждые 5 мин)", value=True)

  sort_option = st.selectbox(
      "Сортировка",
      [
          "По просмотрам (убывание)",
          "По просмотрам (возрастание)",
          "Сначала свежие",
          "Сначала старые",
      ],
  )

  if st.button("💾 Сохранить настройки", use_container_width=True):
    save_config({
        "client_id": client_id,
        "client_secret": client_secret,
        "streamers": streamers_input,
    })
    st.success("Сохранено!")

# Включение автообновления раз в 5 минут (300 000 мс)
if auto_refresh:
  st_autorefresh(interval=300000, key="clips_refresh")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ TWITCH API ---


def get_twitch_token(cid, csec):
  url = "https://id.twitch.tv/oauth2/token"
  params = {
      "client_id": cid,
      "client_secret": csec,
      "grant_type": "client_credentials",
  }
  res = requests.post(url, params=params)
  if res.status_code == 200:
    return res.json().get("access_token")
  raise Exception("Ошибка авторизации. Проверь Client ID и Secret.")


def get_user_id(username, headers):
  url = f"https://api.twitch.tv/helix/users?login={username}"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    data = res.json().get("data")
    if data:
      return data[0]["id"]
  raise Exception(f"Стример '{username}' не найден")


@st.cache_data(ttl=3600)
def fetch_top_games(cid, token):
  """Кэшируемая подгрузка популярных категорий для фильтра"""
  try:
    headers = {"Client-ID": cid, "Authorization": f"Bearer {token}"}
    url = "https://api.twitch.tv/helix/games/top?first=100"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
      return {g["name"]: g["id"] for g in res.json().get("data", [])}
  except:
    pass
  return {}


def get_all_clips(broadcaster_id, headers, game_id=None, max_clips=200):
  """Загрузка ВСЕХ клипов с поддержкой пагинации (без лимита в 29 клипов)"""
  url = "https://api.twitch.tv/helix/clips"
  params = {"broadcaster_id": broadcaster_id, "first": 100}
  if game_id:
    params["game_id"] = game_id

  clips_data = []
  while True:
    res = requests.get(url, headers=headers, params=params)
    if res.status_code != 200:
      break
    data = res.json()
    fetched = data.get("data", [])
    clips_data.extend(fetched)

    cursor = data.get("pagination", {}).get("cursor")
    if cursor and len(clips_data) < max_clips:
      params["after"] = cursor
    else:
      break
  return clips_data


# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.title("🟣 Twitch Clips Hub")
st.caption(
    "Персональная галерея клипов с поддержкой категорий и синхронизацией ПК & iOS"
)

if client_id and client_secret:
  try:
    token = get_twitch_token(client_id, client_secret)

    # Загружаем категории для выпадающего списка
    games_map = fetch_top_games(client_id, token)
    game_options = ["Все категории"] + list(games_map.keys())

    selected_game = st.selectbox("🎮 Фильтр по категории / игре:", game_options)
    selected_game_id = games_map.get(selected_game) if selected_game != "Все категории" else None

    if st.button("🚀 Загрузить клипы", type="primary"):
      with st.spinner("Загрузка всех клипов из Twitch..."):
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        streamers = [s.strip() for s in streamers_input.split(",") if s.strip()]

        all_clips = []
        for username in streamers:
          try:
            b_id = get_user_id(username, headers)
            clips = get_all_clips(b_id, headers, game_id=selected_game_id)
            for clip in clips:
              thumb = (
                  clip.get("thumbnail_url")
                  .replace("{width}", "480")
                  .replace("{height}", "270")
              )
              all_clips.append({
                  "streamer": username,
                  "title": clip.get("title"),
                  "views": clip.get("view_count"),
                  "date": clip.get("created_at"),
                  "game": clip.get("game_name", "Без категории"),
                  "creator": clip.get("creator_name"),
                  "url": clip.get("url"),
                  "thumb": thumb,
              })
          except Exception as e:
            st.warning(f"Ошибка с каналом {username}: {e}")

        # Сортировка
        if sort_option == "По просмотрам (убывание)":
          all_clips.sort(key=lambda x: x["views"], reverse=True)
        elif sort_option == "По просмотрам (возрастание)":
          all_clips.sort(key=lambda x: x["views"], reverse=False)
        elif sort_option == "Сначала свежие":
          all_clips.sort(key=lambda x: x["date"], reverse=True)
        elif sort_option == "Сначала старые":
          all_clips.sort(key=lambda x: x["date"], reverse=False)

        st.session_state["clips"] = all_clips

  except Exception as e:
    st.error(f"Ошибка подключения к Twitch API: {e}")
else:
  st.info("👈 Укажи Client ID и Client Secret в левой панели для начала работы.")

# --- ОТОБРАЖЕНИЕ КАРТОЧЕК КЛИПОВ ---
if "clips" in st.session_state and st.session_state["clips"]:
  clips = st.session_state["clips"]
  st.write(f"Найдено клипов: **{len(clips)}**")

  cols_per_row = 3
  cols = st.columns(cols_per_row)

  for idx, clip in enumerate(clips):
    col = cols[idx % cols_per_row]
    with col:
      st.image(clip["thumb"], use_container_width=True)
      st.markdown(f"### {clip['title']}")

      # Форматирование даты
      date_formatted = clip["date"][:10] if clip["date"] else ""

      st.markdown(f"""
            <span class="clip-tag">🎮 {clip['game']}</span> 
            <span class="clip-tag">📺 {clip['streamer']}</span>
            <br>
            <small style="color: #adadb8;">👀 {clip['views']:,} просмотров • 📅 {date_formatted}</small><br>
            <small style="color: #adadb8;">Автор клипа: {clip['creator']}</small>
            """, unsafe_allow_html=True)

      st.link_button(
          "▶ Смотреть на Twitch", clip["url"], use_container_width=True
      )
      st.write("")
