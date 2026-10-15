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

# --- СОВРЕМЕННЫЙ И СТИЛЬНЫЙ ДИЗАЙН ---
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
    
    /* Стилизация вкладок (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #121214;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #222226;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border-radius: 8px;
        color: #adadb8;
        font-weight: 600;
        border: none;
        padding: 0 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #9146ff !important;
        color: white !important;
    }

    /* Карточка клипа */
    .clip-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 14px;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    
    .clip-card:hover {
        transform: translateY(-4px);
        border-color: #9146ff;
        box-shadow: 0 6px 20px rgba(145, 70, 255, 0.2);
    }

    .clip-card img {
        border-radius: 8px;
        width: 100%;
        object-fit: cover;
    }

    .clip-tag {
        display: inline-block;
        background: #27272a;
        color: #efeff1;
        font-size: 0.75rem;
        padding: 3px 8px;
        border-radius: 6px;
        margin-top: 6px;
        margin-right: 4px;
        font-weight: 500;
    }
    
    /* Компактные фильтры */
    div[data-baseweb="select"] > div {
        background-color: #18181b !important;
        border-color: #27272a !important;
        border-radius: 8px !important;
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
          thumb = (
              clip.get("thumbnail_url", "")
              .replace("{width}", "480")
              .replace("{height}", "270")
          )
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
      params = {"game_id": game_id, "first": 40, "started_at": started_at}
      res = requests.get(clips_url, headers=headers, params=params)
      if res.status_code == 200:
        for clip in res.json().get("data", []):
          thumb = (
              clip.get("thumbnail_url", "")
              .replace("{width}", "480")
              .replace("{height}", "270")
          )
          clips.append({
              "streamer": clip.get("broadcaster_name"),
              "title": clip.get("title"),
              "views": clip.get("view_count"),
              "date": clip.get("created_at"),
              "creator": clip.get("creator_name"),
              "url": clip.get("url"),
              "thumb": thumb,
              "broadcaster_id": clip.get("broadcaster_id"),
          })
    else:
      top_games_url = "https://api.twitch.tv/helix/games/top?first=3"
      games_res = requests.get(top_games_url, headers=headers)
      if games_res.status_code == 200:
        game_ids = [g["id"] for g in games_res.json().get("data", [])]
        for g_id in game_ids:
          params = {"game_id": g_id, "first": 20, "started_at": started_at}
          res = requests.get(clips_url, headers=headers, params=params)
          if res.status_code == 200:
            for clip in res.json().get("data", []):
              thumb = (
                  clip.get("thumbnail_url", "")
                  .replace("{width}", "480")
                  .replace("{height}", "270")
              )
              clips.append({
                  "streamer": clip.get("broadcaster_name"),
                  "title": clip.get("title"),
                  "views": clip.get("view_count"),
                  "date": clip.get("created_at"),
                  "creator": clip.get("creator_name"),
                  "url": clip.get("url"),
                  "thumb": thumb,
                  "broadcaster_id": clip.get("broadcaster_id"),
              })
  except Exception:
    pass

  return clips, headers


def filter_clips_by_language(clips, target_lang, headers):
  """Исправленный и надежный фильтр языка через эндпоинт каналов Twitch"""
  if not target_lang or not clips:
    return clips

  b_ids = list(set([str(c["broadcaster_id"]) for c in clips if "broadcaster_id" in c]))
  if not b_ids:
    return clips

  lang_map = {}
  # Запрашиваем батчами по 100 ID
  for i in range(0, len(b_ids), 100):
    chunk = b_ids[i:i+100]
    channels_url = "https://api.twitch.tv/helix/channels?" + "&".join([f"broadcaster_id={uid}" for uid in chunk])
    res = requests.get(channels_url, headers=headers)
    if res.status_code == 200:
      for chan in res.json().get("data", []):
        lang_map[str(chan["broadcaster_id"])] = chan.get("broadcaster_language", "")

  filtered = []
  for clip in clips:
    b_id = str(clip.get("broadcaster_id"))
    if lang_map.get(b_id) == target_lang:
      filtered.append(clip)
  return filtered


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
  st.caption("Отслеживаемые:")
  for s in list(cfg["streamers"]):
    col_s1, col_s2 = st.columns([0.75, 0.25])
    with col_s1:
      st.text(s)
    with col_s2:
      if st.button("✕", key=f"del_{s}"):
        cfg["streamers"].remove(s)
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
        all_clips = fetch_clips_data(tuple(streamers), CLIENT_ID, CLIENT_SECRET)

        if sort_option == "Сначала свежие":
          all_clips.sort(key=lambda x: x["date"], reverse=True)
        else:
          all_clips.sort(key=lambda x: x["views"], reverse=True)

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
                        <h3 style="font-size: 1rem; margin-top: 8px; margin-bottom: 4px; color: #ffffff;">{clip['title']}</h3>
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
          st.warning("Клипы не найдены для выбранных каналов за последние дни.")

    # --- Вкладка 2: Рекомендации со всего Twitch (компактные стильные фильтры) ---
    with tab_trending:
      games_map = fetch_top_games(CLIENT_ID, CLIENT_SECRET)
      game_names = ["Все игры"] + sorted(list(games_map.keys()))

      # Компактные фильтры в одну строку
      f_col1, f_col2 = st.columns([1, 1])
      with f_col1:
        selected_game_name = st.selectbox("🎮 Категория", game_names, label_visibility="collapsed")
        if selected_game_name == "Все игры":
          st.caption("🎮 Категория: Все игры")
        else:
          st.caption(f"🎮 Категория: {selected_game_name}")
      with f_col2:
        lang_options = {
            "Все языки": None,
            "🇷🇺 Русский": "ru",
            "🇺🇦 Украинский": "uk",
            "🇺🇸 США / Английский": "en",
            "🇩🇪 Немецкий": "de",
            "🇫🇷 Французский": "fr",
            "🇪🇸 Испанский": "es"
        }
        selected_lang_label = st.selectbox("🌍 Язык", list(lang_options.keys()), label_visibility="collapsed")
        target_lang_code = lang_options[selected_lang_label]
        st.caption(f"🌍 Язык: {selected_lang_label}")

      selected_game_id = games_map.get(selected_game_name) if selected_game_name != "Все игры" else None

      trending_clips, api_headers = fetch_global_trending_clips(CLIENT_ID, CLIENT_SECRET, game_id=selected_game_id)

      if target_lang_code and trending_clips:
        trending_clips = filter_clips_by_language(trending_clips, target_lang_code, api_headers)

      trending_clips.sort(key=lambda x: x["views"], reverse=True)

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
                      <h3 style="font-size: 1rem; margin-top: 8px; margin-bottom: 4px; color: #ffffff;">{clip['title']}</h3>
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
        st.warning("По вашему фильтру клипы не найдены. Попробуйте выбрать другую категорию или язык.")

  except Exception as e:
    st.error(f"Ошибка загрузки: {e}")
