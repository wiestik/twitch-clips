from datetime import datetime, timedelta, timezone
import json
import os
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Настройка страницы
st.set_page_config(
    page_title="Twitch Clips Hub", page_icon="🟣", layout="wide"
)

# --- МИНИМАЛИСТИЧНЫЙ ДИЗАЙН БЕЗ ФИОЛЕТОВОЙ ПОДСВЕТКИ ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e0e10;
        color: #efeff1;
    }
    
    [data-testid="stSidebar"] {
        background-color: #121214;
        border-right: 1px solid #222226;
        padding-top: 1rem;
    }
    
    /* Стилизация вкладок (убрана яркая подсветка) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #121214;
        padding: 4px;
        border-radius: 10px;
        border: 1px solid #222226;
        width: fit-content;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 36px;
        background-color: transparent;
        border-radius: 6px;
        color: #848494;
        font-weight: 500;
        font-size: 0.9rem;
        border: none;
        padding: 0 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #27272a !important;
        color: #ffffff !important;
        border-bottom: 2px solid #9146ff !important;
    }

    /* Карточка клипа */
    .clip-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 14px;
        display: flex;
        flex-direction: column;
        height: 100%;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }

    .clip-card:hover {
        transform: translateY(-3px);
        border-color: #9146ff;
    }

    .clip-card img {
        border-radius: 6px;
        width: 100%;
        object-fit: cover;
    }

    .clip-tag {
        display: inline-block;
        background: #27272a;
        color: #efeff1;
        font-size: 0.75rem;
        padding: 2px 6px;
        border-radius: 4px;
        margin-top: 6px;
        margin-right: 4px;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #18181b !important;
        border-color: #27272a !important;
        border-radius: 8px !important;
        min-height: 36px !important;
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
  raise Exception("Ошибка авторизации. Проверь секреты в Streamlit.")


def search_twitch_channels(query, headers):
  if not query or len(query.strip()) < 2:
    return []
  url = f"https://api.twitch.tv/helix/search/channels?query={query.strip()}&first=5"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    data = res.json().get("data", [])
    return [chan["display_name"] for chan in data]
  return []


def get_user_id(username, headers):
  url = f"https://api.twitch.tv/helix/users?login={username}"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    data = res.json().get("data")
    if data:
      return data[0]["id"]
  return None


@st.cache_data(ttl=3600)
def fetch_top_games(client_id, client_secret):
  token = get_twitch_token(client_id, client_secret)
  headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
  url = "https://api.twitch.tv/helix/games/top?first=50"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    return {g["name"]: g["id"] for g in res.json().get("data", [])}
  return {}


@st.cache_data(ttl=60)
def fetch_clips_data(streamers_tuple, client_id, client_secret):
  token = get_twitch_token(client_id, client_secret)
  headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}

  all_clips = []
  for username in streamers_tuple:
    b_id = get_user_id(username, headers)
    if b_id:
      url = "https://api.twitch.tv/helix/clips"
      started_at = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
      params = {
          "broadcaster_id": b_id,
          "first": 30,
          "started_at": started_at,
      }
      res = requests.get(url, headers=headers, params=params)
      if res.status_code == 200:
        for clip in res.json().get("data", []):
          thumb_url = clip.get("thumbnail_url", "")
          thumb = thumb_url.replace("{width}", "480").replace("{height}", "270")
          all_clips.append({
              "streamer": clip.get("broadcaster_name", username),
              "title": clip.get("title"),
              "views": clip.get("view_count"),
              "date": clip.get("created_at"),
              "creator": clip.get("creator_name"),
              "url": clip.get("url"),
              "thumb": thumb,
          })
  return all_clips


@st.cache_data(ttl=60)
def fetch_global_trending_clips(client_id, client_secret, game_id=None):
  token = get_twitch_token(client_id, client_secret)
  headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}

  clips = []
  try:
    started_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    clips_url = "https://api.twitch.tv/helix/clips"
    
    if game_id:
      params = {"game_id": game_id, "first": 30, "started_at": started_at}
      res = requests.get(clips_url, headers=headers, params=params)
      if res.status_code == 200:
        clips.extend(res.json().get("data", []))
    else:
      top_games_url = "https://api.twitch.tv/helix/games/top?first=3"
      games_res = requests.get(top_games_url, headers=headers)
      if games_res.status_code == 200:
        game_ids = [g["id"] for g in games_res.json().get("data", [])]
        for g_id in game_ids:
          p = {"game_id": g_id, "first": 15, "started_at": started_at}
          res = requests.get(clips_url, headers=headers, params=p)
          if res.status_code == 200:
            clips.extend(res.json().get("data", []))
  except Exception:
    pass

  formatted_clips = []
  for clip in clips:
    thumb_url = clip.get("thumbnail_url", "")
    thumb = thumb_url.replace("{width}", "480").replace("{height}", "270")
    formatted_clips.append({
        "streamer": clip.get("broadcaster_name"),
        "title": clip.get("title"),
        "views": clip.get("view_count"),
        "date": clip.get("created_at"),
        "creator": clip.get("creator_name"),
        "url": clip.get("url"),
        "thumb": thumb,
    })
  
  formatted_clips.sort(key=lambda x: x["views"], reverse=True)
  return formatted_clips


# --- МИНИМАЛИСТИЧНАЯ БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
  st.markdown("### ⚙️ Каналы")

  headers_temp = {}
  if CLIENT_ID and CLIENT_SECRET:
    try:
      t = get_twitch_token(CLIENT_ID, CLIENT_SECRET)
      headers_temp = {"Client-ID": CLIENT_ID, "Authorization": f"Bearer {t}"}
    except:
      pass

  search_query = st.text_input(
      "Добавить стримера", placeholder="Введите ник...", label_visibility="collapsed"
  )

  if search_query and headers_temp:
    if "last_query" not in st.session_state or st.session_state["last_query"] != search_query:
      st.session_state["last_query"] = search_query
      st.session_state["suggestions"] = search_twitch_channels(search_query, headers_temp)

    suggestions = st.session_state.get("suggestions", [])
    if suggestions:
      selected_suggestion = st.selectbox(
          "Похожие на Twitch:", ["Выберите канал..."] + suggestions
      )
      if selected_suggestion != "Выберите канал...":
        clean_name = selected_suggestion.strip().lower()
        if clean_name not in cfg["streamers"]:
          cfg["streamers"].append(clean_name)
          save_config(cfg)
          st.rerun()

  if st.button("➕ Добавить"):
    if search_query:
      clean_name = search_query.strip().lower()
      if clean_name not in cfg["streamers"]:
        cfg["streamers"].append(clean_name)
        save_config(cfg)
        st.rerun()

  st.markdown("---")
  sort_option = st.selectbox(
      "Сортировка", ["Сначала свежие", "По просмотрам"]
  )
  auto_refresh = st.checkbox("Режим реального времени (1 мин)", value=True)

if auto_refresh:
  st_autorefresh(interval=60000, key="clips_refresh")

# --- ГЛАВНЫЙ ЭКРАН И ВКЛАДКИ ---
st.title("🟣 Twitch Clips Hub")

if not CLIENT_ID or not CLIENT_SECRET:
  st.error("⚠️ Укажите `TWITCH_CLIENT_ID` и `TWITCH_CLIENT_SECRET` в секретах Streamlit!")
else:
  try:
    tab_subs, tab_trending = st.tabs(["📺 Мои стримеры", "🔥 Рекомендации Twitch"])

    # --- Вкладка 1: Подписки ---
    with tab_subs:
      streamers = cfg.get("streamers", [])
      if not streamers:
        st.info("👈 Добавьте хотя бы одного стримера в боковой панели.")
      else:
        search_keyword = st.text_input("🔍 Поиск клипа (по названию или стримеру):", key="search_subs")

        all_clips = fetch_clips_data(tuple(streamers), CLIENT_ID, CLIENT_SECRET)

        if sort_option == "Сначала свежие":
          all_clips.sort(key=lambda x: x["date"], reverse=True)
        else:
          all_clips.sort(key=lambda x: x["views"], reverse=True)

        if search_keyword:
          kw = search_keyword.lower()
          all_clips = [c for c in all_clips if kw in c["title"].lower() or kw in c["streamer"].lower() or kw in c["creator"].lower()]

        if all_clips:
          cols_per_row = 3
          grid_cols = st.columns(cols_per_row)
          for idx, clip in enumerate(all_clips):
            col = grid_cols[idx % cols_per_row]
            with col:
              date_formatted = (
                  clip["date"].replace("T", " ")[:16] if clip["date"] else ""
              )
              
              st.markdown(
                  f"""
                    <div class="clip-card">
                        <img src="{clip['thumb']}">
                        <h3 style="font-size: 0.95rem; margin-top: 8px; margin-bottom: 4px; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{clip['title']}">{clip['title']}</h3>
                        <div>
                            <span class="clip-tag">📺 {clip['streamer']}</span>
                        </div>
                        <small style="color: #adadb8; display: block; margin-top: 6px;">👀 {clip['views']:,} • 📅 {date_formatted}</small>
                        <small style="color: #adadb8; margin-bottom: 8px;">Автор: {clip['creator']}</small>
                    </div>
                    """,
                  unsafe_allow_html=True,
              )
              st.link_button(
                  "▶ Смотреть на Twitch", clip["url"], use_container_width=True
              )
              st.write("")
        else:
          st.warning("Клипы не найдены.")

    # --- Вкладка 2: Рекомендации со всего Twitch ---
    with tab_trending:
      games_map = fetch_top_games(CLIENT_ID, CLIENT_SECRET)
      game_names = ["Все игры"] + sorted(list(games_map.keys()))

      f_col1, f_col2 = st.columns([1, 1])
      with f_col1:
        selected_game_name = st.selectbox("🎮 Категория", game_names, label_visibility="collapsed")
      with f_col2:
        search_keyword_trend = st.text_input("🔍 Поиск по ключевым словам", placeholder="Название клипа...", label_visibility="collapsed")

      selected_game_id = games_map.get(selected_game_name) if selected_game_name != "Все игры" else None

      trending_clips = fetch_global_trending_clips(CLIENT_ID, CLIENT_SECRET, game_id=selected_game_id)

      if search_keyword_trend:
        kw = search_keyword_trend.lower()
        trending_clips = [c for c in trending_clips if kw in c["title"].lower() or kw in c["streamer"].lower() or kw in c["creator"].lower()]

      if trending_clips:
        t_cols_per_row = 3
        t_grid_cols = st.columns(t_cols_per_row)
        for idx, clip in enumerate(trending_clips):
          col = t_grid_cols[idx % t_cols_per_row]
          with col:
            date_formatted = (
                clip["date"].replace("T", " ")[:16] if clip["date"] else ""
            )
            
            st.markdown(
                f"""
                  <div class="clip-card">
                      <img src="{clip['thumb']}">
                      <h3 style="font-size: 0.95rem; margin-top: 8px; margin-bottom: 4px; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{clip['title']}">{clip['title']}</h3>
                      <div>
                          <span class="clip-tag">📺 {clip['streamer']}</span>
                      </div>
                      <small style="color: #adadb8; display: block; margin-top: 6px;">👀 {clip['views']:,} • 📅 {date_formatted}</small>
                      <small style="color: #adadb8; margin-bottom: 8px;">Автор: {clip['creator']}</small>
                  </div>
                  """,
                unsafe_allow_html=True,
            )
            st.link_button(
                "▶ Смотреть на Twitch", clip["url"], use_container_width=True
            )
            st.write("")
      else:
        st.warning("Клипы не найдены.")

  except Exception as e:
    st.error(f"Ошибка загрузки: {e}")
