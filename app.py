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

# --- МИНИМАЛИСТИЧНЫЙ И СДЕРЖАННЫЙ ДИЗАЙН ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e0e10;
    }
    
    [data-testid="stSidebar"] {
        background-color: #121214;
        border-right: 1px solid #222226;
        padding-top: 1rem;
    }
    
    .clip-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        transition: transform 0.2s ease, border-color 0.2s ease;
        display: flex;
        flex-direction: column;
        height: 100%;
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
        color: #adadb8;
        font-size: 0.75rem;
        padding: 2px 6px;
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


# Кэшируем запросы на 60 секунд, чтобы убрать подлагивания интерфейса при автообновлении
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
          "first": 50,
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
              "streamer": username,
              "title": clip.get("title"),
              "views": clip.get("view_count"),
              "date": clip.get("created_at"),
              "creator": clip.get("creator_name"),
              "url": clip.get("url"),
              "thumb": thumb,
          })
  return all_clips


@st.cache_data(ttl=60)
def fetch_global_trending_clips(client_id, client_secret):
  """Загружает популярные/рекомендованные клипы со всего Twitch за неделю"""
  token = get_twitch_token(client_id, client_secret)
  headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
  
  url = "https://api.twitch.tv/helix/clips"
  started_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
  params = {"first": 30, "started_at": started_at, "is_featured": "true"}
  
  res = requests.get(url, headers=headers, params=params)
  clips = []
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
      })
  return clips


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
    # Создаем вкладки интерфейса
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

    # --- Вкладка 2: Рекомендации со всего Twitch ---
    with tab_trending:
      st.caption("Популярные и трендовые клипы на платформе в реальном времени")
      trending_clips = fetch_global_trending_clips(CLIENT_ID, CLIENT_SECRET)

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
        st.warning("Не удалось загрузить рекомендации с Twitch.")

  except Exception as e:
    st.error(f"Ошибка загрузки: {e}")
