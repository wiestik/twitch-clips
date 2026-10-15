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

# --- КАСТОМНЫЕ CSS-СТИЛИ ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e0e10;
    }
    
    [data-testid="stSidebar"] {
        background-color: #18181b;
        border-right: 1px solid #27272a;
    }
    
    .clip-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 12px;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    
    .clip-card:hover {
        transform: translateY(-4px);
        border-color: #9146ff;
        box-shadow: 0 8px 24px rgba(145, 70, 255, 0.25);
    }

    .clip-card img {
        border-radius: 8px;
        width: 100%;
        object-fit: cover;
    }

    .clip-tag {
        display: inline-block;
        background: #27272a;
        color: #adadb8;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 4px;
        margin-top: 6px;
        margin-right: 4px;
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
  return {"streamers": ["dangerlyoha"]}


def save_config(data):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
  except:
    pass


if "config" not in st.session_state:
  st.session_state["config"] = load_config()

cfg = st.session_state["config"]
if "streamers" not in cfg or not isinstance(cfg["streamers"], list):
  cfg["streamers"] = ["dangerlyoha"]

try:
  CLIENT_ID = st.secrets["TWITCH_CLIENT_ID"]
  CLIENT_SECRET = st.secrets["TWITCH_CLIENT_SECRET"]
except Exception:
  CLIENT_ID = ""
  CLIENT_SECRET = ""

# --- БОКОВАЯ ПАНЕЛЬ УПРАВЛЕНИЯ ---
with st.sidebar:
  st.title("⚙️ Управление")
  st.subheader("📺 Стримеры")

  new_streamer = st.text_input("Добавить стримера (ник)")
  if st.button("➕ Добавить"):
    clean_name = new_streamer.strip().lower()
    if clean_name and clean_name not in cfg["streamers"]:
      cfg["streamers"].append(clean_name)
      save_config(cfg)
      st.rerun()

  st.write("Список отслеживаемых:")
  for s in list(cfg["streamers"]):
    col_s1, col_s2 = st.columns([0.8, 0.2])
    with col_s1:
      st.code(s, language=None)
    with col_s2:
      if st.button("❌", key=f"del_{s}"):
        cfg["streamers"].remove(s)
        save_config(cfg)
        st.rerun()

  st.divider()
  auto_refresh = st.checkbox("🔄 Автообновление (каждые 5 мин)", value=True)
  
  # По умолчанию ставим "Сначала свежие", чтобы новые клипы всегда были первыми
  sort_option = st.selectbox(
      "Сортировка",
      [
          "Сначала свежие",
          "Сначала старые",
          "По просмотрам (убывание)",
          "По просмотрам (возрастание)",
      ],
  )

if auto_refresh:
  st_autorefresh(interval=300000, key="clips_refresh")

# --- TWITCH API ФУНКЦИИ ---


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
  raise Exception("Ошибка авторизации. Проверь секреты в настройках Streamlit.")


def get_user_id(username, headers):
  url = f"https://api.twitch.tv/helix/users?login={username}"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    data = res.json().get("data")
    if data:
      return data[0]["id"]
  raise Exception(f"Стример '{username}' не найден")


@st.cache_data(ttl=3600)
def fetch_games_data(cid, token):
  try:
    headers = {"Client-ID": cid, "Authorization": f"Bearer {token}"}
    url = "https://api.twitch.tv/helix/games/top?first=100"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
      data = res.json().get("data", [])
      id_to_name = {g["id"]: g["name"] for g in data}
      name_to_id = {g["name"]: g["id"] for g in data}
      return id_to_name, name_to_id
  except:
    pass
  return {}, {}


def get_all_clips(broadcaster_id, headers, game_id=None, max_clips=1000):
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
    if not fetched:
      break
    clips_data.extend(fetched)

    cursor = data.get("pagination", {}).get("cursor")
    if cursor and len(clips_data) < max_clips:
      params["after"] = cursor
    else:
      break
  return clips_data


# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.title("🟣 Twitch Clips Hub")
st.caption("Галерея клипов с выводом самых свежих материалов наверх")

streamers = cfg.get("streamers", [])

if not CLIENT_ID or not CLIENT_SECRET:
  st.error(
      "⚠️ Не найдены ключи `TWITCH_CLIENT_ID` и `TWITCH_CLIENT_SECRET` в"
      " секретах Streamlit!"
  )
else:
  try:
    token = get_twitch_token(CLIENT_ID, CLIENT_SECRET)
    id_to_name, name_to_id = fetch_games_data(CLIENT_ID, token)

    game_options = ["Все категории"] + sorted(list(name_to_id.keys()))
    selected_game = st.selectbox("🎮 Фильтр по категории / игре:", game_options)
    selected_game_id = (
        name_to_id.get(selected_game)
        if selected_game != "Все категории"
        else None
    )

    if st.button("🚀 Загрузить клипы", type="primary"):
      with st.spinner("Загрузка всех клипов из Twitch..."):
        headers = {"Client-ID": CLIENT_ID, "Authorization": f"Bearer {token}"}
        all_clips = []

        for username in streamers:
          try:
            b_id = get_user_id(username, headers)
            clips = get_all_clips(b_id, headers, game_id=selected_game_id)
            for clip in clips:
              thumb_url = clip.get("thumbnail_url", "")
              if "-preview-" in thumb_url:
                video_url = thumb_url.split("-preview-")[0] + ".mp4"
              else:
                video_url = clip.get("url")

              thumb = thumb_url.replace("{width}", "480").replace(
                  "{height}", "270"
              )

              g_id = clip.get("game_id")
              g_name = clip.get("game_name")
              if not g_name or g_name.strip() == "":
                g_name = id_to_name.get(g_id, "Без категории")

              all_clips.append({
                  "streamer": username,
                  "title": clip.get("title"),
                  "views": clip.get("view_count"),
                  "date": clip.get("created_at"),
                  "game": g_name,
                  "creator": clip.get("creator_name"),
                  "url": clip.get("url"),
                  "video_url": video_url,
                  "thumb": thumb,
              })
          except Exception as e:
            st.warning(f"Ошибка с каналом {username}: {e}")

        # ПРИНУДИТЕЛЬНАЯ СОРТИРОВКА (Сначала новые по дате создания)
        if sort_option == "Сначала свежие":
          all_clips.sort(key=lambda x: x["date"], reverse=True)
        elif sort_option == "Сначала старые":
          all_clips.sort(key=lambda x: x["date"], reverse=False)
        elif sort_option == "По просмотрам (убывание)":
          all_clips.sort(key=lambda x: x["views"], reverse=True)
        elif sort_option == "По просмотрам (возрастание)":
          all_clips.sort(key=lambda x: x["views"], reverse=False)

        st.session_state["clips"] = all_clips

  except Exception as e:
    st.error(f"Ошибка подключения к Twitch API: {e}")

# --- ОТОБРАЖЕНИЕ КАРТОЧЕК КЛИПОВ ---
if "clips" in st.session_state and st.session_state["clips"]:
  clips = st.session_state["clips"]
  st.write(f"Найдено клипов: **{len(clips)}**")

  cols_per_row = 3
  grid_cols = st.columns(cols_per_row)

  for idx, clip in enumerate(clips):
    col = grid_cols[idx % cols_per_row]
    with col:
      date_formatted = (
          clip["date"].replace("T", " ")[:16] if clip["date"] else ""
      )

      st.markdown(
          f"""
            <div class="clip-card">
                <img src="{clip['thumb']}">
                <h3 style="font-size: 1.05rem; margin-top: 10px; margin-bottom: 6px; color: #ffffff;">{clip['title']}</h3>
                <div>
                    <span class="clip-tag">🎮 {clip['game']}</span> 
                    <span class="clip-tag">📺 {clip['streamer']}</span>
                </div>
                <small style="color: #adadb8; display: block; margin-top: 6px;">👀 {clip['views']:,} просмотров • 📅 {date_formatted}</small>
                <small style="color: #adadb8; margin-bottom: 8px;">Автор: {clip['creator']}</small>
            </div>
            """,
          unsafe_allow_html=True,
      )

      b_col1, b_col2 = st.columns([1, 1])
      with b_col1:
        st.link_button(
            "▶ Смотреть", clip["url"], use_container_width=True
        )
      with b_col2:
        st.link_button(
            "📥 Скачать", clip["video_url"], use_container_width=True
        )
      st.write("")
