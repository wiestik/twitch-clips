from datetime import datetime
import json
import os
import streamlit as st
import requests

# Настройка страницы (широкий формат, иконка)
st.set_page_config(
    page_title="Twitch Clips Gallery", page_icon="📺", layout="wide"
)

CONFIG_FILE = "twitch_config.json"


def load_config():
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except:
      pass
  return {"client_id": "", "client_secret": "", "streamers": "s1mple, buster"}


def save_config(data):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
  except:
    pass


config = load_config()

# --- БОКОВАЯ ПАНЕЛЬ НАСТРОЕК ---
with st.sidebar:
  st.header("⚙️ Настройки и Стримеры")
  client_id = st.text_input(
      "Client ID", value=config.get("client_id", ""), type="default"
  )
  client_secret = st.text_input(
      "Client Secret", value=config.get("client_secret", ""), type="password"
  )
  streamers_input = st.text_input(
      "Стримеры (через запятую)", value=config.get("streamers", "")
  )

  sort_option = st.selectbox(
      "Сортировка клипов", [
          "По просмотрам (убывание)",
          "По просмотрам (возрастание)",
          "Сначала свежие",
      ]
  )

  if st.button("💾 Сохранить настройки"):
    save_config({
        "client_id": client_id,
        "client_secret": client_secret,
        "streamers": streamers_input,
    })
    st.success("Настройки успешно сохранены!")

st.title("📺 Twitch Clips Gallery (ПК & iOS)")
st.write(
    "Удобная галерея клипов с возможностью просмотра на компьютере и телефоне."
)


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
  raise Exception("Ошибка авторизации в Twitch API. Проверь ключи.")


def get_user_id(username, headers):
  url = f"https://api.twitch.tv/helix/users?login={username}"
  res = requests.get(url, headers=headers)
  if res.status_code == 200:
    data = res.json().get("data")
    if data:
      return data[0]["id"]
  raise Exception(f"Стример '{username}' не найден")


def get_clips(broadcaster_id, headers):
  url = "https://api.twitch.tv/helix/clips"
  params = {"broadcaster_id": broadcaster_id, "first": 30}
  res = requests.get(url, headers=headers, params=params)
  if res.status_code == 200:
    return res.json().get("data", [])
  return []


if st.button("🚀 Загрузить клипы", type="primary"):
  if not client_id or not client_secret or not streamers_input:
    st.error("Заполни Client ID, Client Secret и список стримеров в боковом меню!")
  else:
    with st.spinner("Загрузка клипов из Twitch..."):
      try:
        token = get_twitch_token(client_id, client_secret)
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        streamers = [s.strip() for s in streamers_input.split(",") if s.strip()]

        all_clips = []
        for username in streamers:
          try:
            b_id = get_user_id(username, headers)
            clips = get_clips(b_id, headers)
            for clip in clips:
              thumb = (
                  clip.get("thumbnail_url")
                  .replace("{width}", "320")
                  .replace("{height}", "180")
              )
              all_clips.append({
                  "streamer": username,
                  "title": clip.get("title"),
                  "views": clip.get("view_count"),
                  "date": clip.get("created_at"),
                  "url": clip.get("url"),
                  "thumb": thumb,
              })
          except Exception as e:
            st.warning(f"Не удалось загрузить клипы для {username}: {e}")

        # Сортировка
        if sort_option == "По просмотрам (убывание)":
          all_clips.sort(key=lambda x: x["views"], reverse=True)
        elif sort_option == "По просмотрам (возрастание)":
          all_clips.sort(key=lambda x: x["views"], reverse=False)
        elif sort_option == "Сначала свежие":
          all_clips.sort(key=lambda x: x["date"], reverse=True)

        st.session_state["clips"] = all_clips
        st.success(f"Успешно загружено клипов: {len(all_clips)}")
      except Exception as e:
        st.error(f"Ошибка: {e}")

# --- ОТОБРАЖЕНИЕ СЕТКИ КЛИПОВ ---
if "clips" in st.session_state and st.session_state["clips"]:
  clips = st.session_state["clips"]
  cols = st.columns(3)  # Сетка по 3 карточки в ряд

  for idx, clip in enumerate(clips):
    col = cols[idx % 3]
    with col:
      st.image(clip["thumb"], use_container_width=True)
      st.markdown(f"**{clip['title']}**")
      st.caption(f"📺 {clip['streamer']} | 👀 {clip['views']} просмотров")
      st.markdown(f"[▶ Смотреть на Twitch]({clip['url']})")
      st.divider()